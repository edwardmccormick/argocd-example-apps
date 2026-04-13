#!/usr/bin/env bash
set -euo pipefail

HOST_HEADER="${HOST_HEADER:-ai-lab.localhost}"
BASE_URL="${BASE_URL:-http://localhost:8080/ask}"
CONCURRENCY="${CONCURRENCY:-20}"
TOTAL_REQUESTS="${TOTAL_REQUESTS:-400}"
TOP_K="${TOP_K:-3}"
RESULTS_FILE="${RESULTS_FILE:-load_results.log}"

: > "$RESULTS_FILE"

send_request() {
  local question="$1"

  curl -sS \
    --connect-timeout 3 \
    --max-time 15 \
    -o /dev/null \
    -w '%{http_code} %{time_total}\n' \
    -H "Host: ${HOST_HEADER}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg question "$question" --argjson top_k "$TOP_K" '{question: $question, top_k: $top_k}')" \
    "${BASE_URL}"
}

export HOST_HEADER BASE_URL TOP_K
export -f send_request

printf 'target=%s host=%s concurrency=%s total_requests=%s\n' \
  "${BASE_URL}" "${HOST_HEADER}" "${CONCURRENCY}" "${TOTAL_REQUESTS}"

seq 1 "${TOTAL_REQUESTS}" | xargs -P "${CONCURRENCY}" -n 1 bash -c '
  set -euo pipefail
  questions=(
    "What operational value did the Trivy and smoke-test notes describe?"
    "What did the observability baseline say about service indicators?"
    "What happened in the guestbook readiness failure drill?"
    "What did the ETL modernization writeup emphasize?"
  )
  index=$(( RANDOM % ${#questions[@]} ))
  send_request "${questions[$index]}"
' _ >> "$RESULTS_FILE"

echo "Load run complete."
echo "Watch scaling with:"
echo "  kubectl get hpa -n ai-lab -w"
echo "  kubectl get pods -n ai-lab -w"

echo
echo "Summary:"
awk '
{
  count++
  code[$1]++
  total_time += $2
}
END {
  printf "Total responses: %d\n", count
  for (c in code) printf "HTTP %s: %d\n", c, code[c]
  if (count > 0) printf "Average latency: %.3fs\n", total_time / count
}' "$RESULTS_FILE"
