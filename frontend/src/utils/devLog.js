/** Log only in Vite dev builds; stripped from production bundles when unused. */
export function devLog(...args) {
  if (import.meta.env.DEV) {
    console.log(...args);
  }
}

export function devWarn(...args) {
  if (import.meta.env.DEV) {
    console.warn(...args);
  }
}
