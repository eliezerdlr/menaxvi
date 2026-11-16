# Security Policy

## Supported versions

MENAXVI is currently pre-1.0. Security fixes are provided for the latest tagged
release and the current `main` branch.

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, personal
data, or sensitive customer information.

Use GitHub's **Report a vulnerability** private reporting feature for this
repository. Include:

- affected version or commit;
- impact and required preconditions;
- minimal reproduction steps;
- suggested mitigation, if known;
- whether credentials or personal data may be exposed.

You should receive an initial acknowledgement within five business days. A
validated issue will be prioritized according to impact, exploitability, and
customer exposure. Public disclosure should wait until a fix or documented
mitigation is available.

## Scope

The public runtime, local dashboard, release tooling, schemas, canonical
catalog, examples, and provenance controls are in scope. Private project
operations, local customer data, generated reports, build outputs, and
restricted migration inputs are intentionally excluded from the OSS
repository.

The dashboard is a loopback-only pre-alpha evaluation interface. Do not expose
it directly to an untrusted network or treat its local authentication as a
replacement for production IAM, TLS termination, rate limiting, or managed
secret storage.

For implementation controls and secure-development rules, see
[`docs/governance/SECURITY.md`](docs/governance/SECURITY.md).
