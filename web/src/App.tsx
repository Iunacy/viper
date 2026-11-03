import { lazy, Suspense, useEffect, useState } from "react";
import {
  advance,
  frameAt,
  load,
  loadPair,
  names,
  robots,
  type Episode,
  type Recording,
  type Robot,
} from "./replay";
const Scene = lazy(() => import("./Scene"));
const Research = lazy(() => import("./Research"));
const github = "https://github.com/Iunacy/viper";
export function Header({ route }: { route: string }) {
  return (
    <header>
      <a className="wordmark" href="/" aria-label="VIPER home">
        <svg viewBox="0 0 30 28" aria-hidden="true">
          <path d="M2 3h7l6 13L21 3h7L15 27Z" fill="currentColor" />
        </svg>
        VIPER<span className="development">IN DEVELOPMENT</span>
      </a>
      <nav aria-label="Main navigation">
        <a aria-current={route === "/lab" ? "page" : undefined} href="/lab">
          Laboratory
        </a>
        <a
          aria-current={route === "/research" ? "page" : undefined}
          href="/research"
        >
          Research
        </a>
        <a href={github} target="_blank" rel="noreferrer">
          GitHub <span aria-hidden="true">↗</span>
        </a>
      </nav>
    </header>
  );
}
export function useClock(duration: number, initial = 0, loop = false) {
  const [time, setTime] = useState(initial),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!playing) return;
    let raf = 0,
      last = performance.now();
    const tick = (now: number) => {
      const delta = (now - last) / 1000;
      last = now;
      setTime((t) => {
        const next = advance(t, delta, speed, duration);
        return loop && next >= duration ? 0 : next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    const hide = () => {
      if (document.hidden) setPlaying(false);
    };
    document.addEventListener("visibilitychange", hide);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", hide);
    };
  }, [playing, speed, duration, loop]);
  useEffect(() => {
    if (!loop && time >= duration) setPlaying(false);
  }, [time, duration, loop]);
  const toggle = () => {
    if (time >= duration) setTime(0);
    setPlaying((p) => !p);
  };
  return { time, setTime, playing, setPlaying, speed, setSpeed, toggle };
}
function useRecording(recording: Recording | undefined) {
  const [pair, setPair] = useState<Record<Robot, Episode>>(),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!recording) return;
    let ignore = false;
    setPair(undefined);
    setError("");
    loadPair(recording)
      .then((result) => {
        if (!ignore) setPair(result);
      })
      .catch((e) => {
        if (!ignore) setError(String(e.message));
      });
    return () => {
      ignore = true;
    };
  }, [recording, retry]);
  return { pair, error, retry: () => setRetry((r) => r + 1) };
}
function Loading({ error, retry }: { error?: string; retry?: () => void }) {
  return (
    <div className="loading" role={error ? "alert" : "status"}>
      {error || "Opening the recording…"}
      {error ? <button onClick={retry}>Retry</button> : null}
    </div>
  );
}
function Home({ catalog }: { catalog: Recording[] }) {
  const { pair, error, retry } = useRecording(catalog[0]);
  const [robot, setRobot] = useState<Robot>("franka_panda");
  const clock = useClock(catalog[0].duration, 8, true);
  useEffect(() => {
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches)
      clock.setPlaying(true);
  }, [clock.setPlaying]);
  return (
    <main className="home">
      <div className="hero-visual">
        {pair ? (
          <Suspense fallback={<Loading />}>
            <Scene
              episode={pair[robot]}
              time={clock.time}
              trajectory={false}
              reset={0}
              hero
            />
          </Suspense>
        ) : (
          <Loading error={error} retry={retry} />
        )}
      </div>
      <div className="hero-topline">
        <span>ROBOTICS / MOTION / EMBODIMENT</span>
        <span className="record-dot">RECORDED EXECUTION</span>
      </div>
      <div className="hero-copy">
        <h1>
          FROM INTENT
          <br /> TO <span>MOTION.</span>
        </h1>
        <p>
          Different bodies. One task.
          <br /> Explore how robot arms turn bounded feedback into purposeful
          manipulation.
        </p>
        <a className="primary" href="/lab">
          ENTER LAB <span aria-hidden="true">↗</span>
        </a>
        <a className="text-link" href="/research">
          Explore the research <span aria-hidden="true">→</span>
        </a>
      </div>
      <div className="hero-caption">
        <div>
          <span className="mono">
            {robot === "franka_panda" ? "07" : "04"} ARM DOF
          </span>
          <strong>{names[robot]}</strong>
          <span>Pick & place · red target · seed 0</span>
        </div>
        <div className="hero-switch" aria-label="Featured robot">
          {robots.map((r) => (
            <button
              key={r}
              aria-pressed={r === robot}
              onClick={() => setRobot(r)}
            >
              {r === "franka_panda" ? "PANDA" : "OMX"}
            </button>
          ))}
          <button
            aria-label={
              clock.playing ? "Pause hero recording" : "Play hero recording"
            }
            onClick={clock.toggle}
          >
            {clock.playing ? "Pause" : "Play"}
          </button>
        </div>
      </div>
      <footer className="home-footer">
        <span>PhysX recording / reconstructed with pinned robot geometry</span>
        <span>
          CLASSICAL CONTROL <span className="footer-separator">/</span>{" "}
          HISTORICAL EVIDENCE{" "}
          <a href="/research#qualification" aria-label="Recording provenance">
            ↗
          </a>
        </span>
      </footer>
    </main>
  );
}
function TrackingChart({ episode, time }: { episode: Episode; time: number }) {
  const valid = episode.frames.filter((f) => f.error !== null);
  const max = Math.max(0.001, ...valid.map((f) => f.error!));
  const points = valid
    .filter((_, i) => i % 3 === 0)
    .map(
      (f) => `${(f.t / episode.duration) * 280},${76 - (f.error! / max) * 65}`,
    )
    .join(" ");
  return (
    <div className="chart">
      <svg
        viewBox="0 0 280 95"
        role="img"
        aria-label={`One-step Cartesian tracking error, full recording. Scale 0 to ${(max * 1000).toFixed(1)} millimeters.`}
      >
        <path d="M0 76H280M0 10H280" className="chart-grid" />
        <polyline points={points} fill="none" className="chart-line" />
        <path
          d={`M${Math.min(1, time / episode.duration) * 280} 0v80`}
          className="chart-cursor"
        />
        <text x="0" y="92">
          0 s
        </text>
        <text x="235" y="92">
          {episode.duration.toFixed(1)} s
        </text>
      </svg>
      <span className="chart-scale">0–{(max * 1000).toFixed(1)} mm</span>
    </div>
  );
}
function Inspector({
  episode,
  time,
  tab,
  setTab,
}: {
  episode: Episode;
  time: number;
  tab: string;
  setTab: (tab: string) => void;
}) {
  const f = frameAt(episode.frames, time);
  return (
    <aside className="inspector">
      <div className="tabs" role="tablist" aria-label="Inspector view">
        {["Telemetry", "Provenance"].map((t) => (
          <button
            key={t}
            role="tab"
            id={`tab-${t}`}
            aria-selected={tab === t}
            aria-controls="inspector-content"
            tabIndex={tab === t ? 0 : -1}
            onKeyDown={(event) => {
              if (
                !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
              )
                return;
              event.preventDefault();
              const next =
                event.key === "Home"
                  ? "Telemetry"
                  : event.key === "End"
                    ? "Provenance"
                    : t === "Telemetry"
                      ? "Provenance"
                      : "Telemetry";
              setTab(next);
              document.getElementById(`tab-${next}`)?.focus();
            }}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <div
        className="inspector-content"
        id="inspector-content"
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
      >
        {tab === "Telemetry" ? (
          <>
            <div className="section-label">
              END EFFECTOR <span>WORLD / m</span>
            </div>
            <div className="coordinates">
              {["X", "Y", "Z"].map((axis, i) => (
                <div key={axis}>
                  <span>{axis}</span>
                  <strong>{f.ee[i].toFixed(4)}</strong>
                </div>
              ))}
            </div>
            <div className="section-label">
              TRACKING ERROR <span>ONE STEP / mm</span>
            </div>
            <div className="current-error">
              {f.error === null ? "—" : (f.error * 1000).toFixed(3)}
              <span>mm</span>
            </div>
            <TrackingChart episode={episode} time={time} />
            <p className="fine-print">
              Next recorded end effector versus current position plus commanded
              delta. Terminal error is unavailable.
            </p>
            <div className="section-label">
              JOINT STATE <span>rad / rad·s⁻¹</span>
            </div>
            <table className="joints">
              <thead>
                <tr>
                  <th>Joint</th>
                  <th>Position</th>
                  <th>Velocity</th>
                </tr>
              </thead>
              <tbody>
                {episode.jointNames.map((joint, i) => (
                  <tr key={joint}>
                    <th title={joint}>
                      {joint.replace("panda_", "").replace("gripper_", "")}
                    </th>
                    <td>{f.joints[i].toFixed(4)}</td>
                    <td>{f.velocity[i].toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <>
            <div className="section-label">RECORDING IDENTITY</div>
            <dl>
              <dt>Controller</dt>
              <dd>Classical only</dd>
              <dt>Physics</dt>
              <dd>Isaac Sim 5.1.0 / PhysX</dd>
              <dt>Source revision</dt>
              <dd>
                <a href={`${github}/tree/${episode.revision}`}>
                  {episode.revision}
                </a>
              </dd>
              <dt>Playback</dt>
              <dd>
                Observed states at 30 Hz. No new dynamics. Final state held
                after this arm finishes.
              </dd>
              <dt>Recorded outcome</dt>
              <dd>
                {episode.outcome.success
                  ? "Successful placement"
                  : `Failed: ${episode.outcome.failure_reason}`}
              </dd>
            </dl>
            <div className="section-label">ORIGINAL ARTIFACT SHA-256</div>
            {Object.entries(episode.sourceFiles).map(([file, hash]) => (
              <div className="hash" key={file}>
                <span>{file}</span>
                <code>{hash}</code>
              </div>
            ))}
            <a
              className="text-link"
              href={`/data/${episode.robot}-qualification.json`}
              target="_blank"
              rel="noreferrer"
            >
              Qualification artifact ↗
            </a>
            <p className="fine-print">
              The two robots were qualified at different revisions. This is
              synchronized historical replay, not a matched current-revision or
              learned-transfer result.
            </p>
          </>
        )}
      </div>
    </aside>
  );
}
function Lab({ catalog }: { catalog: Recording[] }) {
  const [selection, setSelection] = useState(0),
    [robot, setRobot] = useState<Robot>("franka_panda"),
    [compare, setCompare] = useState(false),
    [overlay, setOverlay] = useState(true),
    [panel, setPanel] = useState(() => window.innerWidth > 700),
    [reset, setReset] = useState(0),
    [tab, setTab] = useState("Telemetry");
  const recording = catalog[selection];
  const { pair, error, retry } = useRecording(recording);
  const clock = useClock(recording.duration);
  useEffect(() => {
    clock.setPlaying(false);
    clock.setTime(0);
  }, [selection, clock.setPlaying, clock.setTime]);
  const shown = compare ? robots : [robot];
  return (
    <main className="lab">
      <div className="lab-toolbar">
        <div className="experiment-select">
          <label htmlFor="recording">RECORDING</label>
          <select
            id="recording"
            value={selection}
            onChange={(e) => setSelection(Number(e.target.value))}
          >
            {catalog.map((item, i) => (
              <option key={item.id} value={i}>
                Pick & place / {item.target} / seed {item.seed}
              </option>
            ))}
          </select>
        </div>
        <div className="toolbar-actions">
          <label className="robot-label">
            <span className="sr-only">Inspect robot</span>
            <select
              aria-label="Inspect robot"
              value={robot}
              onChange={(e) => setRobot(e.target.value as Robot)}
            >
              {robots.map((r) => (
                <option key={r} value={r}>
                  {names[r]}
                </option>
              ))}
            </select>
          </label>
          <button aria-pressed={compare} onClick={() => setCompare((c) => !c)}>
            Compare
          </button>
          <button aria-pressed={overlay} onClick={() => setOverlay((o) => !o)}>
            Trajectory
          </button>
          <button aria-expanded={panel} onClick={() => setPanel((p) => !p)}>
            Inspector
          </button>
        </div>
      </div>
      <div className="lab-body">
        <div className={`stages ${compare ? "comparison" : ""}`}>
          {pair ? (
            shown.map((r) => {
              const ep = pair[r],
                f = frameAt(ep.frames, clock.time);
              return (
                <section
                  className="stage"
                  key={r}
                  aria-label={`${names[r]} replay`}
                >
                  <div className="stage-heading">
                    <h1>{names[r]}</h1>
                    <span className="mono">
                      {clock.time >= ep.duration
                        ? ep.outcome.success
                          ? "PLACED"
                          : "FAILED"
                        : f.phase.replaceAll("_", " ").toUpperCase()}
                    </span>
                  </div>
                  <Suspense fallback={<Loading />}>
                    <Scene
                      episode={ep}
                      time={clock.time}
                      trajectory={overlay}
                      reset={reset}
                    />
                  </Suspense>
                  <div className="stage-foot">
                    <span>{ep.instruction}</span>
                    <span>
                      {clock.time > ep.duration
                        ? "FINAL STATE HELD"
                        : "RECORDED / 30 Hz"}
                    </span>
                  </div>
                </section>
              );
            })
          ) : (
            <Loading error={error} retry={retry} />
          )}
        </div>
        {panel && pair ? (
          <Inspector
            episode={pair[robot]}
            time={clock.time}
            tab={tab}
            setTab={setTab}
          />
        ) : null}
      </div>
      <div className="transport">
        <div className="transport-top">
          <button
            className="play"
            disabled={!pair}
            onClick={clock.toggle}
            aria-label={clock.playing ? "Pause recording" : "Play recording"}
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              {clock.playing ? (
                <path d="M5 4h3v12H5zm7 0h3v12h-3z" />
              ) : (
                <path d="m6 3 11 7-11 7z" />
              )}
            </svg>
            {clock.playing ? "PAUSE" : "PLAY"}
          </button>
          <button
            aria-label="Restart recording"
            disabled={!pair}
            onClick={() => {
              clock.setPlaying(false);
              clock.setTime(0);
              setReset((r) => r + 1);
            }}
          >
            Restart
          </button>
          <span className="timecode">
            {clock.time.toFixed(2)}{" "}
            <span>/ {recording.duration.toFixed(2)} s</span>
          </span>
          <label className="speed">
            <span className="sr-only">Playback speed</span>
            <select
              aria-label="Playback speed"
              value={clock.speed}
              onChange={(e) => clock.setSpeed(Number(e.target.value))}
            >
              {[0.25, 0.5, 1, 2, 4].map((s) => (
                <option value={s} key={s}>
                  {s}×
                </option>
              ))}
            </select>
          </label>
          <span className="sync-label">
            {compare ? "SYNCED ELAPSED TIME" : "OBSERVED-STATE REPLAY"}
          </span>
        </div>
        <input
          className="timeline"
          type="range"
          aria-label="Recorded time"
          min="0"
          max={recording.duration}
          step="any"
          value={clock.time}
          disabled={!pair}
          onChange={(e) => {
            clock.setPlaying(false);
            clock.setTime(Number(e.target.value));
          }}
        />
        <div className="transport-note">
          <span>Historical classical control · separate source revisions</span>
          <a href="/research#qualification">Evidence & limitations ↗</a>
        </div>
      </div>
    </main>
  );
}
export default function App() {
  const route = window.location.pathname;
  const [catalog, setCatalog] = useState<Recording[]>(),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    load<Recording[]>("catalog.json")
      .then((c) => {
        if (!c.length) throw Error("No recordings available.");
        setCatalog(c);
      })
      .catch((e) => setError(e.message));
  }, [retry]);
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header route={route} />
      <div id="main" tabIndex={-1} className="route-content">
        {route === "/research" ? (
          <Suspense fallback={<Loading />}>
            <Research />
          </Suspense>
        ) : catalog ? (
          route === "/lab" ? (
            <Lab catalog={catalog} />
          ) : route === "/" ? (
            <Home catalog={catalog} />
          ) : (
            <main className="not-found">
              <h1>Outside the workspace.</h1>
              <a href="/">Return to VIPER</a>
            </main>
          )
        ) : (
          <Loading
            error={error}
            retry={() => {
              setError("");
              setRetry((r) => r + 1);
            }}
          />
        )}
      </div>
    </>
  );
}
