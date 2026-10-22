"""GitHub App webhook service: production incident category and severity labels."""
import hashlib
import hmac
import logging
import os
import re
import time
from pathlib import Path

import jwt
import requests
from flask import Flask, jsonify, request

LOG = logging.getLogger('incident-labeler')
CATEGORY = 'Production-Incident'
CATEGORY_COLOR = 'F28C28'
SEVERITIES = {str(n): f'Prod::Sev{n}' for n in range(1, 5)}
RED = 'B60205'
API = os.getenv('GITHUB_API_URL', 'https://api.github.com').rstrip('/')
HTTP_TIMEOUT = 12


def extract_severity(body):
    """Read issue-form's Production Severity markdown heading, ignoring other fields."""
    match = re.search(r'(?im)^\s*#{1,6}\s+Production Severity\s*$\s*\n+\s*(S[1-4])\s*(?:\n|$)', body or '')
    return match.group(1)[1] if match else None


def is_incident(issue):
    # Never modify unrelated issues merely because they mention an S1/S2 etc.
    return bool(re.match(r'^\[Prod\]\[Incident\]', issue.get('title', ''), re.I)) and bool(extract_severity(issue.get('body', '')))


def verify_signature(body, signature, secret):
    if not secret or not signature or not signature.startswith('sha256='):
        return False
    expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def private_key():
    pem = os.getenv('GITHUB_PRIVATE_KEY', '').replace('\\n', '\n')
    if pem:
        return pem
    path = os.getenv('GITHUB_PRIVATE_KEY_PATH', '')
    if not path:
        raise RuntimeError('Set GITHUB_PRIVATE_KEY_PATH or GITHUB_PRIVATE_KEY')
    return Path(path).read_text(encoding='utf-8')


def installation_token(installation_id):
    app_id = os.environ['GITHUB_APP_ID']
    now = int(time.time())
    token = jwt.encode({'iat': now - 60, 'exp': now + 540, 'iss': app_id}, private_key(), algorithm='RS256')
    response = requests.post(f'{API}/app/installations/{int(installation_id)}/access_tokens',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28'}, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()['token']


class GitHub:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                                     'X-GitHub-Api-Version': '2022-11-28'})

    def call(self, method, path, **kwargs):
        response = self.session.request(method, f'{API}{path}', timeout=HTTP_TIMEOUT, **kwargs)
        if response.status_code >= 400:
            LOG.error('GitHub API %s %s returned %s: %s', method, path, response.status_code, response.text[:400])
        response.raise_for_status()
        return response.json() if response.content else None

    def issue(self, repo, number):
        return self.call('GET', f'/repos/{repo}/issues/{number}')

    def labels(self, repo):
        # All requested labels are accessed by exact name, no pagination needed.
        labels = {}
        for name in [CATEGORY, *SEVERITIES.values()]:
            r = self.session.get(f'{API}/repos/{repo}/labels/{requests.utils.quote(name, safe="")}', timeout=HTTP_TIMEOUT)
            if r.status_code == 404:
                labels[name] = None
            else:
                r.raise_for_status()
                labels[name] = r.json()
        return labels

    def ensure_labels(self, repo):
        desired = {CATEGORY: (CATEGORY_COLOR, 'Production incident'),
                   **{name: (RED, f'Production incident severity {sev}') for sev, name in SEVERITIES.items()}}
        existing = self.labels(repo)
        for name, (color, description) in desired.items():
            if existing[name] is None:
                self.call('POST', f'/repos/{repo}/labels', json={'name': name, 'color': color, 'description': description})
            elif existing[name].get('color', '').upper() != color:
                encoded = requests.utils.quote(name, safe='')
                self.call('PATCH', f'/repos/{repo}/labels/{encoded}', json={'color': color})

    def sync_issue(self, repo, number, issue=None):
        issue = issue or self.issue(repo, number)
        if 'pull_request' in issue or not is_incident(issue):
            return 'skipped (not a matching production incident)'
        sev = extract_severity(issue['body'])
        wanted = SEVERITIES[sev]
        self.ensure_labels(repo)
        current = {x['name'] for x in issue.get('labels', [])}
        # Only remove recognized severity labels. Preserve category and unrelated labels.
        for old in SEVERITIES.values():
            if old != wanted and old in current:
                self.call('DELETE', f'/repos/{repo}/issues/{number}/labels/{requests.utils.quote(old, safe="")}')
        missing = [label for label in [CATEGORY, wanted] if label not in current]
        if missing:
            self.call('POST', f'/repos/{repo}/issues/{number}/labels', json={'labels': missing})
        return f'synced {wanted}'


def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024  # one MiB max payload

    @app.get('/health')
    def health():
        return jsonify(status='ok')

    @app.post('/webhook')
    def webhook():
        raw = request.get_data()
        if not verify_signature(raw, request.headers.get('X-Hub-Signature-256'), os.getenv('GITHUB_WEBHOOK_SECRET', '')):
            return jsonify(error='invalid signature'), 401
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error='invalid JSON'), 400
        event = request.headers.get('X-GitHub-Event')
        if event == 'ping':
            return jsonify(status='pong')
        if event != 'issues' or payload.get('action') not in ('opened', 'edited', 'reopened'):
            return jsonify(status='ignored')
        installation = payload.get('installation') or {}
        repo = (payload.get('repository') or {}).get('full_name')
        issue = payload.get('issue') or {}
        if not installation.get('id') or not repo or not issue.get('number'):
            return jsonify(error='missing installation/repository/issue'), 400
        # Fetch current issue from GitHub to avoid stale/out-of-order webhook bodies.
        try:
            client = GitHub(installation_token(installation['id']))
            result = client.sync_issue(repo, int(issue['number']))
        except Exception:
            LOG.exception('Unable to synchronize %s#%s', repo, issue['number'])
            return jsonify(error='synchronization failed; retry delivery'), 503
        LOG.info('%s#%s: %s', repo, issue['number'], result)
        return jsonify(status=result)
    return app


app = create_app()
