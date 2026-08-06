#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NETPLAN_SOURCE="${PROJECT_ROOT}/infra/gtm_advisor_legacy_ip.yaml"
NETPLAN_TARGET="/etc/netplan/10-gtm-advisor-legacy-ip.yaml"
LEGACY_IP="192.168.1.28/24"
INTERFACE="eno1"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo $0"
  exit 1
fi

if ! ip link show "${INTERFACE}" >/dev/null 2>&1; then
  echo "Network interface ${INTERFACE} was not found."
  exit 1
fi

if ! ip address show dev "${INTERFACE}" | grep -q "192.168.1.28/24"; then
  ip address add "${LEGACY_IP}" dev "${INTERFACE}"
fi

install -m 0644 "${NETPLAN_SOURCE}" "${NETPLAN_TARGET}"
netplan generate
netplan apply

echo "Added persistent secondary address ${LEGACY_IP} on ${INTERFACE}."
echo "Verify with: ip -br addr show ${INTERFACE}"
