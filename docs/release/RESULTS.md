# Public pipeline qualification — 2026-09-10

The new AnchorBench policy learns six-letter typing after a short continuation.
It is a simulation-qualified demonstration, with remaining contact failures and
no new physical validation. Training is stopped.

## Learning and timing

| Stage | Completed PPO updates | Strict evaluation | Wrong-key failures | Training-loop time |
| --- | ---: | ---: | ---: | ---: |
| P1A, two letters | 501 | 2,048 / 2,048 (100%) | 0 | 29 min 17 s |
| Transit15, six letters | 50 additional | 2,027 / 2,048 (98.97%) | 3 | 2 min 57 s |

Both use seed 1307, 4096 environments, Newton MJWarp and an RTX 5090 with 32 GB.
Evaluation uses 1024 episodes each at seeds 2307 and 3307. Six-letter results are
1013/1024 and 1014/1024; the other 18 failures are scrape terminations.
There are no excessive-contact terminations in these evaluations.
The training-loop total is **32 min 14 s**, excluding container/kernel startup,
evaluation and prior smoke experiments. These are measured local timings, not a
minimum-GPU promise or a multi-seed learning comparison.

The P1A file is `model_500.pt`: the log records iterations 0 through 500, or 501
updates. Resume inherits iteration 500 and executes 50 further updates through
549. Thus `model_549.pt` represents 551 cumulative updates, not 549 or 550.
The dataset includes per-iteration timing CSVs and runtime/image identities.

## Fixed-policy placement tolerance

The six-letter checkpoint, nominal actor map, seed 2307 and 1024-sequence bank
are identical across these tests. Offsets are sampled uniformly at reset.

| Actual keyboard perturbation | Strict successes | Rate | Wrong-key episodes |
| --- | ---: | ---: | ---: |
| Zero-offset control | 1013 / 1024 | 98.93% | 1 |
| X and Y each +/-1 mm; yaw +/-0.25 degrees | 1011 / 1024 | 98.73% | 5 |
| X and Y each +/-3 mm; yaw +/-1 degree | 862 / 1024 | 84.18% | 156 |

Robot reset noise is zero. The zero-offset result matches the original evaluation.
The wider range clearly reduces performance. This is one policy and one seed,
with combined XY/yaw variation; it is neither a guarantee for every placement
nor evidence of physical robustness or robustness to different actuator physics.
Run these tests with `--perturbation-config`; see [task configuration](TASK_CONFIGURATION.md).

## Rollout and deployment review

P1A HE, AZ and QZ recordings pass strict event judging. The six-letter NVIDIA
recording passes with six down/up/clearance cycles. Sampled frames near key-down
and clearance show approach, contact and withdrawal; obvious tunnelling or
teleportation during typing was not observed. The final frame resets the robot
after episode termination. The evaluator now retains the terminal event before
that reset. Rendering alone cannot establish contact forces or hardware safety;
the batch scrape failures above remain part of the result.

The reports also record peak key depression of **1.579 times nominal joint
travel** for the six-letter policy (P1A: 1.540). The key joints therefore exceed
their nominal travel range in this simulator. Strict typing success does not
reject this overtravel, and zero excessive-contact terminations does not prove
physically accurate contact. Key-stop compliance, solver penetration and contact
forces need further qualification before interpreting simulation success as
physical readiness. No physics parameters or success thresholds were changed to
hide this finding.

Key events come from simulated key-joint travel with hysteresis and dwell,
not tip proximity alone. Strict success requires exact text and matching counts
of key-down, key-up and clearance, without failure terminations. Transit15 uses
15 mm clearance for two control ticks.

The standard-LeRobot deployment bundle passes software validation. Its CPU actor
matches 261 recorded simulator action vectors with maximum absolute error
**1.3113e-6** (tolerance 1e-5), including saved normalization and Beta mean output.
This checks inference parity; calibration, fixture alignment and physical typing
still require the operator and the actual robot.

## Published evidence

The [dataset](https://huggingface.co/datasets/VigneshBhavan/so101-keyboard-typing-benchmark)
contains `checkpoints/public-p1a-seed1307/`,
`checkpoints/public-transit15-seed1307/`, matched `params/`, full evaluation JSONs,
videos, placement configurations, actor-parity evidence and training timing CSVs.
`manifest.json` maps the artifacts. `SHA256SUMS` uses relative paths and covers all
release files except itself and Hugging Face's Git attributes/cache metadata.
The repository downloader pins an immutable dataset revision and explicit hashes.

The older fixed-fixture physical benchmark remains separate from these new
simulation results. Metadata cleanup preserves its checkpoint bytes and numeric
results; unpublished raw-log locations are labelled as unavailable. Previous
dataset revisions remain historical records.

## Remaining reproduction evidence

Host tests, Newton contract tests, container execution and CPU deployment checks
are local software evidence. A clean-checkout test on this workstation is not an
independent installation. Follow [REPRODUCTION.md](REPRODUCTION.md) on another
machine and SO-101 before claiming complete new-user physical reproduction.

A fresh checkout with new Python environments passed public download/audit,
cached container build, GPU probe, one-update training, 64/64 released-policy
episodes, hardware setup, export, dry run and CPU parity. The dataset includes
`evaluation/fresh-checkout-software-validation.json`. Caches and the same GPU
were reused; independent-machine and physical validation remain pending.
