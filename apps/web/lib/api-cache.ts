/* Tiny TTL cache with in-flight coalescing for idempotent GETs.
   Errors are never cached; concurrent reads share one request and the
   result is reused briefly across navigations (e.g. the settings page
   mounts six cards at once, the products page fires categories + settings
   + products on reload). */

interface CacheEntry<T> {
  data: T
  expires: number
}

export function createTtlCache<T>(ttlMs: number) {
  let cached: CacheEntry<T> | null = null
  let inflight: Promise<T> | null = null

  function get(fetcher: () => Promise<T>): Promise<T> {
    if (cached && cached.expires > Date.now()) {
      return Promise.resolve(cached.data)
    }
    if (!inflight) {
      inflight = fetcher()
        .then((data) => {
          cached = { data, expires: Date.now() + ttlMs }
          return data
        })
        .finally(() => {
          inflight = null
        })
    }
    return inflight
  }

  function set(data: T): void {
    cached = { data, expires: Date.now() + ttlMs }
  }

  function clear(): void {
    cached = null
  }

  return { get, set, clear }
}
