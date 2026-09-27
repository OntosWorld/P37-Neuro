# Contributing to P37 Neuro

P37 Neuro is robotics infrastructure. Small interface mistakes can become expensive physical-system failures, so changes are expected to be reviewable, reproducible and tested.

## Development rules

- Keep core APIs independent of ROS, simulator and manufacturer SDKs.
- Add type hints to all public Python APIs.
- Add or update tests for behavioral changes.
- Preserve SI units at public boundaries unless a type explicitly states otherwise.
- Never weaken a safety check only to make an experiment pass.
- Do not commit datasets, model weights or credentials to the repository.
- Record random seeds and configuration identifiers for experiments.
- Keep hardware-specific code behind adapters.

## Workflow

1. Create a focused branch.
2. Make the smallest coherent change.
3. Run `make check`.
4. Update documentation when public behavior changes.
5. Open a PR with risk, test and rollback notes when the change touches runtime behavior.

## Conventional Commits

Commit messages and PR titles follow Conventional Commits.

Examples:

```text
feat(data): add episode provenance fields
fix(safety): reject non-finite joint commands
research(locomotion): add held-out morphology suite
test(embodiment): cover invalid joint limits
docs: document simulation contract
ci: add static analysis job
```

Allowed common types include `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore` and `research`.

## Definition of done

A production-facing change is not done until:

- tests pass;
- types pass;
- lint passes;
- changed behavior is documented;
- unsafe states fail closed;
- telemetry / observability impact is considered;
- migration or compatibility impact is stated.
