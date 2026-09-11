# SO-101 deployment tools

For new users, follow [hardware preparation](../../docs/release/HARDWARE_PREPARATION.md)
and use `./so101 prepare-deployment` followed by `./so101 deploy`. Both training
for your own placement and the optional reference checkpoint use that workflow.
You calibrate your own robot with LeRobot; export generates the matching reset
pose from the saved training geometry and your chosen encoder convention.

The shared runner validates the checkpoint, environment, target length, geometry,
reset pose and timing contract before connecting. The public deployment command
also checks the local calibration file on every dry run and execution. Hardware
motion requires the explicit `--execute` option and operator confirmation.

## Historical benchmark tools

The dated `run_physical_calibrated_20260718_irl.sh` launcher and `typing_ab_*`
tools reproduce the original fixed-fixture benchmark. They assume that robot's
separately fitted encoder convention and are retained for interpreting historical
results. The older launcher enables hardware mode unless `SO101_POLICY_DRY_RUN=1`
is set; use the public dry-run-by-default interface for new deployments.

- [Historical deployment contract](../../docs/source/policy_deployment/06_so101_keyboard/physical_typing_contract.rst)
- [Historical matched benchmark](../../docs/source/policy_deployment/06_so101_keyboard/physical_typing_benchmark.rst)

Workshop and Sparse VBD references in those historical tools are outside the
public training interface, which exposes only AnchorBench and USD with MJWarp.
