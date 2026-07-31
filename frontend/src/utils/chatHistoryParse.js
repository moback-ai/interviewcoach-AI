const KNOWN_SPEAKERS = new Set([
  'assistant',
  'interviewer',
  'bot',
  'user',
  'candidate',
  'you',
  'system',
]);

export const normalizeChatSpeaker = (speaker = '') => {
  const normalized = String(speaker).trim().toLowerCase();
  if (['assistant', 'interviewer', 'bot'].includes(normalized)) return 'interviewer';
  if (['user', 'candidate', 'you'].includes(normalized)) return 'candidate';
  if (normalized === 'system') return 'system';
  // Unknown prefixes must never become "YOU" in the UI.
  return 'system';
};

export const formatMessageTimestamp = (value) => {
  if (!value) return new Date().toLocaleTimeString();
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return new Date().toLocaleTimeString();
  return date.toLocaleTimeString();
};

/**
 * Legacy blob parser. Only lines that start with a known role + ":" start a new
 * message. Colons inside interviewer/user text stay in the message body.
 */
export const parseHistoryContent = (content) => {
  const lines = String(content || '').split('\n');
  const conversation = [];
  const roleLineRe = /^(assistant|interviewer|bot|user|candidate|you|system)\s*:(.*)$/i;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed && conversation.length === 0) continue;

    const match = trimmed.match(roleLineRe);
    if (match && KNOWN_SPEAKERS.has(match[1].toLowerCase())) {
      const speaker = normalizeChatSpeaker(match[1]);
      const message = match[2].replace(/^\s/, '');
      const previous = conversation[conversation.length - 1];
      if (previous?.speaker === speaker && previous?.message === message) {
        continue;
      }
      conversation.push({
        id: conversation.length + 1,
        speaker,
        message,
        timestamp: new Date().toLocaleTimeString(),
      });
      continue;
    }

    if (conversation.length > 0) {
      const lastMessage = conversation[conversation.length - 1];
      lastMessage.message = lastMessage.message
        ? `${lastMessage.message}\n${line}`
        : line;
    }
  }

  return conversation;
};

export const mapStructuredMessages = (messages) => {
  if (!Array.isArray(messages) || messages.length === 0) return [];
  return messages
    .map((item, index) => {
      if (!item || typeof item !== 'object') return null;
      const speaker = normalizeChatSpeaker(item.role || item.speaker || '');
      const message = item.content != null ? String(item.content) : String(item.message || '');
      if (!message && speaker === 'system') return null;
      return {
        id: item.id || index + 1,
        speaker,
        message,
        timestamp: formatMessageTimestamp(item.created_at || item.timestamp),
      };
    })
    .filter(Boolean);
};
