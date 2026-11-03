import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { robots, type Episode, type Recording } from "./replay";
const dir = new URL("../public/data/", import.meta.url);
const json = (name: string) =>
  JSON.parse(readFileSync(new URL(name, dir), "utf8"));
it("binds every shipped replay, mesh and metric artifact to the export manifest", () => {
  const manifest = json("manifest.json");
  for (const [file, hash] of Object.entries(manifest.files))
    expect(
      createHash("sha256")
        .update(readFileSync(new URL(file, dir)))
        .digest("hex"),
    ).toBe(hash);
});
it("retains the qualified seed hashes and the original campaign results", () => {
  const catalog: Recording[] = json("catalog.json");
  for (const robot of robots) {
    const exported = json(`${robot}-qualification.json`);
    const original = JSON.parse(
      readFileSync(
        new URL(
          `../../embodiment/qualification/${robot}.json`,
          import.meta.url,
        ),
        "utf8",
      ),
    );
    delete original.raw_artifact_root;
    expect(exported).toEqual(original);
    for (const recording of catalog) {
      const episode: Episode = json(recording.robots[robot]);
      expect(episode.sourceFiles).toEqual(
        exported.trials.find((t: { seed: number }) => t.seed === recording.seed)
          .sha256,
      );
    }
  }
});
