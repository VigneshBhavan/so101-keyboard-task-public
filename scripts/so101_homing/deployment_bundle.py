"""Prepare and validate portable typing deployment inputs without opening hardware."""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import shutil

import yaml
from .constants import ARM_JOINT_NAMES
from .robot import require_calibration
from .fixed_cartesian_policy import (PHYSICAL_CALIBRATED_20260718_PROFILE, JOINT_RATE_LIMITS_RAD_S,
                                     FixedCartesianPolicy)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def floats(value, length):
    result = tuple(float(x) for x in value)
    if len(result) != length or not all(math.isfinite(x) for x in result):
        raise ValueError(f'expected {length} finite values')
    return result


def profile_from_environment(path, encoder_convention):
    env = yaml.load(Path(path).read_text(), Loader=yaml.BaseLoader)
    if not isinstance(env, dict):
        raise ValueError('environment configuration must be a mapping')
    cfg = env['commands']['typing']
    action = env['actions']['action']
    if not math.isclose(float(env['sim']['dt'])*int(env['decimation']), .04, abs_tol=1e-10):
        raise ValueError('deployment requires the trained 25 Hz control contract')
    if floats(action['velocity_limits_rad_s'],5) != tuple(JOINT_RATE_LIMITS_RAD_S):
        raise ValueError('unsupported joint-rate envelope')
    if tuple(action['joint_names']) != tuple(ARM_JOINT_NAMES):
        raise ValueError('unsupported controlled joint order')
    q_reset = floats(cfg['q_reset_ref'],5)
    if q_reset != floats(action['q_reset_ref'],5):
        raise ValueError('action and observation reset references differ')
    if encoder_convention not in ('lerobot', 'benchmark'):
        raise ValueError('unknown encoder convention')
    offsets = (0.,)*5 if encoder_convention == 'lerobot' else PHYSICAL_CALIBRATED_20260718_PROFILE.joint_zero_offset_deg
    points = tuple(floats(row,3) for row in cfg['letter_xyz_b_m'])
    if len(points) != 26:
        raise ValueError('requires the A-Z Cartesian map')
    std = floats(cfg['target_xyz_std_b_m'],3)
    if min(std) <= 0:
        raise ValueError('target normalization scales must be positive')
    length = tuple(int(x) for x in cfg['letter_length'])
    stage = {(1,1):'p0',(2,2):'p1a',(3,3):'p1b',(4,4):'p1c',(6,6):'p1d'}.get(length)
    if stage is None:
        raise ValueError('unsupported target length')
    profile = replace(PHYSICAL_CALIBRATED_20260718_PROFILE,
        calibration_id=env['keyboard_profile'], q_reset_rad=q_reset, az_xyz_b_m=points,
        az_xyz_mean_b_m=floats(cfg['target_xyz_mean_b_m'],3), az_xyz_std_b_m=std,
        target_reference_sha256=env['target_reference_sha256'],
        target_manifest_sha256=env['target_manifest_sha256'], joint_zero_offset_deg=offsets)
    return profile, env, stage


def validate_manifest(path, checkpoint, env_config, robot_id):
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1 or data.get('kind') != 'so101_typing_deployment_bundle':
        raise ValueError('unsupported deployment bundle')
    if data.get('robot_id') != robot_id:
        raise ValueError('bundle robot_id differs from the selected LeRobot calibration ID')
    if sha256(checkpoint) != data.get('checkpoint_sha256') or sha256(env_config) != data.get('env_sha256'):
        raise ValueError('checkpoint/environment hash differs from prepared deployment bundle')
    profile, env, stage = profile_from_environment(env_config, data['encoder_convention'])
    if json.loads(json.dumps(asdict(profile))) != data.get('profile'):
        raise ValueError('bundle geometry differs from the archived training environment')
    if env['task_contract'] != data.get('task_contract') or stage != data.get('stage'):
        raise ValueError('bundle task or stage differs from training')
    return profile, data


def prepare(checkpoint, env_config, robot_id, encoder_convention, out_dir):
    if not robot_id.strip():
        raise ValueError('robot_id must be nonempty and match the LeRobot calibration ID')
    require_calibration(robot_id)
    profile, env, stage = profile_from_environment(env_config, encoder_convention)
    policy = FixedCartesianPolicy(checkpoint)  # Validate supported checkpoint schema on CPU.
    out_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(checkpoint, out_dir/'checkpoint.pt')
    shutil.copy2(env_config, out_dir/'env.yaml')
    for name in ('public_task.json','public_physics.json'):
        candidate = env_config.parent/name
        if candidate.is_file():shutil.copy2(candidate,out_dir/name)
    manifest = {'schema_version':1,'kind':'so101_typing_deployment_bundle','robot_id':robot_id,
                'encoder_convention':encoder_convention,'profile':asdict(profile), 'stage':stage,
                'task_contract':env['task_contract'],'actuator_profile':env['actuator_profile'],
                'checkpoint_sha256':policy.sha256,'env_sha256':sha256(env_config),
                'hardware_validated':False}
    (out_dir/'deployment.json').write_text(json.dumps(manifest,indent=2)+'\n')
    rest = {'schema_version':1,'kind':'so101_policy_rest_pose','robot_id':robot_id,
            'arm_joint_names':list(ARM_JOINT_NAMES),'closed_fixed_jaw_required':True,'contact_required':False,
            'pose_deg':{joint:math.degrees(q)-offset for joint,q,offset in
                        zip(ARM_JOINT_NAMES,profile.q_reset_rad,profile.joint_zero_offset_deg)},
            'source':'software-derived reset target; not a measured hardware pose'}
    (out_dir/'rest_pose.json').write_text(json.dumps(rest,indent=2)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--env-config',type=Path,required=True)
    parser.add_argument('--robot-id',required=True)
    parser.add_argument('--encoder-convention',choices=('lerobot','benchmark'),required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    args=parser.parse_args()
    try:
        prepare(args.checkpoint,args.env_config,args.robot_id,args.encoder_convention,args.out_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(args.out_dir.resolve())


if __name__=='__main__': main()
