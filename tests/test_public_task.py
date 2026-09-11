import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/reinforcement_learning/rsl_rl'))
from public_task import load_config, load_perturbation, nominal_geometry, rotate_xyzw, evaluation_reset_metadata


class PublicTaskTests(unittest.TestCase):
    def test_robustness_cannot_move_the_nominal_actor_map(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'perturbation.json'
            path.write_text(json.dumps({'schema_version': 1, 'keyboard': {'yaw_offset_deg': 1}}))
            with self.assertRaises(ValueError):
                load_perturbation(path)
            path.write_text(json.dumps({'schema_version': 1, 'domain_randomization': {'keyboard_x_m': [-.001, .001]}}))
            self.assertEqual(load_perturbation(path)['domain_randomization']['keyboard_x_m'], [-.001, .001])

    def test_evaluation_reports_resolved_randomization(self):
        cfg = SimpleNamespace(events=SimpleNamespace(
            reset_robot_rest=SimpleNamespace(params={'position_range': (-.005, .005), 'velocity_range': (0, 0)}),
            reset_keyboard=SimpleNamespace(params={'x_range_m': (-.003, .003), 'yaw_range_rad': (0, 0)})))
        report = evaluation_reset_metadata(cfg)
        self.assertFalse(report['exact_model_rest'])
        self.assertTrue(report['zero_joint_velocity'])
        self.assertTrue(report['keyboard_pose_randomization'])
        cfg.events.reset_robot_rest.params['position_range'] = (0, 0)
        cfg.events.reset_keyboard.params['x_range_m'] = (0, 0)
        report = evaluation_reset_metadata(cfg)
        self.assertTrue(report['exact_model_rest'])
        self.assertFalse(report['keyboard_pose_randomization'])

    def test_world_yaw_and_translation_move_map_with_fixture(self):
        pos, rot, points, local = nominal_geometry([1,2,3], [0,0,0,1], [[2,2,3]],
                                                   {'position_m':[4,5,6], 'yaw_offset_deg':90})
        for actual, expected in zip(points[0], [4,6,6]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(local, [[1,0,0]])
        restored = [a+b for a,b in zip(rotate_xyzw(rot,local[0]),pos)]
        for a,b in zip(restored,points[0]):self.assertAlmostEqual(a,b)

    def test_tilted_keyboard_round_trip_and_identity(self):
        q=[math.sin(.2),0,0,math.cos(.2)]
        pos, rot, points, local = nominal_geometry([.2,.1,.01],q,[[.21,.13,.02]],{})
        restored = [a+b for a,b in zip(rotate_xyzw(rot,local[0]),pos)]
        for a,b in zip(restored,points[0]):self.assertAlmostEqual(a,b)

    def test_bad_pose_and_randomization_rejected(self):
        for extra in [{'keyboard':{'position_m':[0,0]}}, {'keyboard':{'yaw_offset_deg':float('nan')}},
                      {'domain_randomization':{'keyboard_x_m':[1,-1]}},
                      {'domain_randomization':{'reset_joint_noise_rad':-1}},
                      {'domain_randomization':{'keyboard_z_m':[-.01,.01]}}]:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'task.json';path.write_text(json.dumps({'schema_version':1,**extra}))
                with self.assertRaises(ValueError):load_config(path)
