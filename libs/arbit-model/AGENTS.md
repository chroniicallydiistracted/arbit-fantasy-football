# Model-specific rules

Inherited root AGENTS.md applies. Follow [ADR-006](../../docs/architecture/decisions/006-model-architecture.md)
and [model specification](../../docs/architecture/model-specification.md).
[ADR-007](../../docs/architecture/decisions/007-model-availability.md) is accepted
with owner amendments A1–A4 (OWN-066); apply them, including labeled known-from bases.
Feature code reads nflverse only through `arbit_model.point_in_time.PointInTime` with a
decision time; never read a whole current file into a feature. A new table needs a
`timing.TableSpec` with its unit and rule, and a test. No trained model/projection
feature exists in this source snapshot. Model input/target/backtest changes require source provenance, cutoff,
no-leakage checks, baselines and recorded test evidence.
