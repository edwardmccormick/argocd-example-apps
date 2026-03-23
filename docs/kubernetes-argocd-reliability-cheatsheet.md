# Kubernetes + Argo CD Reliability Cheatsheet

This is a compact interview reference for talking through reliability patterns, failure modes, and controls in a Kubernetes cluster managed by Argo CD.

## Core Model

- Kubernetes owns scheduling, probes, rollouts, and controller behavior.
- Argo CD owns reconciliation back to Git.
- Reliability issues often happen where those two ownership models meet.

Useful framing questions:

- what is allowed to drift?
- what must be reconciled immediately?
- what should trigger rollout automatically?
- what should be validated before merge instead of after deploy?

## Key Patterns

### Runtime-Owned Fields Must Be Explicit

GitOps gets brittle when Git is forced to own fields that runtime controllers legitimately mutate.

Concrete repo example:

- HPA scaled `ai-reliability` from `1` to `2` and `3`
- Argo self-heal immediately forced it back to `1`
- fixed in [`environments/local/apps/ai-reliability.yaml`](./environments/local/apps/ai-reliability.yaml#L1) with `ignoreDifferences` on `/spec/replicas` plus `RespectIgnoreDifferences=true`

Interview point:

- let Argo own the object
- let the HPA own replica count
- scope the drift exception narrowly

### Config Should Naturally Trigger Rollouts

One of the highest-yield fixes in this repo was moving Prometheus and Grafana config to generated file-backed `ConfigMap`s with Kustomize hash suffixes.

Why:

- plain `ConfigMap` updates do not always restart consumers
- `subPath` mounts are brittle and can leave running pods with stale config
- manual restart requirements are reliability debt

Concrete repo examples:

- Prometheus config in [`platform/observability/config/prometheus`](../platform/observability/config/prometheus)
- Grafana config in [`platform/observability/config/grafana`](../platform/observability/config/grafana)
- generation wiring in [`platform/observability/kustomization.yaml`](../platform/observability/kustomization.yaml#L1)

Interview point:

- prefer file-backed config
- generate hashed `ConfigMap`s
- mount directories instead of brittle per-file `subPath` when possible

### CI Should Prove Deployability, Not Just Syntax

Static validation is necessary and insufficient.

This repo now validates:

- Helm lint and render
- Kustomize render
- YAML parse and schema checks
- Trivy config scanning
- deterministic AI evals
- `kind` smoke tests for both guestbook and AI service

Why it matters:

- static checks did not catch a real guestbook boot regression
- the smoke test did
- targeted diagnostics made the failure actionable instead of opaque

Refs:

- workflow in [`.github/workflows/validate-manifests.yaml`](../.github/workflows/validate-manifests.yaml#L1)
- discussion in [`trivy-and-smoketest-notes.md`](../trivy-and-smoketest-notes.md#L1)

### Distinguish Service Health From Service Quality

This repo intentionally exercises both kinds of failure:

- guestbook readiness drill: rollout unhealthy, users still served by old ready pod
- AI internal failure drill: pod healthy, JSON valid, workflow usefulness degraded

Interview point:

- pod health is not service health
- HTTP 200 is not workflow success
- AI systems need quality signals, not just infrastructure signals

Refs:

- [`failure-drill-guestbook-readiness.md`](../failure-drill-guestbook-readiness.md#L1)
- [`failure-drill-ai-internal-application-failure.md`](../failure-drill-ai-internal-application-failure.md#L1)

### The GitOps Control Plane Is Production Infrastructure

If repo-server is unhealthy, delivery is unhealthy.

Concrete repo lessons:

- repo-server init logic was not idempotent after restart
- Git ref resolution to GitHub timed out after cluster restart
- Argo CD metrics were added to Prometheus and Grafana so sync and repo-server problems are observable

Interview point:

- monitor Argo CD like part of production
- app health alone is not enough in a GitOps system

## Specific Findings From This Lab

- Argo CD can fight HPA unless replica drift is explicitly allowed.
- `subPath` mounts create stale-config failure modes.
- auto-sync is not instant; normal reconciliation is on the order of minutes, not seconds.
- restart-safe bootstrap logic matters; init steps should be idempotent.
- CI failure diagnostics are nearly as important as CI pass/fail.
- AI reliability needs semantic signals such as workflow completion and insufficient-context ratio, not only pod readiness.

## Metrics Worth Talking About

Guestbook:

- availability SLI
- request rate
- latency

AI service:

- workflow completion ratio
- structured output validity ratio
- latency p95
- insufficient-context ratio
- request rate
- citation throughput

Interview point:

- infrastructure metrics tell you whether the service is up
- workflow metrics tell you whether the feature is actually working

## Good Interview Topics

- default RollingUpdate behavior and why broken rollouts do not always create outages
- when Argo should self-heal drift and when drift is legitimate controller behavior
- why deployability tests belong in CI
- how to scope `ignoreDifferences` safely
- why AI systems need semantic SLIs beyond 200s and readiness
- why control-plane observability matters in GitOps
- how to reduce supply-chain risk in CI tooling

## Important Areas Not Fully Implemented Here

- canary or blue/green promotion tied to AI quality metrics
- replay-based live canary analysis before promotion
- KEDA or queue-driven scaling for async workloads
- policy-as-code for probes, security context, requests/limits, and image policies
- multi-environment promotion flows instead of direct deploy-from-main
- stronger secret management and external secret stores
- fully Git-managed Argo CD install customization instead of live patching

## Short Answer

If you need the compressed version in an interview:

1. GitOps is reliable when ownership boundaries are explicit.
2. Argo CD should not fight Kubernetes controllers like HPAs.
3. Config should be structured so changes naturally trigger rollouts.
4. CI should prove deployability, not just manifest validity.
5. Control-plane health is part of application reliability.
6. For AI systems, semantic quality signals matter more than pod health alone.
