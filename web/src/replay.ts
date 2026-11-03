export const robots = ["openmanipulator_x", "franka_panda"] as const;
export type Robot = (typeof robots)[number];
export const names: Record<Robot, string> = {
  openmanipulator_x: "OpenMANIPULATOR-X",
  franka_panda: "Franka Panda",
};
export interface Frame {
  t: number;
  phase: string;
  joints: number[];
  velocity: number[];
  ee: number[];
  target: number[];
  error: number | null;
  poses: number[][];
}
export interface Episode {
  robot: Robot;
  duration: number;
  frames: Frame[];
  revision: string;
  instruction: string;
  jointNames: string[];
  outcome: { success: boolean; failure_reason: string | null };
  sourceFiles: Record<string, string>;
}
export interface Recording {
  id: string;
  seed: number;
  target: string;
  duration: number;
  robots: Record<Robot, string>;
}
export interface Qualification {
  statistics: {
    trials: number;
    successes: number;
    wrong_color_picks: number;
    wilson_95: number[];
  };
  relic_commit: string;
  runtime_pin: { isaacsim: string };
}
export interface Aggregate {
  episodes: number;
  successes: number;
  joint_rmse_rad: { mean: number; ci95: number[] };
  final_cartesian_m: { mean: number; ci95: number[] };
}
export interface Comparison {
  methods: Record<string, { groups: Record<string, Aggregate> }>;
}
export interface Robustness {
  groups: Record<string, Aggregate>;
}
export function frameAt(frames: Frame[], time: number): Frame {
  if (!frames.length || !Number.isFinite(time))
    throw new Error("Invalid replay time or empty recording");
  let low = 0,
    high = frames.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (frames[mid].t <= time + 1e-8) low = mid + 1;
    else high = mid;
  }
  return frames[Math.max(0, low - 1)];
}
export function advance(
  time: number,
  delta: number,
  speed: number,
  duration: number,
) {
  return Math.max(0, Math.min(duration, time + Math.max(0, delta) * speed));
}
const cache = new Map<string, Promise<unknown>>();
export function load<T>(file: string): Promise<T> {
  if (!cache.has(file))
    cache.set(
      file,
      fetch(`/data/${file}`)
        .then((r) => {
          if (!r.ok)
            throw new Error(`Recording could not be loaded (${r.status}).`);
          return r.json();
        })
        .catch((e) => {
          cache.delete(file);
          throw e;
        }),
    );
  return cache.get(file) as Promise<T>;
}
export async function loadPair(
  recording: Recording,
): Promise<Record<Robot, Episode>> {
  const result = await Promise.all(
    robots.map(async (robot) => {
      const e = await load<Episode>(recording.robots[robot]);
      if (
        e.robot !== robot ||
        !e.frames?.length ||
        !Number.isFinite(e.duration) ||
        e.frames.some(
          (f, i) =>
            !Number.isFinite(f.t) || (i > 0 && f.t <= e.frames[i - 1].t),
        )
      )
        throw new Error("Invalid recording. Reload to retry.");
      return e;
    }),
  );
  return { openmanipulator_x: result[0], franka_panda: result[1] };
}
