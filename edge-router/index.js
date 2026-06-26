/**
 * NEXORA Edge Router — Cloudflare Worker that proxies LLM requests.
 *
 * Accepts POST /            → chat-completion request (JSON in, text out)
 * Accepts POST /tts         → text-to-speech (binary audio out)
 * Accepts GET  /, /health   → diagnostic JSON
 *
 * Provider fallback chain:
 *   1. Cloudflare Workers AI binding (`env.AI`) — primary
 *   2. OpenAI (via `x-api-key` header or `OPENAI_API_KEY` secret)
 *   3. Cloudflare AI REST API (`CLOUDFLARE_API_TOKEN` + `CF_AI_MODELS`)
 *   4. OpenRouter (free models by default)
 */
const OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
const OPENAI_TTS_URL = 'https://api.openai.com/v1/audio/speech'
const OPENROUTER_URL = 'https://api.openrouter.ai/v1/chat/completions'
const CLOUDFLARE_AI_URL = 'https://api.cloudflare.com/client/v4/ai/generate'

const SYSTEM_PROMPT = `You are NEXORA, a highly qualified medical AI assistant with PhD-level clinical knowledge. Provide safe, accurate, and practical guidance to rural health workers. Be concise, factual, and do not hallucinate. Always respond in the language of the user's last message (Bengali or English).`

const TTS_MODEL = '@cf/myshell-ai/melotts'

// CF model aliases — front-end picks one of these.
const CF_MODEL_ALIASES = {
  'cf-claude': '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
  'cf-llama': '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
  'cf-qwen': '@cf/meta/llama-3.1-8b-instruct',
  'cf-gemma': '@cf/google/gemma-3-12b-it',
  'cf-mistral': '@cf/mistral/mistral-7b-instruct-v0.2',
  'cf-deepseek': '@cf/deepseek-ai/deepseek-r1-distill-qwen-32b',
}
const DEFAULT_CF_MODEL = '@cf/meta/llama-3.1-8b-instruct'
const CF_AI_MODELS_DEFAULT = '@cf/meta/llama-3.1-8b-instruct'
const OPENROUTER_MODELS_DEFAULT = 'meta-llama/llama-3.1-8b-instruct:free'

function envArray(value, fallback) {
  if (!value) return fallback.split(',').map((s) => s.trim()).filter(Boolean)
  return value.split(',').map((s) => s.trim()).filter(Boolean)
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url)

    // CORS preflight — include the headers our clients actually use.
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(),
      })
    }

    if (request.method === 'GET' && (url.pathname === '/' || url.pathname === '/health')) {
      return cors(
        JSON.stringify({
          status: 'ok',
          worker: 'NEXORA Cloudflare AI Proxy',
          ai_binding: Boolean(env?.AI),
          models: Array.from(
            new Set([
              ...envArray(env?.CF_AI_MODELS, CF_AI_MODELS_DEFAULT),
              ...envArray(env?.OPENROUTER_MODELS, OPENROUTER_MODELS_DEFAULT),
              DEFAULT_CF_MODEL,
            ]),
          ),
          supported_languages: ['en', 'bn'],
        }),
      )
    }

    if (request.method !== 'POST') {
      return cors(JSON.stringify({ error: 'Method not allowed' }), 405)
    }

    if (url.pathname === '/tts') {
      return handleTTS(request, env)
    }

    return handleChat(request, env)
  },
}

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-api-key, x-lang',
    'Access-Control-Max-Age': '86400',
  }
}

function cors(body, status = 200, extra = {}) {
  return new Response(body, {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(), ...extra },
  })
}

function normalizeMessages(payload) {
  if (Array.isArray(payload.messages) && payload.messages.length > 0) {
    return payload.messages
  }
  if (payload.prompt) return [{ role: 'user', content: String(payload.prompt) }]
  if (payload.input) return [{ role: 'user', content: String(payload.input) }]
  return []
}

