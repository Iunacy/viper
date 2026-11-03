// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Episode } from "./replay";
vi.mock("three", async (original) => ({
  ...(await original<typeof import("three")>()),
  WebGLRenderer: class {
    constructor() {
      throw new Error("WebGL unavailable");
    }
  },
}));
import Scene from "./Scene";
afterEach(cleanup);
it("explains unavailable graphics and disables camera actions without hiding the recording workspace", () => {
  const episode: Episode = JSON.parse(
    readFileSync(`${process.cwd()}/public/data/franka_panda-0.json`, "utf8"),
  );
  render(<Scene episode={episode} time={0} trajectory={true} reset={0} />);
  expect(screen.getByRole("alert").textContent).toContain(
    "Recorded telemetry and playback remain available",
  );
  for (const button of screen.getAllByRole("button"))
    expect((button as HTMLButtonElement).disabled).toBe(true);
});
