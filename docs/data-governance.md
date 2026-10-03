# Enterprise Data Governance

P37 robot data can contain proprietary site information, people, customer processes and safety-sensitive machine state. Data-use policy is represented explicitly alongside an episode rather than inferred from storage location.

## Policy fields

`DataGovernancePolicy` records:
- customer ID;
- site ID;
- data region;
- classification;
- whether training is permitted;
- raw-sensor retention in hours;
- whether personal data may be present;
- allowed purposes such as evaluation or training.

Example:

```yaml
customer_id: customer-a
site_id: factory-01
region: eu-west
classification: confidential
training_allowed: false
raw_sensor_retention_hours: 24
contains_personal_data: true
allowed_purposes:
  - evaluation
```

## Enforcement

`evaluate_data_use()` and `require_episode_use()` can reject:
- a purpose that was not approved;
- training when training permission is false;
- transfer to a different region under the default region-bound policy.

Governance metadata can be embedded in canonical episode metadata so it survives collection, review and dataset lineage.

## Enterprise responsibility

P37 provides policy-enforcement primitives; the deploying organization remains responsible for legal, contractual, privacy and retention requirements. Storage lifecycle and deletion workflows must be configured in the deployment environment.

The existence of an episode is never treated as permission to train on it.
