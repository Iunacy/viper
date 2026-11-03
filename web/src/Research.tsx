import { useEffect, useState } from "react";
import {
  load,
  names,
  robots,
  type Comparison,
  type Qualification,
  type Robustness,
  type Robot,
} from "./replay";
const repo = "https://github.com/Iunacy/viper";
const evidenceRevision = "d44f2ddb2f07050fc8f1f657df9067c0097ae215";
function Source({
  path,
  children,
}: {
  path: string;
  children: React.ReactNode;
}) {
  return (
    <a
      className="source-link"
      href={`${repo}/blob/${evidenceRevision}/${path}`}
      target="_blank"
      rel="noreferrer"
    >
      {children} ↗
    </a>
  );
}
export default function Research() {
  const [data, setData] = useState<{
      qual: Record<Robot, Qualification>;
      comparison: Comparison;
      pi: Robustness;
    }>(),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    let dead = false;
    Promise.all([
      load<Qualification>("openmanipulator_x-qualification.json"),
      load<Qualification>("franka_panda-qualification.json"),
      load<Comparison>("adaptive-comparison.json"),
      load<Robustness>("adaptive-analytical_robustness.json"),
    ])
      .then(([omx, panda, comparison, pi]) => {
        if (!dead)
          setData({
            qual: { openmanipulator_x: omx, franka_panda: panda },
            comparison,
            pi,
          });
      })
      .catch((e) => {
        if (!dead) setError(e.message);
      });
    return () => {
      dead = true;
    };
  }, [retry]);
  return (
    <main className="research">
      <div className="research-intro">
        <h1>Motion, with evidence.</h1>
        <p>
          Two robot arms. An inspectable control pipeline.
          <br />A research program with its boundaries in view.
        </p>
        <a className="primary" href="/lab">
          OPEN LAB <span aria-hidden="true">↗</span>
        </a>
      </div>
      <nav className="research-index" aria-label="Research sections">
        <a href="#architecture">Architecture</a>
        <a href="#qualification">Classical results</a>
        <a href="#adaptive">Adaptive control</a>
        <a href="#roadmap">Learned policies</a>
      </nav>
      <section id="architecture">
        <div className="research-heading">
          <h2>From task to measured motion.</h2>
          <span className="status verified">VERIFIED / CLASSICAL PIPELINE</span>
        </div>
        <ol className="pipeline">
          <li>
            <span>Task</span>
            <strong>Color & destination</strong>
            <p>A shared manipulation task in a controlled scene.</p>
          </li>
          <li>
            <span>Control</span>
            <strong>Bounded Cartesian delta</strong>
            <p>World-frame movement and a gripper command.</p>
          </li>
          <li>
            <span>Execution</span>
            <strong>Embodiment adapter</strong>
            <p>Four or seven arm joints, fixed grasp orientation.</p>
          </li>
          <li>
            <span>Observation</span>
            <strong>PhysX → recording</strong>
            <p>Measured state and outcome, captured at 30 Hz.</p>
          </li>
        </ol>
        <p className="research-note">
          The web lab reconstructs observed poses with the existing MuJoCo model
          pipeline. It does not run a new physical simulation or a learned
          policy.
        </p>
        <Source path="embodiment/replay.py">Replay implementation</Source>
      </section>
      <section id="qualification">
        <div className="research-heading">
          <h2>A task shared across two bodies.</h2>
          <span className="status verified">VERIFIED / HISTORICAL</span>
        </div>
        <p>
          Classical color-directed pick & place. Original qualification
          campaigns, each at its own source revision.
        </p>
        {error ? (
          <div role="alert">
            {error}{" "}
            <button
              onClick={() => {
                setError("");
                setRetry((r) => r + 1);
              }}
            >
              Retry evidence
            </button>
          </div>
        ) : !data ? (
          <p role="status">Loading versioned results…</p>
        ) : (
          <div className="result-table">
            <table>
              <thead>
                <tr>
                  <th>Embodiment</th>
                  <th>Successful placements</th>
                  <th>Wrong-color picks</th>
                  <th>95% Wilson interval</th>
                  <th>Source revision</th>
                </tr>
              </thead>
              <tbody>
                {robots.map((robot) => {
                  const q = data.qual[robot];
                  return (
                    <tr key={robot}>
                      <th>{names[robot]}</th>
                      <td>
                        {q.statistics.successes} / {q.statistics.trials}
                      </td>
                      <td>{q.statistics.wrong_color_picks}</td>
                      <td>
                        {q.statistics.wilson_95
                          .map((n) => (n * 100).toFixed(1) + "%")
                          .join("–")}
                      </td>
                      <td>
                        <a href={`${repo}/tree/${q.relic_commit}`}>
                          {q.relic_commit.slice(0, 7)} ↗
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="research-note">
          These campaigns do not establish common-revision qualification,
          learned manipulation, or successful cross-embodiment transfer. The lab
          includes three paired seeds from the twenty-trial campaigns.
        </p>
        <div className="source-row">
          {robots.map((r) => (
            <a
              key={r}
              className="source-link"
              href={`/data/${r}-qualification.json`}
            >
              {names[r]} qualification JSON ↗
            </a>
          ))}
        </div>
      </section>
      <section id="adaptive">
        <div className="research-heading">
          <h2>Learning a correction. Testing the advantage.</h2>
          <span className="status experimental">
            EXPERIMENTAL / ADAPTIVE-v0
          </span>
        </div>
        <p>
          The native adaptive-control study measures joint tracking under
          altered physics. This is a separate study from the PhysX manipulation
          recordings above.
        </p>
        {data ? (
          <div className="adaptive-results">
            <div className="result-table">
              <table>
                <thead>
                  <tr>
                    <th>Method</th>
                    <th>Joint RMSE (rad)</th>
                    <th>95% cluster bootstrap CI</th>
                    <th>Successful conditions</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    [
                      "Conventional",
                      data.comparison.methods.conventional.groups.primary,
                    ],
                    [
                      "Shared learned correction",
                      data.comparison.methods.shared_full.groups.primary,
                    ],
                    ["Full-range PI · exploratory", data.pi.groups.primary],
                  ].map(([label, value]) => {
                    const a = value as typeof data.pi.groups.primary;
                    return (
                      <tr key={label as string}>
                        <th>{label as string}</th>
                        <td>{a.joint_rmse_rad.mean.toFixed(6)}</td>
                        <td>
                          {a.joint_rmse_rad.ci95
                            .map((n) => n.toFixed(6))
                            .join("–")}
                        </td>
                        <td>
                          {a.successes} / {a.episodes}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
        <p className="research-note">
          The analytical PI baseline has lower tracking RMSE than the shared
          learned correction. No overall learned-controller advantage is
          established. The explicit three-to-four-joint transfer probe failed;
          reverse transfer was not tested.
        </p>
        <div className="source-row">
          <Source path="adaptive/revision/RESULTS.md">
            Results & limitations
          </Source>
          <a className="source-link" href="/data/adaptive-comparison.json">
            Comparison JSON ↗
          </a>
          <a
            className="source-link"
            href="/data/adaptive-analytical_robustness.json"
          >
            PI comparison JSON ↗
          </a>
        </div>
      </section>
      <section id="roadmap">
        <div className="research-heading">
          <h2>The next question is transfer.</h2>
          <span className="status planned">PLANNED / LEARNED MANIPULATION</span>
        </div>
        <p>
          Initial qualification scope: E2 versus E3, with limited attribution.
          Real GR00T training, checkpoint recovery, inference and learned
          closed-loop evaluation still require GPU execution evidence.
        </p>
        <div className="roadmap">
          <article>
            <span className="status experimental">
              EXPERIMENTAL INFRASTRUCTURE
            </span>
            <h3>E2 / E3</h3>
            <p>
              Compare a target-only condition with a shared checkpoint condition
              under a matched target-training protocol. No successful learned
              manipulation result is claimed.
            </p>
          </article>
          <article>
            <span className="status planned">CONVERSION ONLY</span>
            <h3>E4</h3>
            <p>
              Checkpoint conversion infrastructure. It does not validate
              cross-embodiment transfer.
            </p>
          </article>
          <article>
            <span className="status planned">NOT IMPLEMENTED</span>
            <h3>E5</h3>
            <p>
              Required for future claims specifically attributing improvements
              to cross-embodiment transfer.
            </p>
          </article>
        </div>
        <Source path="docs/PRE_RENTAL_VERIFICATION.md">
          Qualification audit & execution gates
        </Source>
      </section>
      <section className="reproducibility">
        <h2>Trace the observation.</h2>
        <p>
          Each replay exposes its source revision and SHA-256 digests in the
          lab’s provenance inspector. Static assets were exported through the
          existing hash-verified replay loader. The evidence presented here is
          historical; interface changes do not requalify the robots.
        </p>
        <div className="source-row">
          <a className="source-link" href="/lab">
            Inspect a recording ↗
          </a>
          <Source path="embodiment/replay_render.py">
            Geometry & reconstruction
          </Source>
          <Source path="adaptive/revision/PROTOCOL.md">
            Adaptive protocol
          </Source>
        </div>
      </section>
      <footer className="research-footer">
        <a className="wordmark" href="/">
          VIPER
        </a>
        <span>Open research. Explicit limits.</span>
        <a href={`${repo}/blob/main/LICENSE`}>Apache-2.0 ↗</a>
      </footer>
    </main>
  );
}
