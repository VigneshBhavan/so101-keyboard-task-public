import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.run_public_training_pipeline import Pipeline, passes_gate
from scripts import run_public_training_pipeline as supervisor


class TrainingPipelineTests(unittest.TestCase):
    def test_source_archive_does_not_require_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(supervisor, 'ROOT', root), \
                 patch.object(supervisor.subprocess, 'check_output') as git:
                pipeline = self.pipeline(root / 'run')
            git.assert_not_called()
            self.assertIsNone(pipeline.status['source_commit'])
            self.assertEqual(pipeline.status['source_distribution'], 'archive')

    def test_gate_uses_strict_success_and_rejects_nonfinite_scores(self):
        self.assertFalse(passes_gate({'typed_exact_rate': 1.0, 'overall_success_rate': 0.2}, 0.9))
        self.assertFalse(passes_gate({'overall_success_rate': float('nan')}, 0.9))
        self.assertTrue(passes_gate({'overall_success_rate': 0.95}, 0.9))

    def pipeline(self, root):
        args = argparse.Namespace(out_dir=root, num_envs=4, eval_envs=4, p1a_iterations=1,
                                  transit_iterations=1, seed=1307, minimum_success=0.9,
                                  prepare_deployment=True, robot_id='test_robot')
        pipeline = Pipeline(args)
        pipeline.monitor = Mock()
        return pipeline

    def test_failed_p1a_gate_keeps_evidence_and_prevents_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self.pipeline(Path(directory) / 'run')
            with patch.object(pipeline, 'train', return_value=('checkpoint', 'config')) as train, \
                 patch.object(pipeline, 'evaluate', return_value=False), \
                 patch.object(pipeline, 'video') as video, patch.object(pipeline, 'run') as run:
                self.assertEqual(pipeline.execute(), 2)
            train.assert_called_once()
            video.assert_called_once()
            run.assert_not_called()
            saved = json.loads((pipeline.root / 'status.json').read_text())
            self.assertEqual(saved['status'], 'p1a_quality_gate_failed')
            self.assertFalse(saved['hardware_motion_enabled'])

    def test_successful_pipeline_only_dry_runs_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self.pipeline(Path(directory) / 'run')
            with patch.object(pipeline, 'train', return_value=('checkpoint', 'config')) as train, \
                 patch.object(pipeline, 'evaluate', return_value=True) as evaluate, \
                 patch.object(pipeline, 'video'), patch.object(pipeline, 'run') as run:
                self.assertEqual(pipeline.execute(), 0)
            self.assertEqual(train.call_count, 2)
            self.assertEqual(evaluate.call_count, 3)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[1][0], 'deploy')
            self.assertNotIn('--execute', run.call_args.args[1])

    def test_failed_six_letter_gate_prevents_export(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self.pipeline(Path(directory) / 'run')
            with patch.object(pipeline, 'train', return_value=('checkpoint', 'config')), \
                 patch.object(pipeline, 'evaluate', side_effect=[True, True, False]), \
                 patch.object(pipeline, 'video') as video, patch.object(pipeline, 'run') as run:
                self.assertEqual(pipeline.execute(), 2)
            self.assertEqual(video.call_count, 2)
            run.assert_not_called()
            self.assertEqual(pipeline.status['status'], 'transit15_quality_gate_failed')


if __name__ == '__main__':
    unittest.main()
