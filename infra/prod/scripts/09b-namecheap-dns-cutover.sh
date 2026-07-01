#!/usr/bin/env bash
# Point ugaanlabs.ai DNS at CloudFront via Namecheap API (preserves email forwarding MX).
#
# Prereqs (Namecheap → Profile → Tools → API Access):
#   - Enable API access
#   - Whitelist your public IP (curl https://api.ipify.org)
#
# Usage:
#   NAMECHEAP_API_USER=youruser \
#   NAMECHEAP_API_KEY=... \
#   NAMECHEAP_USERNAME=youruser \
#   bash infra/prod/scripts/09b-namecheap-dns-cutover.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

API_USER="${NAMECHEAP_API_USER:-}"
API_KEY="${NAMECHEAP_API_KEY:-}"
USERNAME="${NAMECHEAP_USERNAME:-$API_USER}"
CLIENT_IP="${NAMECHEAP_CLIENT_IP:-$(curl -fsS https://api.ipify.org)}"
DOMAIN="${FRONTEND_DOMAIN:-ugaanlabs.ai}"
SLD="${DOMAIN%%.*}"
TLD="${DOMAIN#*.}"
STACK="${CF_STACK_NAME:-interviewcoach-prod-cloudfront}"
REGION="${AWS_REGION:-ap-south-1}"
CF_DOMAIN="${CF_DOMAIN_OVERRIDE:-}"

if [[ -z "$API_USER" || -z "$API_KEY" ]]; then
  echo "Set NAMECHEAP_API_USER and NAMECHEAP_API_KEY (see script header)."
  exit 1
fi

if [[ -z "$CF_DOMAIN" ]]; then
  CF_DOMAIN=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='DistributionDomainName'].OutputValue" --output text 2>/dev/null || true)
fi
if [[ -z "$CF_DOMAIN" || "$CF_DOMAIN" == "None" ]]; then
  echo "CloudFront domain unknown. Run 09-code-cloudfront-deploy.sh first."
  exit 1
fi

API_BASE="https://api.namecheap.com/xml.response"
QS="ApiUser=${API_USER}&ApiKey=${API_KEY}&UserName=${USERNAME}&ClientIp=${CLIENT_IP}"

echo "Domain:      ${DOMAIN}"
echo "CloudFront:  ${CF_DOMAIN}"
echo "Client IP:   ${CLIENT_IP} (must be whitelisted in Namecheap API settings)"
echo ""

get_hosts_xml=$(curl -fsS "${API_BASE}?${QS}&Command=namecheap.domains.dns.getHosts&SLD=${SLD}&TLD=${TLD}")
if ! echo "$get_hosts_xml" | grep -q 'Status="OK"'; then
  echo "getHosts failed:"
  echo "$get_hosts_xml" | sed -n '1,40p'
  exit 1
fi

json_body=$(SLD="$SLD" TLD="$TLD" GET_HOSTS_XML="$get_hosts_xml" CF_DOMAIN="$CF_DOMAIN" python3 <<'PY'
import json, os, xml.etree.ElementTree as ET

root = ET.fromstring(os.environ["GET_HOSTS_XML"])
ns = {"n": "http://api.namecheap.com/xml.response"}
cf = os.environ["CF_DOMAIN"].rstrip(".")
records = []

def add(host, rtype, addr, ttl="300", mxpref="10"):
    records.append({
        "host": host, "type": rtype,
        "addr": addr.rstrip("."), "ttl": str(ttl or "300"), "mxpref": str(mxpref or "10"),
    })

preserve = {"MX", "TXT", "CAA", "NS"}
for h in root.findall(".//n:host", ns):
    host, rtype, addr = h.get("Name", ""), h.get("Type", ""), h.get("Address", "")
    if host == "@" and rtype == "A":
        continue
    if host == "www" and rtype in {"A", "CNAME", "ALIAS", "URL", "URL301"}:
        continue
    if rtype in preserve:
        add(host, rtype, addr, h.get("TTL", "1800"), h.get("MXPref", "10"))

add("@", "ALIAS", cf, "300")
add("www", "CNAME", cf, "300")

req = []
for i, rec in enumerate(records, start=1):
    req += [
        {"Key": f"HostName{i}", "Value": rec["host"]},
        {"Key": f"RecordType{i}", "Value": rec["type"]},
        {"Key": f"Address{i}", "Value": rec["addr"]},
        {"Key": f"TTL{i}", "Value": rec["ttl"]},
    ]
    if rec["type"] == "MX":
        req.append({"Key": f"MXPref{i}", "Value": rec["mxpref"]})

print(json.dumps({"RequestValues": req, "SLD": os.environ["SLD"], "TLD": os.environ["TLD"]}))
PY
)

echo "Setting DNS (@ ALIAS + www CNAME → ${CF_DOMAIN}, preserving MX/TXT) ..."
set_hosts_xml=$(curl -fsS -X POST "${API_BASE}?${QS}&Command=namecheap.domains.dns.setHosts" \
  -H "Content-Type: application/json" \
  -d "$json_body")

if ! echo "$set_hosts_xml" | grep -q 'IsSuccess="true"'; then
  echo "setHosts failed:"
  echo "$set_hosts_xml" | sed -n '1,60p'
  exit 1
fi

echo "Namecheap DNS updated."
echo "Waiting for propagation (up to 10 min) ..."
for i in $(seq 1 60); do
  if curl -fsS --max-time 10 "https://${DOMAIN}/api/health" >/dev/null 2>&1; then
    health=$(curl -fsS "https://${DOMAIN}/api/health" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status'), d.get('services',{}).get('stt',{}).get('chain'))" 2>/dev/null || echo "ok")
    echo "Cutover OK (~$((i * 10))s): https://${DOMAIN}/api/health → ${health}"
    exit 0
  fi
  echo "[$i/60] waiting for https://${DOMAIN} ..."
  sleep 10
done

echo "DNS set in Namecheap but not fully propagated yet."
echo "Check: curl -fsS https://${DOMAIN}/api/health"
exit 1
