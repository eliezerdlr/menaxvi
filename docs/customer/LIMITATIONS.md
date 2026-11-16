# Known limitations

MENAXVI `0.1.0` is an **open-source pre-alpha for local evaluation**. It is not
a hosted service or a complete marketing automation platform.

## Product limitations

- One governed workflow vertical slice is validated.
- The manual adapter performs no autonomous external action.
- The local dashboard is intended for loopback use by one operator; it is not a
  hardened Internet-facing or enterprise identity service.
- There are no production adapters for model providers, email, advertising,
  browsers, CMS platforms, payment systems, or social networks.
- Validation does not prove factual accuracy, legal compliance, business
  effectiveness, or fitness for a particular customer.
- Identical behavior across model providers is not claimed.
- User-supplied content and integrations remain the operator's responsibility.

## Operational limitations

- Dashboard state and generated evidence are local and must be backed up by the
  operator.
- In-memory dashboard sessions do not survive a process restart; persistent
  customer records do.
- PBKDF2 password storage and tenant checks are defense-in-depth for local
  evaluation, not a substitute for production IAM, TLS, rate limiting, audit
  infrastructure, or managed secret storage.
- Local SHA-256 evidence detects changes but is not a digital signature or
  remote attestation.
- The manual recorder validates structure and plan binding but cannot
  independently verify that a human performed the stated review.
- Compatibility is tested on supported Python versions in CI, not every
  operating system or Python implementation.

## Distribution boundary

The public repository and release artifact contain approved MENAXVI source,
canonical resources, synthetic examples, and release tooling. Private project
operations, restricted migration inputs, generated reports, local dashboard
data, and build outputs are intentionally excluded from Git history.

## Safe interpretation

Use this release to evaluate governance, validation, deterministic planning,
human approval, recovery, and evidence contracts. Do not expose the dashboard
directly to the Internet or represent the release as autonomous production
marketing software.
