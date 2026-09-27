# Security Policy

P37 Neuro controls and learns from physical systems. Treat security issues that can affect robot behavior, model artifacts, data integrity or deployment credentials as high impact.

## Do not report exploitable vulnerabilities in public issues

Report security-sensitive findings privately to the Ontos World maintainers through the organization's established private security channel.

Include:

- affected component and version/commit;
- reproduction steps;
- potential physical or data impact;
- whether credentials, model artifacts or hardware are exposed;
- suggested mitigation if known.

## Security boundaries

The repository assumes:

- actuator commands pass through an independent safety layer;
- secrets are injected at deployment time;
- training data provenance is retained;
- model artifacts are integrity-checked before deployment;
- production robots do not execute arbitrary repository code directly from untrusted branches.
