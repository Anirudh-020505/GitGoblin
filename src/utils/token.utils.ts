// src/utils/token.utils.ts

const NOISE_FILES = new Set([
  'package-lock.json',
  'yarn.lock',
  'pnpm-lock.yaml',
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
  '.mp4', '.mp3',
  '.pdf', '.zip', '.tar', '.gz',
  'dist/', 'build/', '.next/'
]);

/**
 * Checks if a filename is considered "noise" and should be skipped.
 * Still vital for Gemini to save processing time and bandwidth, even with a large context window.
 */
export const isNoiseFile = (filename: string): boolean => {
  if (NOISE_FILES.has(filename.toLowerCase())) return true;

  const extension = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  if (NOISE_FILES.has(extension)) return true;

  if (filename.includes('dist/') || filename.includes('build/')) return true;

  return false;
};

/**
 * A fast, synchronous heuristic to estimate tokens.
 * Gemini 1.5 Flash has a 1 Million token context window, so this is mostly
 * used for logging and internal analytics rather than strict rate-limiting.
 * * Note: Gemini has a specific `model.countTokens()` async method, but using a fast 
 * synchronous math check (length / 4) keeps the Express event loop completely unblocked.
 */
export const estimateTokens = (text: string): number => {
  // 1 token ≈ 4 characters of code/text
  return Math.ceil(text.length / 4);
};