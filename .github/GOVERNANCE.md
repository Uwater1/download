# Repository Governance

## Responsibilities

- **Maintainer (`@Uwater1`)**: approves changes, owns releases and repository settings, handles security reports, and can make urgent fixes.
- **Data pipeline reviewers**: review download workflows, storage, migration, timestamp, and dataset changes. These paths are protected by `.github/CODEOWNERS`.
- **Contributors**: provide focused pull requests, tests, reproducible reports, and respectful review discussion.

Replace the named owner or add organization teams in `CODEOWNERS` when responsibility changes. Ownership is a review requirement, not a statement that one person must implement every change.

## Personal versus organization repositories

In a personal repository, the owner controls repository settings, branch protection, teams, and security-advisory access. Review responsibility is therefore assigned to the owner account. In an organization repository, those controls can be delegated to organization teams, repository roles, and organization-wide policies; use team handles in `CODEOWNERS` and keep at least two maintainers for continuity.

Moving this repository to an organization should include transferring settings, replacing individual ownership with teams, checking workflow permissions, and confirming who receives private security reports.

## Change and merge rules

Changes should arrive through pull requests, pass the required test workflow, receive the applicable code-owner review, and avoid direct pushes to `main`. Emergency fixes may be made by the maintainer, but should be documented in the follow-up pull request. Data-writing workflows must remain serialized and use least-privilege permissions.

The checked-in ruleset at `.github/rulesets/main.json` is the baseline to import or reproduce in GitHub repository settings. GitHub does not activate a tracked JSON file automatically.