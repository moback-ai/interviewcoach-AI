#!/usr/bin/env bash
# Deprecated wrapper — use 14-aws-deploy-prod-compute.sh
exec bash "$(dirname "$0")/14-aws-deploy-prod-compute.sh" "$@"
