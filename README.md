# Production Incident GitHub App — runner-free auto-labeling

This standalone Python service receives GitHub App webhooks and synchronizes issue labels using GitHub REST API. **No GitHub Actions workflow or GitHub-hosted runner is used.** It works across multiple repositories in which the App is installed.

## Behavior

- An issue titled `[Prod][Incident] ...` with a Markdown issue-form section `### Production Severity` containing `S1`, `S2`, `S3`, or `S4` is recognized.
- Applies `Production-Incident` (orange `F28C28`) and exactly one of `Prod::Sev1` ... `Prod::Sev4` (red `B60205`).
- Creates missing labels or repairs colors in the repository. Removes outdated *recognized* severity labels while preserving unrelated labels.
- Listens to `issues` events with actions `opened`, `edited`, `reopened`; fetches the latest issue state to avoid stale webhook content.
- Notifies via structured HTTP status and server logging. GitHub may display label badges in its own order.
