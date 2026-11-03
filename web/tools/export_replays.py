"""Export verified historical episodes and existing MuJoCo geometry; no dynamics run.
Requires the optional replay environment and original qualification campaigns.
Run from repository root with VIPER_ASSET_CACHE pointing at pinned asset cache.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MUJOCO_GL', 'egl')
import numpy as np
import trimesh
from embodiment.replay import load_qualified_pair
from embodiment.replay_render import Renderer

OUT = ROOT / 'web/public/data'
OUT.mkdir(parents=True, exist_ok=True)

def write(name, data):
    (OUT / name).write_text(json.dumps(data, separators=(',', ':'), allow_nan=False)+'\n')

def rounded(value):
    return np.round(value, 7).tolist()

catalog = []
renderers = {}
for seed in (0, 1, 2):
    pair = load_qualified_pair(seed)
    entry = {'id': f'qualification-{seed}', 'seed': seed, 'target': next(iter(pair.values())).metadata['target'], 'robots': {}}
    for robot, episode in pair.items():
        if robot not in renderers:
            renderers[robot] = Renderer(robot, width=64, height=64)
        renderer = renderers[robot]
        model, data, mj = renderer.model, renderer.data, renderer.mj
        if seed == 0:
            scene = trimesh.Scene()
            for body in range(model.nbody):
                scene.graph.update(frame_to=f'body-{body}', matrix=np.eye(4))
            for g in range(model.ngeom):
                kind = model.geom_type[g]
                if model.geom_group[g] == 3 or kind == mj.mjtGeom.mjGEOM_PLANE:
                    continue
                if kind == mj.mjtGeom.mjGEOM_MESH:
                    mesh = model.geom_dataid[g]
                    a, n = model.mesh_vertadr[mesh], model.mesh_vertnum[mesh]
                    b, count = model.mesh_faceadr[mesh], model.mesh_facenum[mesh]
                    geometry = trimesh.Trimesh(model.mesh_vert[a:a+n], model.mesh_face[b:b+count], process=False)
                elif kind == mj.mjtGeom.mjGEOM_BOX:
                    geometry = trimesh.creation.box(extents=model.geom_size[g]*2)
                else:
                    raise ValueError(f'Unsupported visible geometry: {kind}')
                mat = model.geom_matid[g]
                rgba = model.mat_rgba[mat] if mat >= 0 else model.geom_rgba[g]
                geometry.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(baseColorFactor=rgba, metallicFactor=.32, roughnessFactor=.42))
                transform = trimesh.transformations.quaternion_matrix(model.geom_quat[g])
                transform[:3, 3] = model.geom_pos[g]
                scene.add_geometry(geometry, node_name=f'geom-{g}', parent_node_name=f'body-{model.geom_bodyid[g]}', transform=transform)
            (OUT / f'{robot}.glb').write_bytes(scene.export(file_type='glb'))
        frames = []
        # Keep every original 30 Hz observation, including exact terminal state.
        for row in episode.rows:
            state = episode.state(row['timestamp'])
            for joint, value in zip(renderer.joints, state['joint_position'], strict=True):
                data.qpos[model.jnt_qposadr[joint]] = value
            for color, name in zip(('red', 'green', 'blue'), renderer.cube_bodies, strict=True):
                index = model.body_mocapid[model.body(name).id]
                data.mocap_pos[index] = state['cube_poses'][color][:3]
                data.mocap_quat[index] = state['cube_poses'][color][3:]
            mj.mj_forward(model, data)
            fk_error = np.linalg.norm(data.site_xpos[model.site('relic_replay_tool').id] - state['ee_position'])
            if fk_error > .0002:
                raise ValueError(f'FK check failed: {fk_error}')
            frames.append({'t': row['timestamp'], 'phase': state['phase'], 'joints': state['joint_position'], 'velocity': state['joint_velocity'], 'ee': state['ee_position'], 'target': state['control_target'], 'error': state['tracking_error_m'], 'poses': rounded(np.concatenate((data.xpos, data.xquat), axis=1))})
        filename = f'{robot}-{seed}.json'
        write(filename, {'robot': robot, 'duration': episode.duration, 'frames': frames, 'outcome': episode.outcome, 'revision': episode.source_revision, 'instruction': episode.rows[0]['instruction'], 'jointNames': episode.metadata['joint_names'], 'provenance': episode.provenance, 'sourceFiles': {name: hashlib.sha256((episode.path/name).read_bytes()).hexdigest() for name in ('metadata.json', 'outcome.json', 'samples.jsonl', 'telemetry.jsonl')}, 'geometry': renderer.provenance})
        entry['robots'][robot] = filename
    entry['duration'] = max(e.duration for e in pair.values())
    catalog.append(entry)
write('catalog.json', catalog)
# Direct copies preserve all evidence and are usable as source links on static hosting.
for robot in renderers:
    source = ROOT / 'embodiment/qualification' / f'{robot}.json'
    evidence = json.loads(source.read_text())
    evidence.pop('raw_artifact_root', None)  # machine-specific path is not a deployment dependency
    write(f'{robot}-qualification.json', evidence)
for name in ('comparison.json', 'analytical_robustness.json'):
    (OUT / f'adaptive-{name}').write_bytes((ROOT/'adaptive/revision'/name).read_bytes())
for renderer in renderers.values():
    renderer.close()
print('Exported', len(catalog), 'verified pairs to', OUT)
write('manifest.json', {
    'schema': 'viper.static_replay.v1',
    'description': 'Historical observed-state replay; no dynamics reexecution',
    'sample_rate_hz': 30,
    'pose_decimal_places': 7,
    'qualification_transform': 'raw_artifact_root removed from public qualification copies; remaining fields unchanged',
    'producer_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'embodiment/replay.py', ROOT/'embodiment/replay_render.py')},
    'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'manifest.json'},
})
