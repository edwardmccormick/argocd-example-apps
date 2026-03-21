# Local Reliability Lab

This repository is a hands-on platform lab for building interview-ready depth in Kubernetes, GitOps, observability, quality engineering, and AI reliability. The current base is a local `k3d/k3s` cluster with Traefik ingress, ArgoCD, and a Helm-based guestbook deployment. The goal is to evolve that base into a small but disciplined environment that demonstrates how reliable systems are built and operated.

## Current State

The lab already covers the core control-plane workflow:

- local Kubernetes via `k3d`
- Traefik ingress routing
- ArgoCD UI and CLI access
- GitOps-style application deployment
- initial Helm chart work in [`helm-guestbook`](./helm-guestbook)

The repository now also includes an initial GitOps scaffold:

- [`apps/guestbook`](./apps/guestbook) for workload ownership and app notes
- [`apps/ai-reliability-service`](./apps/ai-reliability-service) for a grounded document-QA workload and eval harness
- [`environments/local`](./environments/local) for the local cluster's ArgoCD-managed resources
- [`platform/argocd`](./platform/argocd) for ArgoCD bootstrap manifests
- [`platform/observability`](./platform/observability) for the local observability baseline
- [`platform/ai-reliability`](./platform/ai-reliability) for the AI reliability workload

That is enough to move beyond basic setup and focus on operational patterns.

## Target Outcome

This repository should grow into a local platform that demonstrates:

- GitOps-managed Kubernetes resources through ArgoCD and Helm
- observability with dashboards, alerts, and traceable failure modes
- SLI/SLO thinking, including availability and latency targets
- CI-enforced quality and security gates
- deliberate failure injection and recovery exercises
- a small AI-powered workload with evaluation, replay, and telemetry
- event-driven autoscaling patterns for queue-based workloads

## Build Plan

### 1. GitOps Foundation

Restructure the repo to manage applications declaratively in Git. Add environment-aware manifests or Helm values, then manage them through ArgoCD `Application` manifests or an app-of-apps pattern. The repository should become the source of truth, with CLI usage reserved for inspection, sync, and troubleshooting.

This step is now active:

- the root ArgoCD bootstrap app lives at [`platform/argocd/root-application.yaml`](./platform/argocd/root-application.yaml)
- the local environment lives at [`environments/local`](./environments/local)
- the Helm-backed guestbook app lives at [`environments/local/apps/guestbook.yaml`](./environments/local/apps/guestbook.yaml)

The guestbook workload now runs from the Helm chart in this repository, with ArgoCD automated sync, prune, and self-heal enabled.

### 2. Observability Baseline

Install and configure a minimal observability stack such as Prometheus, Grafana, and OpenTelemetry-compatible components. The local baseline now uses Prometheus, Grafana, Blackbox Exporter, and an OpenTelemetry Collector. Define at least two service indicators for the guestbook app:

- availability
- request latency

Add dashboards and at least one alert so the lab reflects real operating expectations rather than successful deployment alone.

### 3. Quality And Security Gates

Add CI workflows that validate infrastructure and manifests on every change. The baseline should include:

- `helm lint`
- `helm template`
- YAML validation
- Kubernetes schema validation
- container or manifest vulnerability scanning
- infrastructure policy checks

The point is to show that reliability and quality are enforced before deployment, not inspected afterward.

The repository now includes a GitHub Actions validation workflow for Helm rendering, Kustomize rendering, client-side manifest parsing, Kubernetes schema validation, Trivy config scanning, and an ephemeral kind-based smoke test that verifies the guestbook chart can deploy and serve traffic before merge.

A short write-up on why the Trivy scan and smoke test were worth keeping lives in [`trivy-and-smoketest-notes.md`](./trivy-and-smoketest-notes.md).

That write-up also now captures a related CI lesson: security tools and GitHub Actions are themselves part of the software supply chain, so the repository treats dependency trust, pinning, and blast-radius reduction as part of the quality discussion rather than as a separate concern.

### 4. Failure Drills

Use ArgoCD self-heal, pruning, broken readiness checks, and bad configuration changes as controlled failure exercises. Each drill should produce a short runbook describing:

- expected symptom
- detection path
- recovery path
- follow-up hardening action

### 5. AI Reliability Workload

Add a small AI-backed service that supports:

- retrieval over a small document set
- structured JSON output
- evaluation prompts and replay cases
- prompt, retrieval, and latency telemetry
- token usage visibility

This is the bridge from general SRE practice into AI reliability, evaluation, and observability.

The first version of that workload now exists as a deterministic document-QA service over the repository's own reliability notes. It exposes structured JSON responses, request-latency metrics, workflow completion signals, and a small replay/eval dataset that can run in CI without needing a paid model backend.

### 6. Event-Driven Scaling

Add a lightweight queue-based service and autoscale it with KEDA. This gives the lab a stronger story around asynchronous systems, scaling signals, and workload behavior under pressure.

## Suggested Execution Order

1. GitOps repo structure and ArgoCD application definitions
2. CI quality and security gates
3. Observability stack, dashboards, and alerts
4. Failure drills and runbooks
5. AI workload with evaluation and telemetry
6. Queue-driven autoscaling with KEDA

## Immediate Next Steps

1. Let the GitHub Actions validation workflow run on the next push and fix any gaps it exposes.
2. Recover the guestbook readiness drill by reverting the bad probe path and confirming the rollout completes.
3. Verify Prometheus is probing `guestbook-ui` and that the `Guestbook Overview` dashboard loads in Grafana.
4. Add application-level metrics or OTLP traces from a future workload into the OpenTelemetry Collector.
5. Extend the AI workload from deterministic retrieval into a model-backed path with prompt traces and richer evaluation scoring.

## Operating Principle

This lab is not meant to be a collection of one-off deployments. It is meant to show disciplined platform engineering: declarative delivery, measurable reliability, visible quality, secure defaults, and enough AI integration to discuss modern production concerns with specificity.
