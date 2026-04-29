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
