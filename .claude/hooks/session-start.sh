#!/bin/bash
# Cloud container is ephemeral: re-apply REA registration and the ponytail status line each session.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Pinned to the version that was reviewed; bump deliberately.
npx -y rea-agents@6.5.0 setup --all-detected --yes >/dev/null 2>&1 \
  || echo "session-start: REA setup failed, continuing without it" >&2

# Only point at the status line script if the ponytail plugin installed it; merge, never overwrite.
script="$HOME/.claude/ponytail-statusline.sh"
if [ -f "$script" ]; then
  python3 - "$HOME/.claude/settings.json" "$script" <<'PY'
import json, os, sys
path, script = sys.argv[1], sys.argv[2]
data = json.load(open(path)) if os.path.exists(path) else {}
data["statusLine"] = {"type": "command", "command": f'bash "{script}"'}
json.dump(data, open(path, "w"), indent=2)
PY
fi
