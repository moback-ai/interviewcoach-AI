#!/usr/bin/env bash
# Block production operations from the application repo.
# Runnable only from moback-ai/devsecops-platform (GitHub Actions or DevSecOps local).
#
# DevSecOps workflow must set: env DEVSECOPS_RUN=1
# Emergency local (DevSecOps only): ALLOW_LOCAL_PROD_DEPLOY=1
#
# When sourced from another script, do NOT use `return 0` on success — that exits the caller.

_devsecops_authorized() {
  [[ "${DEVSECOPS_RUN:-}" == "1" ]] && return 0
  [[ "${GITHUB_REPOSITORY:-}" == "moback-ai/devsecops-platform" ]] && return 0
  [[ "${ALLOW_LOCAL_PROD_DEPLOY:-}" == "1" ]] && return 0
  return 1
}

if _devsecops_authorized; then
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    # Run as subprocess — sourcing check-devsecops-actor.sh would exit 0 and abort the caller.
    bash "$(dirname "$0")/check-devsecops-actor.sh"
  fi
else
  cat <<'EOF' >&2
ERROR: Production scripts are DevSecOps-only.

  Do not run infra/prod/scripts from interviewcoach-AI.
  Dev teams: open PR into release/<month>-<year>, pass CI + Security, then ask DevSecOps to build and deploy.

  DevSecOps: moback-ai/devsecops-platform
    Actions → InterviewCoach · Deploy Production

  Copy infra/prod/ to devsecops-platform when scripts change:
    apps/interviewcoach/aws/prod/
EOF
  return 1 2>/dev/null || exit 1
fi
