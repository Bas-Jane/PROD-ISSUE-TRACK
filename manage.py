"""Initialize repository labels or synchronize an old incident without Actions."""
import argparse
from app import GitHub, installation_token

parser = argparse.ArgumentParser()
parser.add_argument('--installation-id', type=int, required=True)
parser.add_argument('--repo', required=True, help='OWNER/REPO')
parser.add_argument('--issue', type=int, help='Optional existing issue to synchronize')
args = parser.parse_args()
if args.repo.count('/') != 1:
    parser.error('--repo must be OWNER/REPO')
client = GitHub(installation_token(args.installation_id))
client.ensure_labels(args.repo)
print('Repository labels created/updated')
if args.issue:
    print(client.sync_issue(args.repo, args.issue))
