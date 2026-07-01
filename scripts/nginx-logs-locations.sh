#!/usr/bin/env bash
# RETIRED — in-app /logs UI and API routes removed (prod uses AWS CloudWatch).
# Remove any nginx location blocks for /logs/ from prod configs.
echo "# No nginx /logs/ locations — use CloudWatch /interviewcoach/prod/api"
