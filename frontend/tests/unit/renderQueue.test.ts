import { describe, expect, it } from "vitest";
import { createRenderQueue } from "@/lib/pdf/renderQueue";

const tick = () => new Promise((r) => setTimeout(r, 0));

function deferredRunner() {
  const started: number[] = [];
  const resolvers = new Map<number, () => void>();
  const run = (key: number) =>
    new Promise<void>((resolve) => {
      started.push(key);
      resolvers.set(key, resolve);
    });
  return { started, run, finish: (key: number) => resolvers.get(key)?.() };
}

describe("createRenderQueue", () => {
  it("never runs more than `concurrency` jobs at once", async () => {
    const { started, run, finish } = deferredRunner();
    const queue = createRenderQueue(run, 2);
    [1, 2, 3, 4].forEach((k) => queue.request(k));
    await tick();
    expect(started).toEqual([1, 2]);
    finish(1);
    await tick();
    expect(started).toEqual([1, 2, 3]);
  });

  it("skips jobs cancelled before they start and de-duplicates requests", async () => {
    const { started, run, finish } = deferredRunner();
    const queue = createRenderQueue(run, 1);
    queue.request(1);
    const cancel2 = queue.request(2);
    queue.request(3);
    queue.request(3);
    cancel2();
    await tick();
    finish(1);
    await tick();
    expect(started).toEqual([1, 3]);
  });

  it("clear drops pending jobs and keeps going after a failing job", async () => {
    const started: number[] = [];
    const queue = createRenderQueue(async (k: number) => {
      started.push(k);
      if (k === 1) throw new Error("boom");
    }, 1);
    queue.request(1);
    queue.request(2);
    await tick();
    await tick();
    expect(started).toEqual([1, 2]);
    queue.request(3);
    queue.clear();
    await tick();
    expect(started).toEqual([1, 2]);
    expect(queue.pending).toBe(0);
  });
});
