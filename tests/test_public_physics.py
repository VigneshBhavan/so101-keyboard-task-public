import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/reinforcement_learning/rsl_rl'))
from public_physics import apply_config, fingerprint, load_config


class PhysicsTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'physics.json'
            path.write_text(json.dumps(data))
            return load_config(path)

    def test_invalid_physics_fails_closed(self):
        for extra in [{'solver': 'physx'}, {'num_substeps': 0}, {'num_substeps': True},
                      {'solver_parameters': {'iterations': 2.5}},
                      {'actuator_parameters': {'stiffness': {'shoulder_pan': 10}}},
                      {'actuator_parameters': {'friction': float('nan')}},
                      {'unrecognized': 5}]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.load({'schema_version': 1, 'solver': 'mjwarp', **extra})

    def test_overrides_do_not_change_unrequested_fields(self):
        data = self.load({'schema_version': 1, 'solver': 'mjwarp', 'num_substeps': 4,
                          'solver_parameters': {'iterations': 50}, 'actuator_parameters': {'stiffness': 80}})
        actuator = Obj(stiffness=100, damping=1)
        env = Obj(task_contract='original', sim=Obj(physics=Obj(num_substeps=2, solver_cfg=Obj(iterations=100))),
                  scene=Obj(robot=Obj(actuators={'all': actuator})))
        apply_config(env, data)
        self.assertEqual(env.sim.physics.num_substeps, 4)
        self.assertEqual(env.sim.physics.solver_cfg.iterations, 50)
        self.assertEqual(actuator.stiffness, 80)
        self.assertEqual(actuator.damping, 1)
        self.assertEqual(env.task_contract, 'original_physics_' + fingerprint(data))

    def test_fingerprint_ignores_json_key_order(self):
        self.assertEqual(fingerprint({'a': 1, 'b': 2}), fingerprint({'b': 2, 'a': 1}))
