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

A rollout plan binds the candidate artifact, previous artifact, qualification-report URI, target robots, canary count, batch size, maximum unhealthy fraction, required approvals, optional maintenance window and rollback policy.

## Create a rollout plan

```bash
p37 deploy \
  --artifact p37-v2 \
  --previous p37-v1 \
  --organization acme \
  --site factory-1 \
  --fleet picking \
  --robots robot-1,robot-2,robot-3 \
  --qualification-report artifacts/qualification/qualification.json \
  --qualification-sha256 <trusted-sha256> \
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

Before a rollout plan is created, `p37 deploy` now verifies the qualification report locally. The report must be a full release qualification, have status `qualifies`, contain no unmet gates, match the exact artifact being deployed, and match the trusted SHA-256 supplied on the command line.

The expected digest should come from a trusted release/CI record or signed release metadata, not from the same untrusted location as the report. SHA-256 verifies report integrity against that trusted value; it does not by itself prove signer identity.

Staged integration/simulation/HIL/physical/fleet reports cannot authorize deployment.

Remote report URIs are intentionally not accepted by the deployment gate yet. A remote report should only be supported once P37 has a trusted fetch-and-verification path rather than accepting an unverifiable string.

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

## Approval and maintenance controls

A rollout can require named approval identities before execution:

```bash
p37 deploy \
  --artifact p37-v2 \
  --previous p37-v1 \
  --organization acme \
  --site factory-1 \
  --fleet picking \
  --robots robot-1,robot-2 \
  --qualification-report artifacts/qualification/qualification.json \
  --qualification-sha256 <trusted-sha256> \
  --required-approvals 2 \
  --approval robotics-lead \
  --approval site-ops \
  --maintenance-window-utc "2026-10-05T01:00:00Z"
```

By default, the rollout policy requests rollback when the unhealthy fraction exceeds its configured limit. `--manual-rollback` disables that threshold-triggered automatic policy while preserving explicit stop-request rollback.

The rollout contract records policy; a customer deployment service remains responsible for enforcing the maintenance window and approval identities against the customer's IAM/change-management system.
