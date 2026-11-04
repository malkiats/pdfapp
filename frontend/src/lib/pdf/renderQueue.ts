/**
 * A small priority-less job queue with a concurrency cap, used to render page
 * thumbnails lazily. Jobs that are cancelled before they start never run, so
 * fast scrolling through a 500-page document only renders what stays visible.
 */
export interface RenderQueue<K> {
  /** Queues `key`; returns a cancel function (no-op once the job has started). */
  request(key: K): () => void;
  /** Drops every pending job; running jobs finish but their results are ignored by the caller. */
  clear(): void;
  /** Number of jobs waiting to start. */
  readonly pending: number;
}

export function createRenderQueue<K>(run: (key: K) => Promise<void>, concurrency = 2): RenderQueue<K> {
  const waiting: K[] = [];
  const queued = new Set<K>();
  let active = 0;

  const pump = () => {
    while (active < concurrency && waiting.length > 0) {
      const key = waiting.shift()!;
      queued.delete(key);
      active += 1;
      run(key)
        .catch(() => undefined)
        .finally(() => {
          active -= 1;
          pump();
        });
    }
  };

  return {
    request(key) {
      if (!queued.has(key)) {
        queued.add(key);
        waiting.push(key);
        // Start on a microtask so a burst of requests can be cancelled before any starts.
        queueMicrotask(pump);
      }
      return () => {
        if (!queued.has(key)) return;
        queued.delete(key);
        const index = waiting.indexOf(key);
        if (index >= 0) waiting.splice(index, 1);
      };
    },
    clear() {
      waiting.length = 0;
      queued.clear();
    },
    get pending() {
      return waiting.length;
    },
  };
}
