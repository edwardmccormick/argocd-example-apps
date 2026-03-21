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

- The new guestbook pod fails readiness
- The old ready pod continues serving traffic while the rollout stalls
- `kubectl get pods -n default` shows a mixed state: one ready old pod and one unready new pod
- `kubectl get rs -n default -l app=guestbook-ui` shows both the old and new ReplicaSets present during the stalled rollout
- `kubectl describe pod` shows readiness probe failures with HTTP 404 for the new pod
- `kubectl get endpointslice -n default -l kubernetes.io/service-name=guestbook-ui -o yaml` shows the old pod as `ready: true` and the new pod as `ready: false`
- Grafana may show odd or flat behavior rather than a full outage because the service still has at least one healthy endpoint
- `GuestbookUnavailable` may not fire in this scenario because availability can remain effectively 100% for the service endpoint

This happens because the Deployment uses the default `RollingUpdate` strategy. With `replicas: 1`, Kubernetes effectively keeps the old ready pod until the new pod becomes ready, which prevents a user-visible outage but leaves the rollout stuck.

## Detection Path

1. Check Argo CD application health for `helm-guestbook`
2. Check pod readiness in `default`
3. Check ReplicaSets for mixed old/new rollout state
4. Inspect guestbook events and readiness failure messages
5. Confirm only the old pod remains in ready service endpoints
6. Review Grafana:
   - `Guestbook Availability SLI`
   - `Guestbook Request Rate SLI`
   - `Guestbook Average Request Latency SLI`
7. Confirm the alert state in Prometheus

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
- Add a separate outage-focused drill if you want to demonstrate a true user-facing failure instead of a safely stalled rollout
