/** User-facing copy when resume and JD uploads are the same file. */
export const SAME_RESUME_JD_FILE_MESSAGE =
  'Please upload a resume and a job description in their respective fields. The same file cannot be used for both.';

function bufferToHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/** SHA-256 hex digest of a File/Blob's bytes. */
export async function hashFileBytes(file) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return bufferToHex(digest);
}

/**
 * True when both files are the same upload (same picker selection or identical bytes).
 * Different sizes short-circuit; matching name+size+lastModified is treated as same file.
 */
export async function filesHaveSameContent(a, b) {
  if (!a || !b) return false;
  if (a === b) return true;
  if (typeof a.size === 'number' && typeof b.size === 'number' && a.size !== b.size) {
    return false;
  }
  if (
    a.name === b.name &&
    a.size === b.size &&
    a.lastModified === b.lastModified
  ) {
    return true;
  }
  const [hashA, hashB] = await Promise.all([hashFileBytes(a), hashFileBytes(b)]);
  return hashA === hashB;
}
