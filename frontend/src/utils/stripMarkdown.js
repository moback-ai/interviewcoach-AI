/**
 * Strip common markdown so chat UI stays plain.
 * Mirrors backend sanitize_interviewer_display_text for older DB rows.
 */
export function stripMarkdownForDisplay(text) {
  let content = String(text ?? '');
  if (!content) return '';

  content = content.replace(/```[\w+-]*\n?([\s\S]*?)```/g, '$1');
  for (let i = 0; i < 3; i += 1) {
    const updated = content
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/__([^_]+)__/g, '$1')
      .replace(/\*([^*\n]+)\*/g, '$1')
      .replace(/_([^_\n]+)_/g, '$1');
    if (updated === content) break;
    content = updated;
  }
  content = content.replace(/`([^`]+)`/g, '$1');
  content = content.replace(/^#{1,6}\s*/gm, '');
  content = content.replace(/\*\*/g, '').replace(/__/g, '');
  content = content.replace(/[ \t]{2,}/g, ' ');
  return content.trim();
}
