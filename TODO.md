# TODO

## Event-Driven Scaling

Add a queue-backed workload and autoscale it with KEDA.

Why it matters:

- demonstrates asynchronous workload behavior instead of only request/response services
- creates a stronger scaling story than replica counts alone
- gives the lab a realistic way to discuss lag, backlog, throughput, and scaling signals

Target shape:

- lightweight producer / consumer pair
- visible queue depth or lag metric
- KEDA-driven scaling policy
- Grafana view that correlates load, lag, and replica count

## Progressive Delivery

Add canary or blue/green deployment patterns tied to existing observability.

Why it matters:

- the lab already measures latency, availability, workflow completion, and structured-output validity
- those signals are exactly the kinds of metrics that should influence rollout safety
- this would turn the repo from “GitOps with monitoring” into “GitOps with deployment analysis”

Target shape:

- progressive delivery for guestbook or the AI service
- promotion gated by measurable signals such as:
  - guestbook availability and latency
  - AI workflow completion ratio
  - AI structured-output validity
  - repo / control-plane health where appropriate
- rollback or non-promotion when the canary violates those thresholds

This is explicitly a next-step item because the underlying observability and alerting are now in place to support it cleanly.
