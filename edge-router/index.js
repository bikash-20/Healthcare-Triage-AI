const OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
const OPENROUTER_URL = 'https://api.openrouter.ai/v1/chat/completions'
const CLOUDFLARE_AI_URL = 'https://api.cloudflare.com/client/v4/ai/generate'

const OPENAI_KEY = globalThis.OPENAI_API_KEY || ''
const CF_AI_KEY = globalThis.CLOUDFLARE_API_TOKEN || ''
const OPENROUTER_KEY = globalThis.OPENROUTER_API_KEY || ''

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' }
  })
}

function normalizeMessages(payload) {
  if (Array.isArray(payload.messages)) {
    return payload.messages
  }
  if (payload.prompt) {
    return [{ role: 'user', content: payload.prompt }]
  }
  if (payload.input) {
    return [{ role: 'user', content: String(payload.input) }]
  }
  return []
}

function buildTextFromMessages(messages) {
  return messages.map(({ role, content }) => `${role}: ${content}`).join('\n')
}

async function fetchOpenAI(payload, apiKey) {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiKey}`
  }
  return fetch(OPENAI_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  })
}

async function fetchCloudflareAI(messages, payload) {
  if (!CF_AI_KEY) {
    throw new Error('Cloudflare AI token not configured')
  }
  const input = buildTextFromMessages(messages)
  const body = {
    model: payload.model || 'gpt-4o-mini',
    input,
    max_output_tokens: payload.max_tokens || 900
  }
  return fetch(CLOUDFLARE_AI_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${CF_AI_KEY}`
    },
    body: JSON.stringify(body)
  })
}

async function fetchOpenRouter(payload) {
  const headers = { 'Content-Type': 'application/json' }
  if (OPENROUTER_KEY) {
    headers.Authorization = `Bearer ${OPENROUTER_KEY}`
  }
  const routerPayload = {
    model: payload.model || 'meta-llama/llama-3.1-8b-instruct:free',
    messages: normalizeMessages(payload),
    temperature: payload.temperature ?? 0.7,
    max_tokens: payload.max_tokens ?? 900
  }
  return fetch(OPENROUTER_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify(routerPayload)
  })
}

async function parseModelResponse(response) {
  const text = await response.text()
  if (response.ok) {
    try {
      const json = JSON.parse(text)
      if (json.choices?.[0]?.message?.content) {
        return json.choices[0].message.content
      }
      if (json.output?.[0]?.content) {
        return json.output[0].content
      }
      return text
    } catch (_e) {
      return text
    }
  }
  throw new Error(`Provider returned ${response.status}: ${text}`)
}

async function routeWithFallback(request, payload) {
  const messages = normalizeMessages(payload)
  const errors = []

  if (request.headers.get('x-api-key') || OPENAI_KEY) {
    const apiKey = request.headers.get('x-api-key') || OPENAI_KEY
    try {
      const response = await fetchOpenAI(payload, apiKey)
      if (response.ok) {
        return await response.text()
      }
      const body = await response.text()
      errors.push(`OpenAI failed ${response.status}: ${body}`)
    } catch (err) {
      errors.push(`OpenAI error: ${err.message}`)
    }
  }

  if (CF_AI_KEY) {
    try {
      const response = await fetchCloudflareAI(messages, payload)
      if (response.ok) {
        const json = await response.json()
        if (json?.result?.output?.[0]?.content) {
          return json.result.output[0].content
        }
        if (json?.result?.output) {
          return JSON.stringify(json.result.output)
        }
        return JSON.stringify(json)
      }
      const body = await response.text()
      errors.push(`Cloudflare AI failed ${response.status}: ${body}`)
    } catch (err) {
      errors.push(`Cloudflare AI error: ${err.message}`)
    }
  }

  try {
    const response = await fetchOpenRouter(payload)
    return await parseModelResponse(response)
  } catch (err) {
    errors.push(`OpenRouter failed: ${err.message}`)
  }

  throw new Error(errors.join(' | '))
}

async function handleRequest(request) {
  if (request.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  let payload
  try {
    payload = await request.json()
  } catch (err) {
    return jsonResponse({ error: 'Invalid JSON payload', detail: err.message }, 400)
  }

  try {
    const text = await routeWithFallback(request, payload)
    return new Response(text, { status: 200, headers: { 'Content-Type': 'text/plain' } })
  } catch (err) {
    return jsonResponse({ error: 'All providers failed', detail: err.message }, 502)
  }
}
