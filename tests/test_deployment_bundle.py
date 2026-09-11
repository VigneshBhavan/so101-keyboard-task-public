from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml
from scripts.so101_homing.constants import ARM_JOINT_NAMES
from scripts.so101_homing.fixed_cartesian_policy import JOINT_RATE_LIMITS_RAD_S
from scripts.so101_homing.deployment_bundle import profile_from_environment, sha256, validate_manifest


class DeploymentBundleTests(unittest.TestCase):
    def test_missing_calibration_stops_export_before_writing_bundle(self):
        from scripts.so101_homing import deployment_bundle
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'bundle'
            with patch.object(deployment_bundle, 'require_calibration', side_effect=FileNotFoundError('calibrate first')), \
                 patch.object(deployment_bundle, 'FixedCartesianPolicy') as policy:
                with self.assertRaises(FileNotFoundError):
                    deployment_bundle.prepare(Path('unused'), Path('unused'), 'robot', 'lerobot', out)
                policy.assert_not_called()
            self.assertFalse(out.exists())

    def test_missing_calibration_stops_dry_run_before_runner(self):
        from scripts.so101_homing import deploy_bundle
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'deployment.json').write_text(json.dumps({'robot_id': 'missing'}))
            with patch('sys.argv', ['deploy_bundle', directory, 'NVIDIA']), \
                 patch.object(deploy_bundle, 'require_calibration', side_effect=FileNotFoundError('calibrate first')), \
                 patch.object(deploy_bundle.subprocess, 'call') as run, self.assertRaises(SystemExit) as error:
                deploy_bundle.main()
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_calibration_lookup_lists_available_ids_without_hardware(self):
        from scripts.so101_homing import robot
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'another_robot.json').write_text('{}')
            with patch.object(robot, 'calibration_directory', return_value=root), \
                 patch.object(robot, 'load_lerobot') as hardware:
                with self.assertRaisesRegex(FileNotFoundError, 'another_robot.*lerobot-calibrate'):
                    robot.require_calibration('missing')
                hardware.assert_not_called()

    def environment(self):
        return {'sim':{'dt':.01},'decimation':4, 'keyboard_profile':'mx_keys_powered_az_20260718',
                'task_contract':'test_task','target_reference_sha256':'map','target_manifest_sha256':'source',
                'commands':{'typing':{'q_reset_ref':[0]*5,'letter_xyz_b_m':[[.2+i*.001,.1,.01] for i in range(26)],
                    'target_xyz_mean_b_m':[.2,.1,.01],'target_xyz_std_b_m':[.01,.02,.001],'letter_length':[2,2]}},
                'actions':{'action':{'joint_names':list(ARM_JOINT_NAMES),'velocity_limits_rad_s':list(JOINT_RATE_LIMITS_RAD_S),'q_reset_ref':[0]*5}}}

    def test_geometry_and_convention_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'env.yaml';path.write_text(yaml.safe_dump(self.environment()))
            profile,_,stage=profile_from_environment(path,'lerobot')
            self.assertEqual(profile.joint_zero_offset_deg,(0.,)*5)
            self.assertEqual(profile.az_xyz_b_m[0],(.2,.1,.01))
            self.assertEqual(stage,'p1a')
            benchmark,_,_=profile_from_environment(path,'benchmark')
            self.assertNotEqual(profile.joint_zero_offset_deg,benchmark.joint_zero_offset_deg)

    def test_identity_hashes_and_profile_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);env=root/'env.yaml';env.write_text(yaml.safe_dump(self.environment()))
            cp=root/'checkpoint.pt';cp.write_bytes(b'test-checkpoint')
            profile,_,stage=profile_from_environment(env,'lerobot')
            data={'schema_version':1,'kind':'so101_typing_deployment_bundle','robot_id':'robot',
                  'encoder_convention':'lerobot','profile':asdict(profile),'stage':stage,'task_contract':'test_task',
                  'checkpoint_sha256':sha256(cp),'env_sha256':sha256(env)}
            manifest=root/'deployment.json';manifest.write_text(json.dumps(data))
            validate_manifest(manifest,cp,env,'robot')
            with self.assertRaises(ValueError):validate_manifest(manifest,cp,env,'other')
            data['profile']['az_xyz_b_m']=[[0,0,0]]*26;manifest.write_text(json.dumps(data))
            with self.assertRaises(ValueError):validate_manifest(manifest,cp,env,'robot')
            cp.write_bytes(b'changed')
            with self.assertRaises(ValueError):validate_manifest(manifest,cp,env,'robot')

    def test_execute_requires_explicit_user_devices_before_loading_bundle(self):
        from scripts.so101_homing import deploy_bundle
        with patch('sys.argv', ['deploy_bundle', '/nonexistent', 'HE', '--execute']), \
             patch.object(deploy_bundle.subprocess, 'call') as run, self.assertRaises(SystemExit) as error:
            deploy_bundle.main()
        self.assertEqual(error.exception.code, 2)
        run.assert_not_called()

    def test_unsupported_control_timing_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            data=self.environment();data['sim']['dt']=.02
            path=Path(directory)/'env.yaml';path.write_text(yaml.safe_dump(data))
            with self.assertRaises(ValueError):profile_from_environment(path,'lerobot')