function ensureSystemMessage(messages, lang) {
  if (messages.some((m) => m.role === 'system')) return messages
  const langHint =
    lang === 'bn'
      ? ' The user is communicating in Bengali — reply in Bengali (বাংলা).'
      : ' Reply in English unless the user clearly asks for another language.'
  return [{ role: 'system', content: SYSTEM_PROMPT + langHint }, ...messages]
}

function aliasToCFModel(alias) {
  if (!alias) return null
  return CF_MODEL_ALIASES[alias] || alias
}

function buildTextFromMessages(messages) {
  return messages.map(({ role, content }) => `${role}: ${content}`).join('\n')
}

async function fetchOpenAI(payload, apiKey) {
  return fetch(OPENAI_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(payload),
  })
}

async function fetchCloudflareAI(messages, payload, model, apiToken) {
  if (!apiToken) throw new Error('Cloudflare AI token not configured')
  const input = buildTextFromMessages(messages)
  const body = {
    model: model || payload.model || CF_AI_MODELS_DEFAULT,
    input,
    max_output_tokens: payload.max_tokens || 900,
  }
  return fetch(CLOUDFLARE_AI_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiToken}`,
    },
    body: JSON.stringify(body),
  })
}

async function fetchOpenRouter(payload, model, apiKey) {
  const headers = { 'Content-Type': 'application/json' }
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`
  const routerPayload = {
    model: model || payload.model || OPENROUTER_MODELS_DEFAULT,
    messages: normalizeMessages(payload),
    temperature: payload.temperature ?? 0.7,
    max_tokens: payload.max_tokens ?? 900,
  }
  return fetch(OPENROUTER_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify(routerPayload),
  })
}

async function fetchOpenRouterWithFallback(payload, apiKey, models) {
  const errors = []
  for (const model of models) {
    try {
      const response = await fetchOpenRouter(payload, model, apiKey)
      if (response.ok) {
        return await parseModelResponse(response)
      }
      const body = await response.text()
      errors.push(`OpenRouter model ${model} failed ${response.status}: ${body.slice(0, 200)}`)
    } catch (err) {
      errors.push(`OpenRouter model ${model} error: ${err.message}`)
    }
  }
  throw new Error(errors.join(' | '))
}

async function parseModelResponse(response) {
  const text = await response.text()
  if (!response.ok) {
    throw new Error(`Provider returned ${response.status}: ${text.slice(0, 200)}`)
  }
  try {
    const json = JSON.parse(text)
    if (json.choices?.[0]?.message?.content) return json.choices[0].message.content
    if (json.output?.[0]?.content) return json.output[0].content
    return text
  } catch (_e) {
    return text
  }
}

async function runWorkersAI(payload, env, lang) {
  const messages = ensureSystemMessage(normalizeMessages(payload), lang)
  const alias = payload.model
  const modelName = aliasToCFModel(alias) || payload.model || DEFAULT_CF_MODEL
  const temperature = payload.temperature ?? 0.7
  const max_tokens = payload.max_tokens || 900

  const result = await env.AI.run(modelName, {
    messages,
    temperature,
    max_tokens,
  })

  const text = (result?.response || result?.result?.response || '').trim()
  if (!text) throw new Error('Workers AI binding returned empty response')
  return text
}

