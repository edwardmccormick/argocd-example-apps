# Failure Drill: Guestbook Readiness Regression

This drill intentionally breaks the guestbook readiness probe to exercise detection, diagnosis, and GitOps recovery.

## Objective

Validate that the platform surfaces a bad rollout quickly and that recovery happens by reverting Git rather than patching live state.

## Preconditions

- `helm-guestbook` is healthy and synced in Argo CD
- Prometheus and Grafana are running in the `observability` namespace
- The guestbook dashboard is reachable
- Automated sync, prune, and self-heal are enabled for the guestbook application

## Failure Injection

Change the readiness probe path in [`values.yaml`](./helm-guestbook/values.yaml#L47) from:

```yaml
probes:
  readiness:
    path: /
```

to:

```yaml
probes:
  readiness:
    path: /does-not-exist
```

Commit and push the change so Argo CD reconciles it.

## Expected Symptoms

- The new guestbook pods fail readiness
- `kubectl get pods -n default` shows pods as `Running` but not `Ready`
- `kubectl describe pod` shows readiness probe failures with HTTP 404
- `guestbook:availability:5m` drops as the service has fewer or no ready endpoints
- Grafana shows falling availability and request-rate behavior
- `GuestbookUnavailable` may fire if the bad state persists long enough

## Detection Path

1. Check Argo CD application health for `helm-guestbook`
2. Check pod readiness in `default`
3. Inspect guestbook events and readiness failure messages
4. Review Grafana:
   - `Guestbook Availability SLI`
   - `Guestbook Request Rate SLI`
   - `Guestbook Average Request Latency SLI`
5. Confirm the alert state in Prometheus

## Recovery Path

1. Revert the readiness probe path in Git back to `/`
2. Commit and push the revert
3. Let Argo CD resync automatically, or manually sync if needed
4. Confirm the new pods become ready
5. Confirm `guestbook:availability:5m` returns to `1`

Do not patch the live deployment directly unless Git reconciliation is broken and the exercise has shifted into incident mitigation mode.

## Follow-Up Hardening

- Add ingress-path blackbox probing so availability reflects the actual user entrypoint
- Add a runbook step that compares service endpoints before and after the rollout
- Consider adding a canary or staged rollout pattern before applying risky changes automatically
- Extend alerting to include a deployment rollout health signal, not only steady-state availability
