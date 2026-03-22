#!/usr/bin/env bash
set -euo pipefail

HOST_HEADER="${HOST_HEADER:-ai-lab.localhost}"
BASE_URL="${BASE_URL:-http://localhost:8080/ask}"
CONCURRENCY="${CONCURRENCY:-20}"
TOTAL_REQUESTS="${TOTAL_REQUESTS:-400}"
TOP_K="${TOP_K:-3}"

send_request() {
  local question="$1"
  curl -sS \
    -H "Host: ${HOST_HEADER}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg question "$question" --argjson top_k "$TOP_K" '{question: $question, top_k: $top_k}')" \
    "${BASE_URL}" >/dev/null
}

export HOST_HEADER BASE_URL TOP_K
export -f send_request

printf 'target=%s host=%s concurrency=%s total_requests=%s\n' \
  "${BASE_URL}" "${HOST_HEADER}" "${CONCURRENCY}" "${TOTAL_REQUESTS}"

seq 1 "${TOTAL_REQUESTS}" | xargs -I{} -P "${CONCURRENCY}" bash -lc '
  questions=(
    "What operational value did the Trivy and smoke-test notes describe?"
    "What did the observability baseline say about service indicators?"
    "What happened in the guestbook readiness failure drill?"
    "What did the ETL modernization writeup emphasize?"
  )
  index=$(( RANDOM % ${#questions[@]} ))
  send_request "${questions[$index]}"
'

echo "Load run complete."
echo "Watch scaling with:"
echo "  kubectl get hpa -n ai-lab -w"
echo "  kubectl get pods -n ai-lab -w"
