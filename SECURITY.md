# Security Policy

P37 Neuro controls and learns from physical systems. Treat security issues that can affect robot behavior, model artifacts, data integrity or deployment credentials as high impact.

## Report vulnerabilities privately

Do **not** report exploitable vulnerabilities in public GitHub issues.

Use the repository's GitHub **Security → Report a vulnerability** flow when available. This keeps the report private through GitHub Security Advisories.

If that route is not available for your account, contact **engineering@ontos.ws** and state that the message concerns a private P37 security report. Do not include production credentials or private keys in the first message.

Include:
- affected component and version/commit;
- reproduction steps;
- potential physical or data impact;
- whether credentials, model artifacts or hardware are exposed;
- suggested mitigation if known.

## Security boundaries

The repository assumes:
- actuator commands pass through an independent deterministic safety layer;
- secrets are injected at deployment time;
- training data provenance and governance metadata are retained;
- model artifacts are integrity-checked before deployment;
- signed release manifests are verified before promotion;
- production robots do not execute arbitrary repository code directly from untrusted branches;
- customer fleet systems retain independent authentication, authorization and emergency-stop authority.

See `docs/safety.md` for the physical-system safety boundary.

## Response expectations

Reports are triaged by severity and physical-system impact. We will acknowledge a valid private report, preserve confidentiality during remediation, and coordinate disclosure when a fix is available.

Do not include production credentials, raw customer sensor data, or information that could cause unsafe physical operation unless it is strictly necessary to reproduce the issue.
