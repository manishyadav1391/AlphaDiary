/** Console tradebook import (FR-IMP). */

/**
 * Mirrors `importer.MAX_BYTES` (services/importer.py). The server stays
 * authoritative and still answers 413; this only spares the owner a 20 MB
 * upload that was never going to land. Move the two together.
 */
export const MAX_IMPORT_BYTES = 20 * 1024 * 1024;

/** The server's own sentence, so client and server never contradict. */
export const TOO_LARGE = "That file is over 20 MB. Export a shorter date range.";

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
