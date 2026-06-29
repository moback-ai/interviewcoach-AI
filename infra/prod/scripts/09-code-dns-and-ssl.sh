#!/usr/bin/env bash
# Wait for DNS A record → prod EC2, then enable HTTPS (Let's Encrypt).
# Usage: bash infra/prod/scripts/09-code-dns-and-ssl.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

DOMAIN="${FRONTEND_DOMAIN:-ugaanlabs.ai}"
API_IP="${API_PUBLIC_IP:-${API_HOST#*@}}"
OLD_IP="${OLD_DNS_IP:-3.110.248.130}"

echo "=== DNS cutover for ${DOMAIN} ==="
echo ""
echo "At your domain registrar (nameservers: dns1.registrar-servers.com):"
echo "  1. Open DNS / Advanced DNS for ${DOMAIN}"
echo "  2. Set A record @ (root)  → ${API_IP}"
echo "  3. Set A record www       → ${API_IP}  (or CNAME www → ${DOMAIN})"
echo "  4. Remove or update any A record still pointing to ${OLD_IP}"
echo ""
echo "Test stack now (before DNS): http://${API_IP}/"
echo ""

for i in $(seq 1 60); do
  RESOLVED=$(dig +short "${DOMAIN}" A | head -1)
  if [[ "$RESOLVED" == "${API_IP}" ]]; then
    echo "DNS OK (${DOMAIN} → ${API_IP}) after ~$((i * 10))s wait."
    bash "$(dirname "$0")/09-code-enable-ssl.sh"
    echo ""
    echo "=== Prod live ==="
    echo "  https://${DOMAIN}/"
    echo "  https://${DOMAIN}/api/health"
    exit 0
  fi
  echo "[$i/60] DNS still ${RESOLVED:-<empty>} (need ${API_IP}) — waiting 10s ..."
  sleep 10
done

echo "DNS not updated after 10 minutes."
echo "Update the A record at your registrar, then run:"
echo "  bash infra/prod/scripts/09-code-enable-ssl.sh"
exit 1
