import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { frameAt, names, type Episode } from "./replay";

interface Props {
  episode: Episode;
  time: number;
  trajectory: boolean;
  reset: number;
  hero?: boolean;
}
export default function Scene({
  episode,
  time,
  trajectory,
  reset,
  hero = false,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const latest = useRef({ time, trajectory });
  latest.current = { time, trajectory };
  const resetCamera = useRef<() => void>(() => {});
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    resetCamera.current();
  }, [reset]);
  useEffect(() => {
    const el = host.current!;
    resetCamera.current = () => {};
    let dead = false;
    let raf = 0;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "low-power",
      });
    } catch {
      setError(
        "3D is unavailable on this device. Recorded telemetry and playback remain available.",
      );
      return;
    }
    setReady(false);
    setError("");
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.setClearColor(0x101214, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.4;
    el.appendChild(renderer.domElement);
    renderer.domElement.setAttribute(
      "aria-label",
      `${names[episode.robot]} recorded-state 3D viewer. Drag to orbit, scroll to zoom. Use camera buttons for keyboard control.`,
    );
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1, 0.005, 30);
    camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.09;
    controls.minDistance = 0.18;
    controls.maxDistance = 3;
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.enablePan = true;
    const panda = episode.robot === "franka_panda";
    const resetView = () => {
      camera.position.set(
        panda ? 0.88 : 0.56,
        panda ? -1.12 : -0.58,
        panda ? 0.85 : 0.4,
      );
      controls.target.set(panda ? -0.05 : 0.13, 0.035, panda ? 0.3 : 0.1);
      controls.update();
    };
    resetView();
    resetCamera.current = resetView;
    scene.add(new THREE.HemisphereLight(0xe2f0ff, 0x343638, 3));
    const key = new THREE.DirectionalLight(0xffffff, 4);
    key.position.set(0.5, -1, 2);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x92c9ed, 2);
    rim.position.set(-1, 0.8, 1);
    scene.add(rim);
    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(1.8, 96),
      new THREE.MeshStandardMaterial({
        color: 0x171b1e,
        roughness: 0.82,
        metalness: 0.3,
      }),
    );
    ground.position.z = -0.002;
    scene.add(ground);
    const grid = new THREE.GridHelper(2, 40, 0x323a40, 0x22282d);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.001;
    scene.add(grid);
    const trailGeometry = new THREE.BufferGeometry().setFromPoints(
      episode.frames.map(
        (f) => new THREE.Vector3(...(f.ee as [number, number, number])),
      ),
    );
    const trail = new THREE.Line(
      trailGeometry,
      new THREE.LineBasicMaterial({
        color: 0xa5d9fa,
        transparent: true,
        opacity: 0.7,
      }),
    );
    scene.add(trail);
    const target = new THREE.Mesh(
      new THREE.SphereGeometry(0.003, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0xf0c87d }),
    );
    scene.add(target);
    let model: THREE.Group | undefined;
    let bodies: THREE.Object3D[] = [];
    const dispose = (object: THREE.Object3D) =>
      object.traverse((node) => {
        if (node instanceof THREE.Mesh || node instanceof THREE.Line) {
          node.geometry.dispose();
          const materials = Array.isArray(node.material)
            ? node.material
            : [node.material];
          materials.forEach((m) => m.dispose());
        }
      });
    new GLTFLoader().load(
      `/data/${episode.robot}.glb`,
      (gltf) => {
        if (dead) {
          dispose(gltf.scene);
          return;
        }
        model = gltf.scene;
        scene.add(model);
        bodies = episode.frames[0].poses.map((_, i) =>
          model!.getObjectByName(`body-${i}`)!,
        );
        setReady(true);
      },
      undefined,
      () => {
        if (!dead)
          setError(
            "Robot geometry could not load. Telemetry is still available. Reload to retry.",
          );
      },
    );
    const resize = () => {
      const { width, height } = el.getBoundingClientRect();
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(1, height);
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    resize();
    const lost = (event: Event) => {
      event.preventDefault();
      setError(
        "Graphics context interrupted. Reload to restore 3D; telemetry is still available.",
      );
    };
    renderer.domElement.addEventListener("webglcontextlost", lost);
    const draw = () => {
      const { time: t, trajectory: visible } = latest.current;
      const f = frameAt(episode.frames, t);
      bodies.forEach((body, i) => {
        if (!body) return;
        const p = f.poses[i];
        body.position.set(p[0], p[1], p[2]);
        body.quaternion.set(p[4], p[5], p[6], p[3]);
      });
      trail.visible = visible;
      target.visible = visible;
      target.position.set(...(f.target as [number, number, number]));
      trailGeometry.setDrawRange(0, episode.frames.indexOf(f) + 1);
      if (!document.hidden) {
        controls.update();
        renderer.render(scene, camera);
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    const turn = (event: Event) => {
      const direction = (event as CustomEvent<string>).detail;
      if (direction === "in" || direction === "out") {
        camera.position
          .sub(controls.target)
          .multiplyScalar(direction === "in" ? 0.85 : 1.18)
          .add(controls.target);
      } else {
        const offset = camera.position.clone().sub(controls.target);
        offset.applyAxisAngle(
          new THREE.Vector3(0, 0, 1),
          direction === "left" ? 0.18 : -0.18,
        );
        camera.position.copy(controls.target).add(offset);
      }
      controls.update();
    };
    el.addEventListener("camera", turn);
    return () => {
      dead = true;
      resetCamera.current = () => {};
      cancelAnimationFrame(raf);
      observer.disconnect();
      controls.dispose();
      dispose(scene);
      renderer.dispose();
      renderer.domElement.remove();
      el.removeEventListener("camera", turn);
    };
  }, [episode, hero]);
  return (
    <div className={`scene ${hero ? "hero-scene" : ""}`} ref={host}>
      {!ready && !error ? (
        <div className="scene-status" role="status">
          Loading robot geometry…
        </div>
      ) : null}
      {error ? (
        <div className="scene-status" role="alert">
          {error}
        </div>
      ) : null}
      {!hero ? (
        <div className="camera-controls" aria-label="Camera controls">
          {[
            ["left", "Orbit left"],
            ["right", "Orbit right"],
            ["in", "Zoom in"],
            ["out", "Zoom out"],
          ].map(([id, label]) => (
            <button
              key={id}
              disabled={!ready || Boolean(error)}
              title={label}
              aria-label={label}
              onClick={() =>
                host.current?.dispatchEvent(
                  new CustomEvent("camera", { detail: id }),
                )
              }
            >
              {id === "left"
                ? "←"
                : id === "right"
                  ? "→"
                  : id === "in"
                    ? "+"
                    : "−"}
            </button>
          ))}
          <button
            disabled={!ready || Boolean(error)}
            onClick={() => resetCamera.current()}
          >
            Reset view
          </button>
        </div>
      ) : null}
    </div>
  );
}
