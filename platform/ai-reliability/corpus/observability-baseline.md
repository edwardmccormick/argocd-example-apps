# Observability Baseline

This document defines the initial observability baseline for the local reliability lab.

## Stack

- Prometheus for scraping, rule evaluation, and alerting
- Grafana for dashboards
- Blackbox Exporter for synthetic HTTP probing
- OpenTelemetry Collector for OTLP ingestion from workloads
- k6 CronJob for periodic in-cluster load generation

## Guestbook Service Indicators

The guestbook workload currently exposes two baseline indicators.

### Availability

- SLI name: `guestbook:availability:5m`
- Expression: `avg_over_time(probe_success{job="blackbox-guestbook"}[5m])`
- Meaning: fraction of successful synthetic HTTP probes over the trailing 5 minutes
- Initial target: `>= 0.99`

This is synthetic availability measured from inside the cluster against the guestbook service endpoint.

### Request Latency

- SLI name: `guestbook:latency_avg_ms:5m`
- Expression: `sum(rate(apache_request_time_milliseconds_total[5m])) / clamp_min(sum(rate(apache_requests_total[5m])), 1e-9)`
- Meaning: average Apache request latency in milliseconds over the trailing 5 minutes
- Initial target: `<= 250ms`

This latency comes from Apache status metrics exported from the guestbook pod through an OpenTelemetry sidecar.

### Request Rate

- SLI support metric: `guestbook:request_rate:5m`
- Expression: `sum(rate(apache_requests_total[5m]))`
- Meaning: average requests per second over the trailing 5 minutes

This is not an SLO by itself, but it helps interpret availability and latency behavior during traffic changes.

## Alerts

- `GuestbookUnavailable`
  - Fires when `guestbook:availability:5m < 1` for 2 minutes
- `GuestbookLatencyHigh`
  - Fires when `guestbook:latency_avg_ms:5m > 250` for 10 minutes

## Load Testing

- CronJob name: `guestbook-load-generator`
- Tool: `grafana/k6`
- Schedule: every 10 minutes
- Profile: 5 virtual users for 30 seconds against `http://guestbook-ui.default.svc.cluster.local/`

This generates low but regular traffic so the request-rate and latency graphs move without requiring manual clicks in a browser. The initial threshold profile is intentionally conservative for a local lab.

## Current Limitations

- Availability is measured from a synthetic in-cluster probe, not from an external user path.
- Latency is Apache-level latency, not end-to-end browser latency.
- Guestbook logs are exported through OTLP, but they are not yet queryable in a local log backend.
- There is no explicit error-rate SLI yet because the sample guestbook app does not expose rich HTTP outcome metrics beyond the current Apache baseline.

## Next Steps

- Add a log backend such as Loki if local log search becomes necessary.
- Add external probing through Traefik if you want ingress-path availability instead of service-only availability.
- Add a second load profile that targets the ingress path through Traefik instead of the service-only path.
