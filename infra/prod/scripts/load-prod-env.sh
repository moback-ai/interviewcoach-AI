#!/usr/bin/env bash
# Source prod.env from infra/prod/ (safe — no secrets in that file).
_load_prod_env_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${_load_prod_env_dir}/prod.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${_load_prod_env_dir}/prod.env"
  set +a
fi
unset _load_prod_env_dir
