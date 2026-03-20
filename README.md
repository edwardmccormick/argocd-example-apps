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
- [`environments/local`](./environments/local) for the local cluster's ArgoCD-managed resources
- [`platform/argocd`](./platform/argocd) for ArgoCD bootstrap manifests

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

This step is now scaffolded, but not finished:

- the root ArgoCD bootstrap app lives at [`platform/argocd/root-application.yaml`](./platform/argocd/root-application.yaml)
- the local environment lives at [`environments/local`](./environments/local)
- the Helm-backed guestbook app lives at [`environments/local/apps/guestbook.yaml`](./environments/local/apps/guestbook.yaml)

Two cleanup tasks remain before this becomes the active path:

- update `repoURL` placeholders to your real GitHub repository
- remove or retire the older non-Helm guestbook application already running in the cluster

### 2. Observability Baseline

Install and configure a minimal observability stack such as Prometheus, Grafana, and OpenTelemetry-compatible components. Define at least two service indicators for the guestbook app:

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

1. Complete the `helm-guestbook` chart by adding templates for the Deployment, Service, and any ingress resources you want ArgoCD to manage.
2. Replace the `REPLACE_ME` GitHub URLs in the ArgoCD bootstrap files with the actual repository URL.
3. Apply the bootstrap app or the local environment manifests to ArgoCD.
4. Confirm the existing non-Helm guestbook app is removed before enabling automated sync on the Helm-backed app.
5. After cutover, add:
   - `prune: true`
   - `selfHeal: true`
   under `spec.syncPolicy.automated` in the Helm application manifest.

## Operating Principle

This lab is not meant to be a collection of one-off deployments. It is meant to show disciplined platform engineering: declarative delivery, measurable reliability, visible quality, secure defaults, and enough AI integration to discuss modern production concerns with specificity.
