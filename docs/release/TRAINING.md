# Training stages, outputs and comparisons

The public entry point starts from scratch unless `--checkpoint` is supplied.
P1A trains two-letter sequences. Transit15 trains six-letter sequences with the
15 mm transit-clearance contract. Observation/action sizes remain 22/5.

## Short validation

```bash
./so101 train --actuator anchorbench --num-envs 64 --iterations 10 --seed 1307
```

One-iteration runs with four environments have been tested for all three actuator
profiles, task DR, changed nominal pose, custom solver settings and custom actuator
parameters. The 64-environment, 10-update AnchorBench quickstart and DR run also
pass, as does a short P1A-to-Transit15 resume. These runs test the pipeline, not
policy performance. First startup
compiles Warp kernels; the named Docker cache volume reuses them on later runs.

## Train for your configured keyboard pose

After creating your task JSON as shown in the README, an example two-stage
budget is 4,000 P1A updates followed by 16,000 six-letter updates. Evaluate early
and choose the continuation budget from your results:

```bash
./so101 train --actuator anchorbench --stage p1a \
  --task-config configs/tasks/my-keyboard.json \
  --num-envs 4096 --iterations 4000 --seed 1307

# Select the final model from that run, and use the same profile/configuration.
./so101 train --actuator anchorbench --stage transit15 \
  --checkpoint /absolute/path/to/P1A/model_N.pt \
  --num-envs 4096 --iterations 16000 --seed 1307
```

This documents a runnable staged recipe, not a newly reproduced benchmark result.
The historical benchmark used qualified precursor checkpoints and specific
multi-GPU runs. The released artifact manifest records checkpoint identities. A new seed, new geometry or new precursor is a new experiment.
RSL-RL checkpoint indices are inherited on resume; use saved iteration metadata
and the request's additional-iteration budget rather than guessing update counts
from a filename. Do not select a checkpoint solely because it has the largest
number: evaluate it under the intended sequence bank and event criteria.

`--checkpoint` restores optimizer/policy state. Task/physics JSONs beside the
checkpoint under `params/` are inherited automatically; keep the same actuator
choice unless intentionally performing a separately labelled transfer experiment.
Use `--task-config` or `--physics-config` explicitly when changing the experiment.

The 4096-environment, full-budget recipe has not been rerun in the new public
container. Memory use and wall time must be measured for the recipient's GPU.
Reduce `--num-envs` if necessary, but record it: it changes samples per PPO update
and therefore the training budget. The current default is 64 environments, not a
claim that 64 reproduces the historical training setup.

## Evaluate and compare

```bash
./so101 evaluate --actuator anchorbench --stage transit15 \
  --checkpoint /absolute/path/to/model_N.pt \
  --env-config /absolute/path/to/params/env.yaml --num-envs 1024 --seed 1307
```

Use the same task, reward, observations, training sample budget, seeds, checkpoint
selection rule and evaluation sequences when comparing independently trained
actuator profiles. Keep solver comparisons separate. A fixed-policy physics
ablation is a different experiment and is not performed silently by this CLI.

Reports include exact typing, strict press/release/clearance success, wrong keys,
termination reasons and checkpoint/configuration hashes. Generated configurations
and logs live under `output/public/<timestamp>-train/rsl_rl/...`; evaluation results
live in the corresponding `*-evaluate` directory. Keep the complete `params/`
folder with each policy for replay and deployment export.

## Supervise the staged run

For the default reference geometry, the host-side supervisor runs the same public commands sequentially and saves
stage status, console logs, evaluation reports, videos and GPU samples. Run it
inside a persistent terminal such as tmux for a long experiment:

```bash
./so101 build
./so101 setup-hardware
python3 scripts/run_public_training_pipeline.py \
  --out-dir output/reference-training-seed1307 --prepare-deployment
```

Defaults are 4096 environments, 4000 P1A updates, then 16000 additional Transit15
updates. It evaluates P1A on 1024 episodes with seed 2307 before advancing. The
default promotion threshold is 90% strict success, an engineering gate rather
than a claim of hardware readiness. A failed gate saves its report and video,
stops before Transit15, and marks `status.json` for inspection.

Transit15 is evaluated on 1024 episodes each with seeds 2307 and 3307. The optional
deployment step exports a bundle for the placeholder ID `public_pipeline_validation`
and runs software validation only. Re-export for the operator's real calibration
ID before physical use. Recorded videos still need visual review; scalar gates
do not certify contact quality or sim-to-real transfer.

The output directory must be new. `status.json` records current stage and terminal
status; `gpu.csv` records total GPU memory/use every 10 seconds, including desktop
processes. Each stage has its own public CLI request and resolved training inputs.
For individual commands, `./so101 ... --output-dir NEW_DIRECTORY` selects an explicit
output directory instead of the default timestamped location.

For custom task/physics JSONs, use the explicit train/resume commands above; the
supervisor currently exposes the reference configuration only. Short-run results
are retained in [development validation](RESULTS.md), not as recommended policies.
