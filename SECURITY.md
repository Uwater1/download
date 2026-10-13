# Security Policy

## Supported versions

Only the `main` branch is currently maintained. Older snapshots and downloaded datasets do not receive security fixes.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's **Report a vulnerability** action on the repository's Security tab to start a private advisory. Include:

- affected file, workflow, or dependency and the commit or version;
- reproducible steps or a minimal proof of concept;
- impact and any required permissions or secrets;
- a suggested mitigation, if known.

If private reporting is unavailable, contact the repository owner through the email listed on the owner's GitHub profile and do not include secrets in the initial message.

The maintainer will acknowledge a report within 7 days, assess severity and affected versions, and coordinate a fix or mitigation before public disclosure. Please allow a reasonable remediation window; urgent active exploitation should be identified clearly.

## Dependency and workflow updates

Dependabot checks Python dependencies weekly. Maintainers review those pull requests, run the test workflow, and merge security updates promptly after checking compatibility. Workflow action updates require the same review and must preserve least-privilege permissions. Rotate any exposed credential immediately and remove it from repository history where appropriate.