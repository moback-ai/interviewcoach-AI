#!/usr/bin/env bash
# Block production operations from the application repo.
# Runnable only from moback-ai/devsecops-platform (GitHub Actions or DevSecOps local).
#
# DevSecOps workflow must set: env DEVSECOPS_RUN=1
# Emergency local (DevSecOps only): ALLOW_LOCAL_PROD_DEPLOY=1
if [[ "${DEVSECOPS_RUN:-}" == "1" \
   || "${GITHUB_REPOSITORY:-}" == "moback-ai/devsecops-platform" \
   || "${ALLOW_LOCAL_PROD_DEPLOY:-}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

cat <<'EOF' >&2
ERROR: Production scripts are DevSecOps-only.

  Do not run infra/prod/scripts from interviewcoach-AI.
  Dev teams: merge PR to develop, then ask DevSecOps to deploy.

  DevSecOps: moback-ai/devsecops-platform
    Actions → InterviewCoach · Deploy Production

  Copy infra/prod/ to devsecops-platform when scripts change:
    apps/interviewcoach/aws/prod/
EOF
exit 1
