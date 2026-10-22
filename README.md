# Production Incident GitHub App — runner-free auto-labeling

This standalone Python service receives GitHub App webhooks and synchronizes issue labels using GitHub REST API. **No GitHub Actions workflow or GitHub-hosted runner is used.** It works across multiple repositories in which the App is installed.

## Behavior

- An issue titled `[Prod][Incident] ...` with a Markdown issue-form section `### Production Severity` containing `S1`, `S2`, `S3`, or `S4` is recognized.
- Applies `Production-Incident` (orange `F28C28`) and exactly one of `Prod::Sev1` ... `Prod::Sev4` (red `B60205`).
- Creates missing labels or repairs colors in the repository. Removes outdated *recognized* severity labels while preserving unrelated labels.
- Listens to `issues` events with actions `opened`, `edited`, `reopened`; fetches the latest issue state to avoid stale webhook content.
- Notifies via structured HTTP status and server logging. GitHub may display label badges in its own order.

## GitHub App registration

1. GitHub → **Settings → Developer settings → GitHub Apps → New GitHub App**. For an organization-owned App, use organization settings instead.
2. Give the App a unique name. Set **Webhook URL** to `https://YOUR_PUBLIC_HOST/webhook`, **Webhook secret** to a long random value, and **Active** on. HTTPS is required for a secure public deployment.
3. Under **Repository permissions**, choose **Issues: Read & write** and **Metadata: Read-only** (metadata is standard). No Actions permission is required.
4. Subscribe to the **Issues** webhook event. Only issues opened/edited/reopened are processed by the service.
5. Save the App, copy its **App ID**, and generate/download a **private key (.pem)**. Store it privately; do not commit it to Git.
6. **Install App** into the target repository (or choose multiple repositories). Note its installation ID from its installation URL or installation API.

GitHub App permissions and webhook event availability are controlled by the organization/repository administrator. If you lack permission to install Apps, ask that administrator.

## Deploy with Docker (external Linux server, VM, or hosting provider)

Requires an always-reachable HTTPS URL and a host capable of running containers. The included container listens on port 8080; put an HTTPS reverse proxy / cloud load balancer in front of it.

```bash
cp .env.example .env
# Edit .env: real App ID and webhook secret
# Put the downloaded GitHub App key at ./private-key.pem
chmod 600 private-key.pem
docker compose up -d --build
curl http://127.0.0.1:8080/health
```

Expose `https://YOUR_PUBLIC_HOST/webhook` using your existing HTTPS reverse proxy. For local experimentation, a trusted HTTPS tunnel to localhost can be used, but a persistent host is required for reliable automatic processing.

**Secrets:** `.env` and `private-key.pem` must never be pushed to GitHub or published in container images. Rotate them if exposed. Keep the service private except for the HTTPS webhook endpoint; use the supplied signature validation for every webhook delivery.

## Local Python (without Docker)

```bash
python -m venv .venv
# Activate .venv (Windows: .venv\\Scripts\\activate ; Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
# Configure GITHUB_APP_ID, GITHUB_WEBHOOK_SECRET and GITHUB_PRIVATE_KEY_PATH
python -m flask --app app run --host 127.0.0.1 --port 8080
```

Local Flask's built-in server is for development only; production uses Gunicorn or another production server.

## Initialize labels or backfill an existing issue

With the App installed and environment configured, run from the same environment as the service:

```bash
python manage.py --installation-id 123456 --repo OWNER/REPO
python manage.py --installation-id 123456 --repo OWNER/REPO --issue 1176
```

Inside Docker, example:

```bash
docker compose exec incident-labeler python manage.py --installation-id 123456 --repo OWNER/REPO --issue 1176
```

The installation ID is **not** the App ID. Replace example values with your actual ones. New issues are labeled automatically; the manual management command is only for initialization or old issues.

## Verify and troubleshoot

1. Verify `https://YOUR_PUBLIC_HOST/health` reports `{"status":"ok"}`.
2. In GitHub App settings, open **Advanced → Recent Deliveries**. A `ping` should return 200. The Issues webhook for a test issue should return 200 with `synced Prod::SevN`.
3. Create a test issue using the Production Incident template; verify orange `Production-Incident` and red `Prod::SevN` under **Issues → Labels**.
4. Change the selected severity by editing the issue body. The next `issues.edited` delivery should switch labels. Editing the issue-form Markdown content will trigger this event; editing labels manually does not automatically reapply the intended severity.
5. Check `docker compose logs -f incident-labeler` for errors.

Troubleshooting: **401** means invalid/missing webhook signature or secret; **503** means GitHub API/token/permissions error (inspect server logs); **ignored/skipped** means the event or title/body doesn't match; missing deliveries mean webhook URL, event subscription, network firewall, or installation problems. Re-deliver a failed webhook from the GitHub App's delivery history after correcting the problem.

## Security and operational notes

- Signature is checked with HMAC-SHA256 over the raw payload before processing.
- GitHub App JWT and short-lived installation token are generated server-side using the private key.
- No arbitrary repository selection is accepted from unsigned requests.
- The sync operation is **idempotent** for the same issue content. It fetches current issue state, but concurrent issue edits could still race; for larger production workloads add a durable queue and per-issue serialization.
- Don't expose `/webhook` without HTTPS and signature verification. Do not log tokens/private keys.
- Intended for GitHub.com; `GITHUB_API_URL` can be configured for GitHub Enterprise Server, subject to API compatibility.

## Contents

`app.py`: webhook server and GitHub API label synchronization; `manage.py`: label initialization/backfill; `Dockerfile`, `compose.yaml`, `.env.example`: deployment; `tests/`: basic unit tests.

## Optional issue form

`.github/ISSUE_TEMPLATE/ProdIncid.yml` is a compatible issue form reflecting the established Production Incident fields. Copy it into the **target repository** only if you need to install/replace the issue form; if your current form already matches, leave it untouched. The App itself should be hosted separately from the repository.

**Note on containers:** For the ready-to-run Docker Compose example, the server process must be able to read the bind-mounted private key; the sample runs as the container's default user. For stricter production security, configure a non-root execution identity and a secrets mount with corresponding file ownership/permissions in your hosting platform. Protect the Docker host and secret files.
