# Enterprise Deployment

P37 separates qualification from rollout. A model artifact should not move into a robot fleet merely because the runtime can load it.

## Deployment hierarchy

The rollout contract targets:

```text
organization
    └── site
         └── fleet
              └── robot IDs
```

A rollout plan binds the candidate artifact, previous artifact, qualification-report URI, target robots, canary count, batch size and maximum unhealthy fraction.

## Create a rollout plan

```bash
p37 deploy \
  --artifact p37-v2 \
  --previous p37-v1 \
  --organization acme \
  --site factory-1 \
  --fleet picking \
  --robots robot-1,robot-2,robot-3 \
  --qualification-report s3://reports/p37-v2/qualification.json \
  --canary-count 1 \
  --batch-size 1 \
  --output artifacts/rollout.json
```

Inspect it:

```bash
p37 status --plan artifacts/rollout.json
```

Create a deterministic rollback plan:

```bash
p37 rollback --plan artifacts/rollout.json --output artifacts/rollback.json
```

These commands create auditable deployment plans. They do **not** bypass customer fleet-management, approval or robot-controller systems.

## Production integration

An enterprise deployment service should:
1. verify the signed model release;
2. verify the referenced qualification report;
3. verify robot compatibility;
4. deploy the canary group;
5. consume runtime health metrics;
6. stop or roll back when policy requires;
7. continue through batches only after approval/health gates;
8. record every promotion and rollback event.

The repository implements the rollout contract and health/rollback policy. Live production fleet execution remains environment-specific qualification work.
