#!/usr/bin/env bash
# Deprecated — PROD uses ASG rollouts. Redirects to 06-code-deploy-api-asg.sh
# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
exec bash "$(dirname "$0")/06-code-deploy-api-asg.sh" "$@"
