#!/usr/bin/env bash
# Source prod.env from infra/prod/ (safe — no secrets in that file).
# Caller-provided IMAGE_TAG / ECR_REGISTRY win (GitHub Actions sets these at deploy time).
_load_prod_env_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_saved_image_tag="${IMAGE_TAG-}"
_saved_ecr_registry="${ECR_REGISTRY-}"
if [[ -f "${_load_prod_env_dir}/prod.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${_load_prod_env_dir}/prod.env"
  set +a
fi
[[ -n "$_saved_image_tag" ]] && IMAGE_TAG="$_saved_image_tag"
[[ -n "$_saved_ecr_registry" ]] && ECR_REGISTRY="$_saved_ecr_registry"
unset _load_prod_env_dir _saved_image_tag _saved_ecr_registry
