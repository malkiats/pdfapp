const UNITS = ["B", "KB", "MB", "GB"] as const;

/** Human-readable size using 1024 multiples, e.g. 26214400 -> "25 MB". */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const rounded = value >= 10 || unit === 0 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded} ${UNITS[unit]}`;
}

export const MB = 1024 * 1024;

/** Local wall-clock time for an RFC 3339 timestamp, e.g. "14:05". Empty string if invalid. */
export function formatClockTime(iso: string, locale?: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(date);
}

/** Friendly labels for MIME types used in the catalog, e.g. for "Accepts: PDF, JPG". */
export const MIME_LABELS: Record<string, string> = {
  "application/pdf": "PDF",
  "image/jpeg": "JPG",
  "image/png": "PNG",
  "image/webp": "WEBP",
  "image/tiff": "TIFF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
  "text/html": "HTML",
  "text/plain": "TXT",
  "text/markdown": "MD",
};

/** File extensions for each MIME type, used for the file picker and when the browser reports no type. */
export const MIME_EXTENSIONS: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/webp": [".webp"],
  "image/tiff": [".tif", ".tiff"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "text/html": [".html", ".htm"],
  "text/plain": [".txt"],
  "text/markdown": [".md", ".markdown"],
};

export function mimeLabel(mime: string): string {
  return MIME_LABELS[mime] ?? mime.split("/").pop()?.toUpperCase() ?? mime;
}

export function acceptLabel(accepts: readonly string[]): string {
  return [...new Set(accepts.map(mimeLabel))].join(", ");
}
