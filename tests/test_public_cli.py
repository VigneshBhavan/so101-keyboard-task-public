"""Host-only contract checks: never start Docker or connect to hardware."""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('public_cli', str(ROOT / 'so101'))
spec = importlib.util.spec_from_loader(loader.name, loader)
cli = importlib.util.module_from_spec(spec)
loader.exec_module(cli)


class PublicCliTests(unittest.TestCase):
    def test_download_archive_requires_explicit_option(self):
        for extra in ([], ['--all']):
            with patch.object(sys, 'argv', ['so101', 'download', *extra]), \
                 patch.object(cli.subprocess, 'call', return_value=0) as execute:
                self.assertEqual(cli.main(), 0)
                self.assertEqual(execute.call_args.args[0],
                                 [str(ROOT / 'scripts/download_benchmark_artifacts.sh'), *extra])

    def plan(self, *args):
        with patch.object(sys, 'argv', ['so101', *args]), patch('builtins.print') as out, patch.object(cli.subprocess, 'call') as execute:
            self.assertEqual(cli.main(), 0)
            execute.assert_not_called()
            return out.call_args.args[0]

    def test_profiles_map_to_distinct_registered_tasks(self):
        for profile, registered in cli.PROFILES.items():
            command = self.plan('train', '--actuator', profile, '--plan')
            self.assertIn(f'FixedCartesian-{registered}-P1A', command)
            self.assertIn('physics=newton_mjwarp', command)
            self.assertNotIn('--device=/dev', command)

    def test_rejects_unqualified_solver_and_invalid_budget(self):
        for args in [('train', '--solver', 'physx'), ('train', '--iterations', '0'),
                     ('train', '--actuator', 'workshop')]:
            with patch.object(sys, 'argv', ['so101', *args]), self.assertRaises(SystemExit) as error:
                cli.main()
            self.assertEqual(error.exception.code, 2)

    def test_artifacts_are_mounted_read_only_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='typing test ') as directory:
            checkpoint = Path(directory) / 'checkpoint.pt'
            config = Path(directory) / 'env.yaml'
            checkpoint.write_bytes(b'fixture')
            config.write_text('fixture: true')
            command = self.plan('evaluate', '--checkpoint', str(checkpoint), '--env-config', str(config), '--plan')
            self.assertIn('dst=/inputs/checkpoint.pt,readonly', command)
            self.assertIn('dst=/inputs/env.yaml,readonly', command)

    def test_resume_preserves_explicit_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / 'model_0.pt'
            checkpoint.write_bytes(b'fixture')
            command = self.plan('train', '--stage', 'transit15', '--checkpoint', str(checkpoint), '--plan')
            self.assertIn('--resume --checkpoint /inputs/checkpoint.pt', command)
            self.assertIn('dst=/inputs/checkpoint.pt,readonly', command)

    def test_probe_obeys_selected_profile(self):
        command = self.plan('probe', '--actuator', 'usd', '--seed', '42', '--plan')
        self.assertIn('FixedCartesian-USDDrive-P1D-Transit15', command)
        self.assertIn('--seed 42', command)


if __name__ == '__main__':
    unittest.main()
