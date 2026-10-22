# Production Incident Labeling — No Workflows Required

Automatically apply production-incident and severity labels **when issues are created using one of four GitHub issue forms**.

## Quick install (GitHub browser only)

1. In your target repository, open **Issues → Labels**. Create the following exact names (case-sensitive), with the colors shown in `labels.csv`:
   - `Production-Incident`: `F59E0B` (orange)
   - `Prod::Sev1`, `Prod::Sev2`, `Prod::Sev3`, `Prod::Sev4`: `DC2626` (red)
2. Open **Code → Add file → Upload files** (or add each file in GitHub's editor).
3. Upload the five files from `.github/ISSUE_TEMPLATE/` **preserving their directory path**. If the browser upload cannot preserve the hidden folder, create them individually using **Add file → Create new file** with the exact full paths listed below. Alternatively, copy the folder into a local clone using VS Code and commit/push to your default branch.
4. Confirm that the files are on the repository's **default branch** (commonly `main`).
5. Open **Issues → New issue**. Select a production incident severity form, fill required fields, then submit.
6. Verify that BOTH labels appear on the created issue.

GitHub paths:
- `.github/ISSUE_TEMPLATE/01-production-incident-sev1.yml`
- `.github/ISSUE_TEMPLATE/02-production-incident-sev2.yml`
- `.github/ISSUE_TEMPLATE/03-production-incident-sev3.yml`
- `.github/ISSUE_TEMPLATE/04-production-incident-sev4.yml`
- `.github/ISSUE_TEMPLATE/config.yml`

## What is automatic — and what isn't

- **Automatic:** Issue forms add the configured labels when an issue is first created using that form.
- **Not automatic:** Changing a severity described in an issue's text, or editing the issue later, does not change labels. Change the labels manually for reclassification.
- **Not automatic:** Issues opened through Blank issue, REST API, or other unrelated templates do not receive these default labels.
- **Important:** Template YAML does **not create labels**. Labels must exist beforehand. `labels.csv` is a reference, not an automatic import.
- `config.yml` hides the Blank issue option. Remove that file or set `blank_issues_enabled: true` if you need Blank issue alongside these forms.
- Other existing templates are unaffected. Never overwrite an existing `config.yml` without merging its existing `contact_links` and settings.

## Optional label creation with GitHub CLI

If `gh` is already installed and authenticated, from your target repository directory run:

```powershell
gh label create "Production-Incident" --color F59E0B --description "Production incident" --force
1..4 | ForEach-Object { gh label create "Prod::Sev$_" --color DC2626 --description "Production severity $_" --force }
```

This command creates or updates existing labels (including their colors). It is **not needed** when creating labels via the GitHub website.

## Optional local validation

`python tools/validate_package.py` (Python 3.8+, no third-party packages). This checks the files and expected label declarations locally; it does not check GitHub or validate all GitHub YAML schema rules.

## Troubleshooting

- **Templates not visible:** Confirm file extension `.yml`, exact directory `.github/ISSUE_TEMPLATE`, default branch, repository Issues enabled, and that the YAML hasn't been accidentally nested under another directory.
- **Labels not applied:** Create the exact five labels in Issues → Labels, then create a **new** issue from a template. Editing an older issue will not retroactively assign labels.
- **Wrong colors:** Fix label colors in Issues → Labels; template YAML does not control label color.
- **Other templates missing after install:** Check whether an existing `config.yml` was overwritten. Merge the old settings back.
- **Severity changed after reporting:** Manually remove the old severity label and add the new severity label.

GitHub reference: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
