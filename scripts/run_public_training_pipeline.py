#!/usr/bin/env python3
"""Run staged public training, held-out evaluation and optional software-only export.

This host-side supervisor uses the public ./so101 CLI. It never enables hardware.
Each invocation owns a new output directory and can run in a detached tmux session.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time


ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def checkpoint_artifacts(run):
    configs = list(run.glob('rsl_rl/*/*/params/env.yaml'))
    if len(configs) != 1:
        raise RuntimeError(f'Expected one saved training environment in {run}, found {len(configs)}')
    checkpoints = list(configs[0].parent.parent.glob('model_*.pt'))
    if not checkpoints:
        raise RuntimeError(f'No checkpoint was saved in {run}')
    # Select the completed run's final checkpoint, then assess its quality by evaluation.
    checkpoint = max(checkpoints, key=lambda p: int(p.stem.removeprefix('model_')))
    return checkpoint, configs[0]


def passes_gate(report, minimum):
    # Exact typing alone does not establish release/clearance or valid contacts.
    score = float(report['overall_success_rate'])
    return 0 <= score <= 1 and score >= minimum


class Pipeline:
    def __init__(self, args):
        self.args = args
        self.root = args.out_dir.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=False)
        self.status = {
            'schema_version': 1, 'started_at': now(), 'status': 'starting',
            'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'supervisor_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'configuration': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
            'hardware_motion_enabled': False, 'stages': [],
        }
        self.save()
        self.stop = threading.Event()
        self.monitor = threading.Thread(target=self.monitor_gpu, daemon=True)

    def save(self):
        self.status['updated_at'] = now()
        write_json(self.root / 'status.json', self.status)

    def monitor_gpu(self):
        with (self.root / 'gpu.csv').open('w') as log:
            log.write('timestamp, index, memory_used_mib, memory_total_mib, utilization_percent, power_watts\n')
            while not self.stop.is_set():
                result = subprocess.run([
                    'nvidia-smi', '--query-gpu=timestamp,index,memory.used,memory.total,utilization.gpu,power.draw',
                    '--format=csv,noheader,nounits',
                ], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    log.write(result.stdout)
                    log.flush()
                self.stop.wait(10)

    def run(self, name, arguments, simulation=True):
        run = self.root / name
        command = [str(ROOT / 'so101'), *map(str, arguments)]
        if simulation:
            command += ['--output-dir', str(run)]
        entry = {'name': name, 'command': command, 'started_at': now(), 'status': 'running'}
        self.status['status'] = 'running'
        self.status['active_stage'] = name
        self.status['stages'].append(entry)
        self.save()
        print(f'[{now()}] Starting {name}', flush=True)
        start = time.monotonic()
        with (self.root / f'{name}.launcher.log').open('w') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        entry.update(exit_code=result.returncode, elapsed_seconds=round(time.monotonic()-start, 2),
                     finished_at=now(), status='passed' if result.returncode == 0 else 'failed')
        self.save()
        if result.returncode:
            raise RuntimeError(f'{name} exited {result.returncode}; see {name}.launcher.log')
        return run

    def train(self, name, stage, iterations, checkpoint=None):
        command = ['train', '--actuator', 'anchorbench', '--stage', stage,
                   '--num-envs', self.args.num_envs, '--iterations', iterations, '--seed', self.args.seed]
        if checkpoint:
            command += ['--checkpoint', checkpoint]
        return checkpoint_artifacts(self.run(name, command))

    def evaluate(self, name, stage, artifacts, seed):
        checkpoint, config = artifacts
        run = self.run(name, ['evaluate', '--actuator', 'anchorbench', '--stage', stage,
            '--checkpoint', checkpoint, '--env-config', config, '--num-envs', self.args.eval_envs,
            '--seed', seed])
        report = json.loads((run / 'evaluation.json').read_text())
        entry = self.status['stages'][-1]
        entry['overall_success_rate'] = report['overall_success_rate']
        entry['typed_exact_rate'] = report['typed_exact_rate']
        entry['quality_gate_passed'] = passes_gate(report, self.args.minimum_success)
        self.save()
        return entry['quality_gate_passed']

    def video(self, name, stage, artifacts, target):
        checkpoint, config = artifacts
        self.run(name, ['video', '--actuator', 'anchorbench', '--stage', stage,
            '--checkpoint', checkpoint, '--env-config', config, '--target', target])

    def execute(self):
        self.monitor.start()
        try:
            p1a = self.train('01-p1a-train', 'p1a', self.args.p1a_iterations)
            qualified = self.evaluate('02-p1a-evaluate', 'p1a', p1a, self.args.seed + 1000)
            self.video('03-p1a-video', 'p1a', p1a, 'HE')
            if not qualified:
                self.status['status'] = 'p1a_quality_gate_failed'
                self.status['next_action'] = 'Inspect evaluation and video before extending training or advancing curriculum.'
                return 2
            transit = self.train('04-transit15-train', 'transit15', self.args.transit_iterations, p1a[0])
            gates = [self.evaluate(f'05-transit15-evaluate-seed-{seed}', 'transit15', transit, seed)
                     for seed in (self.args.seed + 1000, self.args.seed + 2000)]
            self.video('06-transit15-video', 'transit15', transit, 'NVIDIA')
            if self.args.prepare_deployment:
                bundle = self.root / 'deployment'
                self.run('07-prepare-deployment', ['prepare-deployment', '--checkpoint', transit[0],
                    '--env-config', transit[1], '--robot-id', 'public_pipeline_validation',
                    '--encoder-convention', 'lerobot', '--out-dir', bundle], simulation=False)
                self.run('08-deployment-dry-run', ['deploy', bundle, 'NVIDIA'], simulation=False)
            self.status['status'] = 'software_quality_gates_passed' if all(gates) else 'transit15_quality_gate_failed'
            self.status['final_checkpoint'] = str(transit[0])
            self.status['next_action'] = 'Inspect saved rollout videos and traces; physical reproduction requires operator validation.'
            return 0 if all(gates) else 2
        except KeyboardInterrupt:
            self.status['status'] = 'interrupted'
            raise
        except Exception as error:
            self.status['status'] = 'execution_failed'
            self.status['error'] = str(error)
            raise
        finally:
            self.stop.set()
            self.monitor.join(timeout=15)
            self.status['finished_at'] = now()
            self.status.pop('active_stage', None)
            self.save()
            print(f'[{now()}] {self.status["status"]}: {self.root / "status.json"}', flush=True)


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--num-envs', type=positive, default=4096)
    parser.add_argument('--eval-envs', type=positive, default=1024)
    parser.add_argument('--p1a-iterations', type=positive, default=4000)
    parser.add_argument('--transit-iterations', type=positive, default=16000)
    parser.add_argument('--seed', type=int, default=1307)
    parser.add_argument('--minimum-success', type=float, default=0.90)
    parser.add_argument('--prepare-deployment', action='store_true', help='Requires ./so101 setup-hardware; performs dry run only')
    args = parser.parse_args()
    if not 0 < args.minimum_success <= 1:
        parser.error('--minimum-success must be in (0, 1]')
    return Pipeline(args).execute()


if __name__ == '__main__':
    raise SystemExit(main())