async function routeWithFallback(request, payload, env) {
  const lang = payload.lang || request.headers.get('x-lang') || 'en'
  const errors = []

  if (env?.AI) {
    try {
      return await runWorkersAI(payload, env, lang)
    } catch (err) {
      errors.push(`Workers AI binding failed: ${err.message}`)
    }
  }

  const callerKey = request.headers.get('x-api-key')
  const openaiKey = callerKey || env?.OPENAI_API_KEY || ''
  if (openaiKey) {
    try {
      const response = await fetchOpenAI(payload, openaiKey)
      if (response.ok) return await response.text()
      const body = await response.text()
      errors.push(`OpenAI failed ${response.status}: ${body.slice(0, 200)}`)
    } catch (err) {
      errors.push(`OpenAI error: ${err.message}`)
    }
  }

  const cfToken = env?.CLOUDFLARE_API_TOKEN || ''
  if (cfToken) {
    const cfModels = payload.model ? [payload.model] : envArray(env?.CF_AI_MODELS, CF_AI_MODELS_DEFAULT)
    for (const model of cfModels) {
      try {
        const response = await fetchCloudflareAI(
          ensureSystemMessage(normalizeMessages(payload), lang),
          payload,
          model,
          cfToken,
        )
        if (response.ok) {
          const json = await response.json()
          if (json?.result?.output?.[0]?.content) return json.result.output[0].content
          if (json?.result?.output) return JSON.stringify(json.result.output)
          return JSON.stringify(json)
        }
        const body = await response.text()
        errors.push(`Cloudflare AI model ${model} failed ${response.status}: ${body.slice(0, 200)}`)
      } catch (err) {
        errors.push(`Cloudflare AI model ${model} error: ${err.message}`)
      }
    }
  }

  const orModels = envArray(env?.OPENROUTER_MODELS, OPENROUTER_MODELS_DEFAULT)
  const orKey = env?.OPENROUTER_API_KEY || ''
  try {
    return await fetchOpenRouterWithFallback(payload, orKey, orModels)
  } catch (err) {
    errors.push(`OpenRouter failed: ${err.message}`)
  }

  throw new Error(errors.join(' | '))
}

async function handleChat(request, env) {
  let payload
  try {
    payload = await request.json()
  } catch (err) {
    return cors(JSON.stringify({ error: 'Invalid JSON payload', detail: err.message }), 400)
  }

  try {
    const text = await routeWithFallback(request, payload, env)
    return new Response(text, {
      status: 200,
      headers: { 'Content-Type': 'text/plain; charset=utf-8', ...corsHeaders() },
    })
  } catch (err) {
    return cors(JSON.stringify({ error: 'All providers failed', detail: err.message }), 502)
  }
}

async function handleTTS(request, env) {
  let payload
  try {
    payload = await request.json()
  } catch (err) {
    return cors(JSON.stringify({ error: 'Invalid JSON payload', detail: err.message }), 400)
  }

  const text = (payload?.text || '').trim()
  if (!text) {
    return cors(JSON.stringify({ error: 'text is required' }), 400)
  }

  const lang = payload?.lang || 'en'

  if (env?.AI) {
    try {
      const result = await env.AI.run(TTS_MODEL, { prompt: text, lang })
      let bytes
      if (result instanceof ArrayBuffer) {
        bytes = new Uint8Array(result)
      } else if (result instanceof Uint8Array) {
        bytes = result
      } else {
        const audioB64 = typeof result === 'string'
          ? result
          : (result?.audio || result?.result?.audio || '')
        if (!audioB64) throw new Error('TTS binding returned empty audio')
        bytes = Uint8Array.from(atob(audioB64), (c) => c.charCodeAt(0))
      }
      return new Response(bytes, {
        status: 200,
        headers: {
          'Content-Type': 'audio/mpeg',
          'Content-Length': String(bytes.length),
          ...corsHeaders(),
        },
      })
    } catch (err) {
      // Fall through to OpenAI TTS if configured.
      console.error('Workers AI TTS failed:', err.message)
    }
  }

  const openaiKey = env?.OPENAI_API_KEY || ''
  if (!openaiKey) {
    return cors(
      JSON.stringify({ error: 'No TTS provider configured', detail: 'Missing Workers AI binding or OpenAI key' }),
      500,
    )
  }

  try {
    const voice = lang === 'bn' ? 'shimmer' : (payload?.voice || 'alloy')
    const response = await fetch(OPENAI_TTS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${openaiKey}`,
        Accept: 'audio/mpeg',
      },
      body: JSON.stringify({
        model: payload?.model || 'gpt-4o-mini-tts',
        voice,
        input: text,
      }),
    })
    if (!response.ok) {
      const body = await response.text()
      return cors(JSON.stringify({ error: 'OpenAI TTS failed', detail: body }), response.status)
    }
    const arrayBuffer = await response.arrayBuffer()
    return new Response(arrayBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'audio/mpeg',
        ...corsHeaders(),
      },
    })
  } catch (err) {
    return cors(JSON.stringify({ error: 'TTS failed', detail: err.message }), 502)
  }
}
