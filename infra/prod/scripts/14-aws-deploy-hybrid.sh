#!/usr/bin/env bash
# Deprecated wrapper — use 14-aws-deploy-prod-compute.sh
# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
exec bash "$(dirname "$0")/14-aws-deploy-prod-compute.sh" "$@"
