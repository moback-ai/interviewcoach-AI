#!/usr/bin/env bash
# Create or update AWS monthly cost budget alert at $550 (USD)
#
# Usage: ./set-budget-alert.sh [--apply]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"

LIMIT_USD="${BUDGET_LIMIT_USD:-550}"
EMAIL="${BUDGET_ALERT_EMAIL:-}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
BUDGET_NAME="interviewcoach-monthly-550"

if [[ -z "$EMAIL" ]]; then
  EMAIL="$(aws iam list-account-aliases --query 'AccountAliases[0]' --output text 2>/dev/null || true)"
  EMAIL="${BUDGET_ALERT_EMAIL:-govardhan@ugaanlabs.ai}"
fi

TMP="$(mktemp)"
cat >"$TMP" <<JSON
{
  "BudgetName": "${BUDGET_NAME}",
  "BudgetLimit": { "Amount": "${LIMIT_USD}", "Unit": "USD" },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST",
  "CostFilters": {},
  "CostTypes": {
    "IncludeTax": true,
    "IncludeSubscription": true,
    "UseBlended": false
  }
}
JSON

NOTIFY="$(mktemp)"
cat >"$NOTIFY" <<JSON
[
  {
    "NotificationType": "ACTUAL",
    "ComparisonOperator": "GREATER_THAN",
    "Threshold": 80,
    "ThresholdType": "PERCENTAGE",
    "NotificationState": "ALARM"
  },
  {
    "NotificationType": "FORECASTED",
    "ComparisonOperator": "GREATER_THAN",
    "Threshold": 100,
    "ThresholdType": "PERCENTAGE",
    "NotificationState": "ALARM"
  }
]
JSON

SUBS="$(mktemp)"
cat >"$SUBS" <<JSON
[
  {
    "SubscriptionType": "EMAIL",
    "Address": "${EMAIL}"
  }
]
JSON

echo "Budget: \$${LIMIT_USD}/month | Alerts to: ${EMAIL}"

if [[ "$APPLY" -ne 1 ]]; then
  echo "DRY-RUN: aws budgets create-budget / create-notification / create-subscriber"
  rm -f "$TMP" "$NOTIFY" "$SUBS"
  exit 0
fi

if aws budgets describe-budget --account-id "$ACCOUNT_ID" --budget-name "$BUDGET_NAME" &>/dev/null; then
  aws budgets update-budget --account-id "$ACCOUNT_ID" --new-budget "file://${TMP}"
else
  aws budgets create-budget --account-id "$ACCOUNT_ID" --budget "file://${TMP}"
fi

aws budgets delete-notification \
  --account-id "$ACCOUNT_ID" --budget-name "$BUDGET_NAME" \
  --notification ACTUAL_GreaterThan_80 2>/dev/null || true

for i in 0 1; do
  aws budgets create-notification \
    --account-id "$ACCOUNT_ID" \
    --budget-name "$BUDGET_NAME" \
    --notification "$(python3 -c "import json; print(json.dumps(json.load(open('$NOTIFY'))[$i]))")" \
    --subscribers "file://${SUBS}" 2>/dev/null || true
done

echo "Budget alert configured."
rm -f "$TMP" "$NOTIFY" "$SUBS"
