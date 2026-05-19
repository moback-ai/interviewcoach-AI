/** User-facing copy when a PDF is empty or unreadable by PyPDF2 (legacy error text). */
export const EMPTY_UPLOAD_READABLE_MESSAGE =
  'The uploaded resume appears to be empty or missing enough relevant information. Please upload a valid resume.';

export function mapEmptyUploadFileError(message) {
  if (typeof message !== 'string') return message;
  return /cannot read an empty file/i.test(message) ? EMPTY_UPLOAD_READABLE_MESSAGE : message;
}
