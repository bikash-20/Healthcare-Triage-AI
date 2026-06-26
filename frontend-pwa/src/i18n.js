/**
 * Frontend bilingual translations — must stay in sync with
 * `backend-core/app/translations.py`.
 *
 * Usage:
 *   import { t, detectLanguage } from './i18n'
 *   const greeting = t('app.tagline', lang)
 */
export const TRANSLATIONS = {
  // Generic / errors
  'app.name': { en: 'Rural Health Triage', bn: 'রুরাল হেলথ ট্রায়াজ' },
  'app.tagline': {
    en: 'Community health worker dashboard for rapid intake, analytics, and clinical referral guidance powered by AI.',
    bn: 'কমিউনিটি স্বাস্থ্য কর্মীদের জন্য দ্রুত রোগী গ্রহণ, বিশ্লেষণ এবং এআই-চালিত ক্লিনিক্যাল রেফারেল সহায়তা।',
  },
  'error.required_fields': {
    en: 'Required fields are missing.',
    bn: 'প্রয়োজনীয় তথ্য অনুপস্থিত।',
  },
  'error.tts_failed': {
    en: 'Audio playback failed. Please try again.',
    bn: 'অডিও চালানো ব্যর্থ হয়েছে। আবার চেষ্টা করুন।',
  },
  'error.network': {
    en: 'Network error. Please check your connection.',
    bn: 'নেটওয়ার্ক ত্রুটি। আপনার সংযোগ পরীক্ষা করুন।',
  },
  // Vitals form
  'vitals.title': { en: 'Patient Vital Signs', bn: 'রোগীর শারীরিক লক্ষণ' },
  'vitals.subtitle': {
    en: 'Enter vitals or use lab report upload to auto-populate values.',
    bn: 'লক্ষণগুলি প্রবেশ করান অথবা ল্যাব রিপোর্ট আপলোড করে স্বয়ংক্রিয়ভাবে পূরণ করুন।',
  },
  'vitals.bp': {
    en: 'Blood Pressure (systolic/diastolic)',
    bn: 'রক্তচাপ (সিস্টোলিক/ডায়াস্টোলিক)',
  },
  'vitals.hr': { en: 'Heart Rate (bpm)', bn: 'হৃদস্পন্দন (বিপিএম)' },
  'vitals.temp': { en: 'Temperature (°F)', bn: 'তাপমাত্রা (°F)' },
  'vitals.spo2': { en: 'SpO₂ (%)', bn: 'অক্সিজেন স্যাচুরেশন (%)' },
  'vitals.glucose': {
    en: 'Blood Glucose (mg/dL)',
    bn: 'রক্তে গ্লুকোজ (মিলিগ্রাম/ডেসিলিটার)',
  },
  'vitals.submit': { en: 'Submit Vitals', bn: 'ভিটালস জমা দিন' },
  'vitals.analyzing': { en: '⏳ Analyzing vitals...', bn: '⏳ বিশ্লেষণ চলছে...' },
  'vitals.simulate_critical': {
    en: 'Simulate Critical Case',
    bn: 'গুরুতর কেস সিমুলেট করুন',
  },
  'vitals.analyzing_critical': { en: 'Analyzing...', bn: 'বিশ্লেষণ চলছে...' },
  'vitals.ocr_title': {
    en: 'Drag & drop a prescription or lab report image here, or click to upload.',
    bn: 'প্রেসক্রিপশন বা ল্যাব রিপোর্টের ছবি এখানে টেনে আনুন বা আপলোড করতে ক্লিক করুন।',
  },
  'vitals.ocr_hint': {
    en: 'Supports handwriting and printed reports.',
    bn: 'হাতে লেখা ও মুদ্রিত রিপোর্ট উভয়ই সমর্থিত।',
  },
  'vitals.ocr_status_label': { en: 'OCR Scan Status', bn: 'ওসিআর স্ক্যান অবস্থা' },
  'vitals.ocr_ready': { en: 'Ready', bn: 'প্রস্তুত' },
  'vitals.ocr_processing': { en: 'Processing…', bn: 'প্রক্রিয়াকরণ চলছে…' },
  'vitals.ocr_uploading': { en: 'Uploading image...', bn: 'ছবি আপলোড হচ্ছে...' },
  'vitals.ocr_complete': {
    en: 'OCR scan complete. Auto-filled vitals when available.',
    bn: 'ওসিআর স্ক্যান সম্পন্ন। প্রাপ্ত ভিটালস স্বয়ংক্রিয়ভাবে পূরণ করা হয়েছে।',
  },
  'vitals.ocr_failed': { en: 'OCR upload failed', bn: 'ওসিআর আপলোড ব্যর্থ হয়েছে' },
  'vitals.ocr_detected_label': { en: 'Detected text preview', bn: 'শনাক্ত করা পাঠ' },
  'vitals.ocr_extracted_labs': { en: 'Extracted Labs', bn: 'নিষ্কাশিত ল্যাব' },
  // Audio intake
  'audio.title': {
    en: 'Voice Intake (Bengali/English)',
    bn: 'ভয়েস ইনটেক (বাংলা/ইংরেজি)',
  },
  'audio.subtitle': { en: 'Record Patient Symptoms', bn: 'রোগীর লক্ষণ রেকর্ড করুন' },
  'audio.start': { en: 'Start Recording', bn: 'রেকর্ডিং শুরু করুন' },
  'audio.stop': { en: 'Stop & Upload', bn: 'থামান ও আপলোড করুন' },
  'audio.recording': { en: 'Recording...', bn: 'রেকর্ডিং চলছে...' },
  'audio.analyzing': { en: 'Analyzing...', bn: 'বিশ্লেষণ চলছে...' },
  'audio.processing': {
    en: '⏳ Analyzing symptoms and generating triage...',
    bn: '⏳ লক্ষণ বিশ্লেষণ ও ট্রায়াজ তৈরি হচ্ছে...',
  },
  'audio.idle': { en: 'Idle', bn: 'প্রস্তুত' },
  'audio.complete': { en: 'Recording complete.', bn: 'রেকর্ডিং সম্পন্ন।' },
  'audio.failed': { en: 'Audio processing failed.', bn: 'অডিও প্রক্রিয়াকরণ ব্যর্থ হয়েছে।' },
  'audio.permission_denied': {
    en: 'Microphone access denied. Please allow microphone permission.',
    bn: 'মাইক্রোফোন অ্যাক্সেস প্রত্যাখ্যাত। অনুগ্রহ করে অনুমতি দিন।',
  },
  'audio.duration': { en: 'Duration', bn: 'সময়কাল' },
  // Triage card
  'triage.title': { en: 'Triage Status', bn: 'ট্রায়াজ অবস্থা' },
  'triage.empty': {
    en: 'Submit vitals or run an audio intake to see triage results.',
    bn: 'ট্রায়াজ ফলাফল দেখতে ভিটালস জমা দিন বা ভয়েস ইনটেক চালান।',
  },
  'triage.alerts': { en: 'Alerts', bn: 'সতর্কতা' },
  'triage.urgency': { en: 'Urgency', bn: 'জরুরিত্ব' },
  'triage.recommendations': { en: 'Recommendations', bn: 'সুপারিশ' },
  'triage.severity.green': { en: 'GREEN', bn: 'সবুজ' },
  'triage.severity.yellow': { en: 'YELLOW', bn: 'হলুদ' },
  'triage.severity.red': { en: 'RED', bn: 'লাল' },
  'triage.severity.black': { en: 'BLACK', bn: 'কালো' },
  'triage.reasoning_default': {
    en: 'No critical anomalies detected.',
    bn: 'কোনো গুরুতর সমস্যা শনাক্ত হয়নি।',
  },
  'triage.differential': { en: 'Differential', bn: 'সম্ভাব্য রোগ নির্ণয়' },
  // Dose calculator
  'dose.title': { en: 'Dose Calculator', bn: 'ওষুধের ডোজ গণক' },
  'dose.subtitle': {
    en: 'Calculate safe medication dose based on patient age and weight.',
    bn: 'রোগীর বয়স ও ওজন অনুযায়ী নিরাপদ ওষুধের ডোজ গণনা।',
  },
  'dose.medication': { en: 'Medication name', bn: 'ওষুধের নাম' },
  'dose.age': { en: 'Age (years)', bn: 'বয়স (বছর)' },
  'dose.weight': { en: 'Weight (kg)', bn: 'ওজন (কেজি)' },
  'dose.calculate': {
    en: '💊 Calculate Safe Dose',
    bn: '💊 নিরাপদ ডোজ গণনা করুন',
  },
  'dose.submit': { en: 'Calculate Dose', bn: 'ডোজ গণনা করুন' },
  'dose.calculating': { en: '⏳ Calculating...', bn: '⏳ গণনা চলছে...' },
  'dose.failed': { en: 'Dose calculation failed.', bn: 'ডোজ গণনা ব্যর্থ হয়েছে।' },
  'dose.result_label': { en: 'Recommended dose', bn: 'প্রস্তাবিত ডোজ' },
  'dose.unavailable': { en: 'Not available', bn: 'পাওয়া যায়নি' },
  'dose.duration': { en: 'Duration', bn: 'সময়কাল' },
  'dose.notes': { en: 'Notes', bn: 'মন্তব্য' },
  'dose.warning': { en: 'Warning', bn: 'সতর্কতা' },
  'dose.english': { en: 'English', bn: 'English' },
  'dose.bangla': { en: 'বাংলা', bn: 'বাংলা' },
  'dose.total_dose': { en: 'Total dose', bn: 'মোট ডোজ' },
  'dose.frequency': { en: 'Frequency', bn: 'সেবনের নিয়ম' },
  'dose.route': { en: 'Route', bn: 'সেবন পদ্ধতি' },
  'dose.dose_per_kg': { en: 'Dose/kg', bn: 'ডোজ/কেজি' },
  'dose.listen': { en: '🔊 Listen', bn: '🔊 শুনুন' },
  'dose.loading': { en: '⏳ Loading...', bn: '⏳ লোড হচ্ছে...' },
  'dose.no_content': { en: 'No content to speak', bn: 'পড়ার জন্য কিছু নেই' },
  'dose.warning_banner': {
    en: '⚠️ Dangerous combination detected',
    bn: '⚠️ বিপজ্জনক সংমিশ্রণ শনাক্ত হয়েছে',
  },
  // Audio player / TTS
  'tts.listen_summary': {
    en: '🔊 Listen Clinical Summary',
    bn: '🔊 ক্লিনিক্যাল সারাংশ শুনুন',
  },
  'tts.loading': { en: '⏳ Loading...', bn: '⏳ লোড হচ্ছে...' },
  'tts.no_data': { en: 'No triage data available', bn: 'কোনো ট্রায়াজ তথ্য পাওয়া যায়নি' },
  'tts.audio_failed': { en: 'Audio failed', bn: 'অডিও ব্যর্থ হয়েছে' },
  // Chat
  'chat.title': { en: 'NEXORA Chat', bn: 'নেক্সোরা চ্যাট' },
  'chat.subtitle': {
    en: 'Context-aware medical assistant for the current patient.',
    bn: 'বর্তমান রোগীর জন্য প্রাসঙ্গিক চিকিৎসা সহায়ক।',
  },
  'chat.open': { en: 'Open NEXORA', bn: 'নেক্সোরা খুলুন' },
  'chat.close': { en: 'Close NEXORA', bn: 'নেক্সোরা বন্ধ করুন' },
  'chat.send': { en: 'Send', bn: 'পাঠান' },
  'chat.thinking': { en: 'Thinking', bn: 'ভাবছে' },
  'chat.error': { en: 'Chat failed. Please try again.', bn: 'চ্যাট ব্যর্থ হয়েছে। আবার চেষ্টা করুন।' },
  'chat.welcome': {
    en: 'Hi, I am NEXORA, your medical AI expert. How may I help you today?',
    bn: 'হাই, আমি নেক্সোরা, আপনার মেডিকেল এআই এক্সপার্ট। আজ আপনাকে কীভাবে সাহায্য করতে পারি?',
  },
  'chat.placeholder_en': {
    en: 'Ask NEXORA a clinical question...',
    bn: 'Ask NEXORA a clinical question...',
  },
  'chat.placeholder_bn': {
    en: 'আপনার প্রশ্ন লিখুন...',
    bn: 'আপনার প্রশ্ন লিখুন...',
  },
  'chat.send_en': { en: 'Ask NEXORA', bn: 'Ask NEXORA' },
  'chat.send_bn': { en: 'প্রশ্ন করুন', bn: 'প্রশ্ন করুন' },
  'chat.processing_en': { en: 'Processing...', bn: 'Processing...' },
  'chat.processing_bn': { en: 'প্রসেস হচ্ছে...', bn: 'প্রসেস হচ্ছে...' },
  'chat.toggle_show': { en: 'Hide', bn: 'লুকান' },
  'chat.toggle_hide': { en: 'Show', bn: 'দেখান' },
  'chat.patient_context': { en: 'Patient Context', bn: 'রোগীর তথ্য' },
  'chat.no_vitals': { en: 'No vitals available.', bn: 'কোনো ভিটালস নেই।' },
  'chat.no_triage': { en: 'No triage data available.', bn: 'কোনো ট্রায়াজ তথ্য নেই।' },
  'chat.you': { en: 'You', bn: 'আপনি' },
  'chat.assistant': { en: 'NEXORA', bn: 'নেক্সোরা' },
  'chat.collapsed_hint': {
    en: 'Tap show to open NEXORA chat. It will stay aware of patient vitals and triage context.',
    bn: "নেক্সোরা চ্যাট খুলতে 'দেখান' চাপুন। এটি রোগীর ভিটালস ও ট্রায়াজ প্রসঙ্গে সচেতন থাকবে।",
  },
  // Install banner
  'install.title': {
    en: 'Install Rural Health Triage',
    bn: 'রুরাল হেলথ ট্রায়াজ ইনস্টল করুন',
  },
  'install.body_ios': {
    en: 'Tap Share then Add to Home Screen for offline access.',
    bn: "অফলাইন ব্যবহারের জন্য 'শেয়ার' তারপর 'হোম স্ক্রিনে যোগ করুন' চাপুন।",
  },
  'install.body_android': {
    en: 'Install the app for instant offline access and a home screen shortcut.',
    bn: 'অফলাইন ব্যবহার ও হোম স্ক্রিন শর্টকাটের জন্য অ্যাপ ইনস্টল করুন।',
  },
  'install.body_default': {
    en: 'Get instant offline access and home screen shortcut. Install now for faster access.',
    bn: 'অফলাইন ব্যবহার ও হোম স্ক্রিন শর্টকাট পেতে এখনই ইনস্টল করুন।',
  },
  'install.later': { en: 'Later', bn: 'পরে' },
  'install.install': { en: 'Install', bn: 'ইনস্টল' },
  // Language toggle
  'lang.toggle_to_en': { en: 'English', bn: 'English' },
  'lang.toggle_to_bn': { en: 'বাংলা', bn: 'বাংলা' },
  // PDF
  'pdf.title': {
    en: 'Rural Health Summary',
    bn: 'রিলেটেড স্বাস্থ্য সারসংক্ষেপ',
  },
  'pdf.download': { en: 'Download PDF', bn: 'পিডিএফ ডাউনলোড করুন' },
  'pdf.preparing': { en: 'Preparing PDF...', bn: 'পিডিএফ তৈরি হচ্ছে...' },
  'pdf.error': { en: 'PDF generation failed', bn: 'পিডিএফ তৈরি ব্যর্থ হয়েছে' },
  // Misc
  'glass.active_nodes_title': { en: 'Active Nodes', bn: 'সক্রিয় নোড' },
  'glass.active_nodes_value': { en: '210', bn: '২১০' },
  'glass.active_nodes_desc': {
    en: 'Health worker devices reporting vitals and voice intake data.',
    bn: 'ভিটালস ও ভয়েস ইনটেক ডেটা রিপোর্ট করছে এমন স্বাস্থ্যকর্মী ডিভাইস।',
  },
}

/**
 * Look up a translation.
 * @param {string} key
 * @param {'en'|'bn'} lang
 */
export function t(key, lang = 'en') {
  const entry = TRANSLATIONS[key]
  if (!entry) return key
  return entry[lang] || entry.en || key
}

/**
 * Detect Bengali by counting characters in the U+0980–U+09FF block.
 * @param {string} text
 */
export function isBengali(text) {
  if (!text) return false
  const matches = text.match(/[\u0980-\u09FF]/g)
  return Boolean(matches && matches.length >= 3)
}

/**
 * Detect language for a piece of text. Returns 'bn' if enough Bengali, else 'en'.
 */
export function detectLanguage(text, fallback = 'en') {
  return isBengali(text) ? 'bn' : fallback
}

/**
 * Map a triage severity code to a localized label.
 */
export function localizeTriage(severity, lang = 'en') {
  if (!severity) return ''
  const key = `triage.severity.${String(severity).toLowerCase()}`
  return t(key, lang)
}

export const SUPPORTED_LANGUAGES = ['en', 'bn']
export const DEFAULT_LANGUAGE = 'en'
