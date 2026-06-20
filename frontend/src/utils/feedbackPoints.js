function cleanPoint(text) {
  let cleaned = String(text).replace(/\\n/g, '\n').trim();
  cleaned = cleaned.replace(/^\d+\.?\s*/, '');
  const noteIndex = cleaned.search(/Note:/i);
  if (noteIndex > 0) {
    cleaned = cleaned.slice(0, noteIndex).trim();
  }
  return cleaned.replace(/\s+/g, ' ').trim();
}

function splitNumberedText(text) {
  const normalized = String(text).replace(/\\n/g, '\n').trim();
  if (!normalized) return [];

  const numbered = normalized
    .split(/\d+\.\s*/)
    .map(cleanPoint)
    .filter((point) => point && !/^\d+$/.test(point));

  if (numbered.length > 1) {
    return numbered;
  }

  const lines = normalized
    .split(/\n+/)
    .map((line) => cleanPoint(line.replace(/^[-•*]\s*/, '')))
    .filter(Boolean);

  if (lines.length > 1) {
    return lines;
  }

  const cleaned = cleanPoint(normalized);
  return cleaned ? [cleaned] : [];
}

export function parseFeedbackPoints(value) {
  if (value == null || value === '') return [];

  const items = Array.isArray(value) ? value : [value];
  const points = [];

  for (const item of items) {
    if (item == null) continue;

    if (Array.isArray(item)) {
      points.push(...parseFeedbackPoints(item));
      continue;
    }

    const text = String(item).trim();
    if (!text) continue;

    if (text.startsWith('[')) {
      try {
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed)) {
          points.push(...parseFeedbackPoints(parsed));
          continue;
        }
      } catch {
        // fall through to text parsing
      }
    }

    points.push(...splitNumberedText(text));
  }

  return points.filter(Boolean);
}
