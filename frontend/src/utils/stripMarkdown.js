/**
 * Removes common Markdown syntax (as produced by ChatGPT-style copy/paste)
 * so plain-text inputs don't show raw markers like **bold** or ## headings.
 */
export function stripMarkdown(text) {
  if (!text) return '';

  return String(text)
    .replace(/\r\n?/g, '\n')
    // fenced code blocks: keep the content, drop the fences
    .replace(/^```[^\n]*\n?/gm, '')
    // headings: "## Title" -> "Title"
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    // blockquotes
    .replace(/^\s{0,3}>\s?/gm, '')
    // horizontal rules
    .replace(/^\s*([-*_])(\s*\1){2,}\s*$/gm, '')
    // bullets "* item" / "+ item" -> "- item" (before italics handling)
    .replace(/^(\s*)[*+]\s+/gm, '$1- ')
    // bold / bold-italic: **text**, __text__, ***text***
    .replace(/(\*\*\*|\*\*|___|__)(?=\S)([\s\S]*?\S)\1/g, '$2')
    // italic: *text* / _text_ (only when wrapped around words, avoids "5 * 3" or snake_case)
    .replace(/(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])/g, '$1')
    .replace(/(?<![\w_])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w_])/g, '$1')
    // inline code
    .replace(/`([^`\n]+)`/g, '$1')
    // links: [label](url) -> label
    .replace(/\[([^\]]+)\]\((?:[^)\s]+)\)/g, '$1')
    // collapse 3+ blank lines
    .replace(/\n{3,}/g, '\n\n');
}

/**
 * onPaste handler factory for controlled <textarea>/<input>.
 * Cleans the pasted text and inserts it at the current selection.
 */
export function createCleanPasteHandler(getValue, setValue) {
  return (event) => {
    const pasted = event.clipboardData?.getData('text');
    if (!pasted) return;

    const cleaned = stripMarkdown(pasted);
    if (cleaned === pasted) return; // nothing to clean, let the browser paste normally

    event.preventDefault();
    const el = event.target;
    const current = getValue() || '';
    const start = el.selectionStart ?? current.length;
    const end = el.selectionEnd ?? current.length;
    const next = current.slice(0, start) + cleaned + current.slice(end);
    setValue(next);

    const caret = start + cleaned.length;
    requestAnimationFrame(() => {
      try { el.setSelectionRange(caret, caret); } catch { /* element may be gone */ }
    });
  };
}
