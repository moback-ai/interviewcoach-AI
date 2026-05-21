#!/usr/bin/env bash
# Audit backend/requirements.txt; ignore ML CVEs with no PyPI fix yet (see pyproject.toml).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v pip-audit >/dev/null 2>&1; then
  python3 -m pip install --upgrade pip pip-audit >/dev/null
fi

IGNORE_ARGS=()
while IFS= read -r vuln_id; do
  [[ -z "$vuln_id" ]] && continue
  IGNORE_ARGS+=(--ignore-vuln "$vuln_id")
done < <(python3 - <<'PY'
import re
from pathlib import Path

text = Path("pyproject.toml").read_text()
block = re.search(r"ignore-vulns\s*=\s*\[(.*?)\]", text, re.S)
if not block:
    raise SystemExit("ignore-vulns not found in pyproject.toml")
for line in block.group(1).splitlines():
    m = re.search(r'"([^"]+)"', line)
    if m:
        print(m.group(1))
PY
)

echo "Running pip-audit (${#IGNORE_ARGS[@]} accepted-risk ignores for unfixed ML CVEs)..."
pip-audit -r backend/requirements.txt --progress-spinner off --desc on "${IGNORE_ARGS[@]}"
