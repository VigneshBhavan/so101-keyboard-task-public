"""Data-only task configuration for nominal fixture placement and blind pose DR."""
import hashlib
import json
import math
from pathlib import Path


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def load_config(path):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or set(data) - {'schema_version', 'keyboard', 'domain_randomization'}:
        raise ValueError('unknown task configuration fields')
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('task configuration requires schema_version=1')
    keyboard = data.get('keyboard', {})
    if not isinstance(keyboard, dict) or set(keyboard) - {'position_m', 'yaw_offset_deg'}:
        raise ValueError('keyboard accepts position_m and yaw_offset_deg')
    if 'position_m' in keyboard:
        position = keyboard['position_m']
        if not isinstance(position, list) or len(position) != 3 or not all(map(finite, position)):
            raise ValueError('position_m must contain three finite robot-base coordinates in metres')
    if not finite(keyboard.get('yaw_offset_deg', 0)):
        raise ValueError('yaw_offset_deg must be finite')
    dr = data.get('domain_randomization', {})
    if not isinstance(dr, dict) or set(dr) - {'keyboard_x_m', 'keyboard_y_m', 'keyboard_yaw_deg', 'reset_joint_noise_rad'}:
        raise ValueError('unknown domain randomization field')
    for key, bounds in dr.items():
        if key == 'reset_joint_noise_rad':
            if not finite(bounds) or bounds < 0:
                raise ValueError('reset_joint_noise_rad must be finite and nonnegative')
        elif not isinstance(bounds, list) or len(bounds) != 2 or not all(map(finite, bounds)) or bounds[0] > bounds[1]:
            raise ValueError(f'{key} requires ordered finite [minimum, maximum]')
    return data


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def rotate_xyzw(q, v):
    x, y, z, w = q
    # q v q^-1 for a unit quaternion.
    tx, ty, tz = 2*(y*v[2]-z*v[1]), 2*(z*v[0]-x*v[2]), 2*(x*v[1]-y*v[0])
    return [v[0]+w*tx+y*tz-z*ty, v[1]+w*ty+z*tx-x*tz, v[2]+w*tz+x*ty-y*tx]


def nominal_geometry(position, rotation, points, keyboard):
    new_position = keyboard.get('position_m', position)
    yaw = math.radians(keyboard.get('yaw_offset_deg', 0))
    c, s = math.cos(yaw), math.sin(yaw)
    transformed = []
    for point in points:
        x, y, z = [a-b for a,b in zip(point, position)]
        transformed.append([new_position[0]+c*x-s*y, new_position[1]+s*x+c*y, new_position[2]+z])
    # Left-multiply by a robot-base-Z rotation; quaternion order is xyzw.
    h, k = math.sin(yaw/2), math.cos(yaw/2)
    x,y,z,w = rotation
    new_rotation = [k*x-h*y, k*y+h*x, k*z+h*w, k*w-h*z]
    local = [rotate_xyzw([-rotation[0],-rotation[1],-rotation[2],rotation[3]],
                         [a-b for a,b in zip(point, position)]) for point in points]
    return list(new_position), new_rotation, transformed, local


def apply_config(env_cfg, data):
    from isaaclab_tasks.core.dexsuite.config.so101.mdp.public_events import reset_public_keyboard
    state = env_cfg.scene.keyboard.init_state
    old_position = list(state.pos)
    position, rotation, points, local = nominal_geometry(old_position, state.rot,
                                                        env_cfg.commands.typing.letter_xyz_b_m, data.get('keyboard', {}))
    state.pos, state.rot = tuple(position), tuple(rotation)
    plane = env_cfg.scene.plane.init_state
    plane.pos = (plane.pos[0], plane.pos[1], plane.pos[2]+position[2]-old_position[2])
    cfg = env_cfg.commands.typing
    cfg.letter_xyz_b_m = tuple(tuple(p) for p in points)
    # Preserve the original coordinate normalization: changed position remains observable.
    cfg.public_pose_randomization = True
    env_cfg.target_reference_sha256 = fingerprint({'letter_xyz_b_m': points})
    dr = data.get('domain_randomization', {})
    env_cfg.events.reset_keyboard.func = reset_public_keyboard
    env_cfg.events.reset_keyboard.params = {
        'x_range_m': tuple(dr.get('keyboard_x_m', [0,0])),
        'y_range_m': tuple(dr.get('keyboard_y_m', [0,0])),
        'yaw_range_rad': tuple(math.radians(x) for x in dr.get('keyboard_yaw_deg', [0,0])),
        'letter_xyz_keyboard_m': local,
    }
    noise = dr.get('reset_joint_noise_rad', 0)
    env_cfg.events.reset_robot_rest.params['position_range'] = (-noise, noise)
    # q_reset_ref remains fixed; only reset arrival is randomized.
    env_cfg.task_contract += '_task_' + fingerprint(data)
    return env_cfg
