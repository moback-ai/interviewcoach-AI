export const INTERVIEWER_IMAGES = {
  heroine: '/assets/interview/interviewer_heroine.png',
  hero: '/assets/interview/interviewer_hero.png',
  default: '/assets/interview/interviewer_1.png',
};

export const INTERVIEWER_VOICE_PRESETS = [
  {
    id: 'server_default',
    label: 'Classic',
    subtitle: 'Fastest fallback',
    personaName: 'Sadhan',
    role: 'Balanced interviewer',
    voiceType: 'Server voice',
    mode: 'server',
    rate: 1,
    pitch: 1,
    accentColor: '#5B8CFF',
    imageUrl: INTERVIEWER_IMAGES.default,
    interviewerGender: 'neutral',
  },
  {
    id: 'ava',
    label: 'Ava',
    subtitle: 'Warm and calm',
    personaName: 'Ava',
    role: 'Warm interviewer',
    voiceType: 'Female browser voice',
    mode: 'browser',
    rate: 0.96,
    pitch: 1.18,
    accentColor: '#6AA6FF',
    imageUrl: INTERVIEWER_IMAGES.heroine,
    interviewerGender: 'female',
  },
  {
    id: 'noah',
    label: 'Noah',
    subtitle: 'Clear and direct',
    personaName: 'Noah',
    role: 'Technical interviewer',
    voiceType: 'Male browser voice',
    mode: 'browser',
    rate: 0.92,
    pitch: 0.88,
    accentColor: '#7C8BFF',
    imageUrl: INTERVIEWER_IMAGES.hero,
    interviewerGender: 'male',
  },
  {
    id: 'mira',
    label: 'Mira',
    subtitle: 'Bright and energetic',
    personaName: 'Mira',
    role: 'Friendly interviewer',
    voiceType: 'Female browser voice',
    mode: 'browser',
    rate: 1.02,
    pitch: 1.28,
    accentColor: '#67C5E8',
    imageUrl: INTERVIEWER_IMAGES.heroine,
    interviewerGender: 'female',
  },
];

const FEMALE_HINTS = [
  'female',
  'woman',
  'ava',
  'aria',
  'samantha',
  'victoria',
  'karen',
  'zira',
  'susan',
  'serena',
  'mira',
];

const MALE_HINTS = [
  'male',
  'man',
  'noah',
  'daniel',
  'david',
  'alex',
  'fred',
  'jorge',
  'tom',
  'aaron',
];

const VOICE_PRESET_STORAGE_KEY = 'interviewcoach.voicePreset';
const VOICE_PRESET_MANUAL_KEY = 'interviewcoach.voicePresetManual';

function scoreVoice(voice, presetId) {
  const name = `${voice.name} ${voice.lang}`.toLowerCase();
  const isEnglish = name.includes('en');
  let score = isEnglish ? 10 : 0;

  if (presetId === 'ava' || presetId === 'mira') {
    if (FEMALE_HINTS.some((hint) => name.includes(hint))) score += 8;
    if (presetId === 'mira' && (name.includes('google') || name.includes('natural'))) score += 3;
  }

  if (presetId === 'noah') {
    if (MALE_HINTS.some((hint) => name.includes(hint))) score += 8;
    if (name.includes('english')) score += 2;
  }

  if (voice.default) score += 2;

  return score;
}

export function normalizeUserGender(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'male' || normalized === 'm') return 'male';
  if (normalized === 'female' || normalized === 'f') return 'female';
  if (normalized === 'other') return 'other';
  return '';
}

/** Male candidate → female interviewer; female candidate → male interviewer. */
export function getDefaultVoicePresetForGender(userGender) {
  const gender = normalizeUserGender(userGender);
  if (gender === 'male') return 'mira';
  if (gender === 'female') return 'noah';
  return 'ava';
}

export function getInterviewerImageForGender(userGender) {
  const gender = normalizeUserGender(userGender);
  if (gender === 'male') return INTERVIEWER_IMAGES.heroine;
  if (gender === 'female') return INTERVIEWER_IMAGES.hero;
  return INTERVIEWER_IMAGES.default;
}

export function resolveInterviewerImageUrl(activePreset, userGender) {
  const genderImage = getInterviewerImageForGender(userGender);
  if (normalizeUserGender(userGender)) {
    return genderImage;
  }
  return activePreset?.imageUrl || INTERVIEWER_IMAGES.default;
}

export function getStoredVoicePresetId(userGender) {
  if (typeof window === 'undefined') {
    return getDefaultVoicePresetForGender(userGender);
  }
  const manual = window.localStorage.getItem(VOICE_PRESET_MANUAL_KEY) === '1';
  const stored = window.localStorage.getItem(VOICE_PRESET_STORAGE_KEY);
  if (manual && stored) {
    return stored;
  }
  return getDefaultVoicePresetForGender(userGender);
}

export function persistVoicePresetChoice(presetId, { manual = true } = {}) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(VOICE_PRESET_STORAGE_KEY, presetId);
  if (manual) {
    window.localStorage.setItem(VOICE_PRESET_MANUAL_KEY, '1');
  }
}

export function getInterviewerVoicePreset(presetId) {
  return INTERVIEWER_VOICE_PRESETS.find((preset) => preset.id === presetId) || INTERVIEWER_VOICE_PRESETS[0];
}

export function canUseBrowserSpeech() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && typeof window.SpeechSynthesisUtterance !== 'undefined';
}

export function chooseBrowserVoice(voices, presetId) {
  if (!Array.isArray(voices) || voices.length === 0) return null;

  const scoredVoices = [...voices]
    .map((voice) => ({ voice, score: scoreVoice(voice, presetId) }))
    .sort((a, b) => b.score - a.score);

  return scoredVoices[0]?.voice || voices[0];
}
