import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import {
  load,
  advance,
  frameAt,
  robots,
  type Episode,
  type Recording,
} from "./replay";
const catalog: Recording[] = JSON.parse(
  readFileSync(new URL("../public/data/catalog.json", import.meta.url), "utf8"),
);
const read = (file: string): Episode =>
  JSON.parse(
    readFileSync(new URL(`../public/data/${file}`, import.meta.url), "utf8"),
  );
describe("deterministic recorded-state replay", () => {
  it("selects the preceding observation, with exact tick and end boundaries", () => {
    const ep = read(catalog[0].robots.franka_panda);
    expect(frameAt(ep.frames, 0)).toBe(ep.frames[0]);
    expect(frameAt(ep.frames, ep.frames[6].t)).toBe(ep.frames[6]);
    expect(frameAt(ep.frames, ep.frames[6].t - 0.001)).toBe(ep.frames[5]);
    expect(frameAt(ep.frames, 999)).toBe(ep.frames.at(-1));
    expect(() => frameAt(ep.frames, NaN)).toThrow();
  });
  it("clamps the clock at both ends and scales elapsed time", () => {
    expect(advance(2, 0.5, 4, 8)).toBe(4);
    expect(advance(7, 1, 2, 8)).toBe(8);
    expect(advance(1, -5, 1, 8)).toBe(1);
  });
  for (const recording of catalog)
    for (const robot of robots) {
      it(`${recording.id} / ${robot}: keeps all states finite and source identity complete`, () => {
        const ep = read(recording.robots[robot]);
        expect(ep.robot).toBe(robot);
        expect(ep.frames.at(-1)!.t).toBe(ep.duration);
        expect(recording.duration).toBeGreaterThanOrEqual(ep.duration);
        expect(ep.revision).toMatch(/^[a-f0-9]{40}$/);
        expect(Object.keys(ep.sourceFiles)).toHaveLength(4);
        Object.values(ep.sourceFiles).forEach((h) =>
          expect(h).toMatch(/^[a-f0-9]{64}$/),
        );
        ep.frames.forEach((f, i) => {
          expect(f.t).toBeCloseTo(i / 30, 6);
          expect(f.joints).toHaveLength(ep.jointNames.length);
          expect(f.velocity).toHaveLength(ep.jointNames.length);
          expect(f.ee).toHaveLength(3);
          for (const p of f.poses) {
            expect(p).toHaveLength(7);
            p.forEach((n) => expect(Number.isFinite(n)).toBe(true));
            expect(Math.hypot(...p.slice(3))).toBeCloseTo(1, 5);
          }
        });
        expect(ep.frames.at(-1)!.error).toBeNull();
        expect(ep.outcome.success).toBe(true);
      });
    }
  it("holds each arm at its own last observation under the shared clock", () => {
    for (const item of catalog)
      for (const robot of robots) {
        const ep = read(item.robots[robot]);
        expect(frameAt(ep.frames, item.duration)).toBe(ep.frames.at(-1));
      }
  });
});

it("allows a failed recording fetch to be retried", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce({ ok: false, status: 503 })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ ready: true }) });
  vi.stubGlobal("fetch", fetcher);
  try {
    await expect(load("retry-test.json")).rejects.toThrow("503");
    await expect(load("retry-test.json")).resolves.toEqual({ ready: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  } finally {
    vi.unstubAllGlobals();
  }
});
