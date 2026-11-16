# MENAXVI customer documentation

## Release status

MENAXVI `0.1.0` is an **open-source pre-alpha for local evaluation**. It
provides a dependency-free Python CLI and a loopback-only customer dashboard for
the reviewed campaign-message workflow.

The public repository contains approved MENAXVI source and clean-room canonical
resources only. Restricted migration source and private project evidence are not
part of the OSS distribution.

## Documentation map

- [Tutorial: validate a repository](VALIDATION-TUTORIAL.md)
- [Tutorial: run the reviewed campaign-message workflow](WORKFLOW-TUTORIAL.md)
- [Tutorial: complete the customer dashboard journey](DASHBOARD-TUTORIAL.md)
- [Compatibility matrix](COMPATIBILITY.md)
- [Support and upgrade policy](SUPPORT-AND-UPGRADES.md)
- [Known limitations](LIMITATIONS.md)
- [Runnable example data](../../examples/reviewed-campaign-message/README.md)

## Supported customer journey

1. build the deterministic zipapp or run the CLI from a trusted checkout;
2. diagnose and validate a MENAXVI repository root;
3. open the local dashboard and create a workspace;
4. complete synthetic business-context onboarding;
5. review and approve the workflow plan;
6. execute the bounded local workflow;
7. inspect the artifact and evidence;
8. test controlled failure, retry, rollback, and persistence.

The CLI and dashboard do not call a model, publish content, spend money, use
external credentials, or perform autonomous external actions. The dashboard
binds to `127.0.0.1` by default and stores password hashes and customer state in
a local JSON file selected by the operator.

## Safety and authority

A successful validation result means that the selected policy checks passed. It
does not prove factual accuracy, legal compliance, business effectiveness, or
fitness for direct Internet exposure. The complete source-checkout release gate
remains authoritative.
