# Trivy And Smoke Test Notes

One of the more useful outcomes in this repository was not just "CI is green" but the way Trivy changed the quality of the manifests.

## What Happened

After adding CI validation, the Trivy config scan immediately started failing on several Kubernetes manifests. The failures were not exotic. They were common baseline hardening issues:

- containers running with the default security context
- writable root filesystems
- missing explicit pod-level security settings

None of those issues stopped the lab from working locally. That is exactly why the scan was valuable. The manifests were functionally correct, but they were still carrying security debt.

## Why This Matters

Static security scanning is useful here because it catches the kinds of omissions that are easy to accept in a local lab and easy to miss in code review:

- "it works" is not the same as "it is hardened"
- defaults are often more permissive than they should be
- a small repo still benefits from production-style guardrails

The Trivy scan forced the repository to move from merely deployable manifests toward defensible manifests.

## What It Improved

The scan drove concrete hardening changes such as:

- explicit `securityContext` configuration
- `readOnlyRootFilesystem: true`
- `runAsNonRoot` where appropriate
- `seccompProfile: RuntimeDefault`
- writable scratch mounts only where the container actually needed them

That last point matters. The scan did not just encourage turning on security knobs blindly. It pushed the repo toward understanding runtime behavior, then expressing the minimum required write access explicitly.

## Why The Smoke Test Matters Too

The Trivy findings were useful on their own, but the real value came from pairing them with the ephemeral deployment smoke test in CI.

That combination gives two distinct protections:

- Trivy says: "this manifest is not hardened enough"
- the smoke test says: "your hardening changes still allow the workload to boot and serve traffic"

That is a much better story than linting alone.

## What The Smoke Test Failure Taught Us

The smoke test did not just provide a green or red checkbox. It exposed a real deployability bug that static validation did not catch.

The specific issue was subtle:

- the guestbook container was hardened with `readOnlyRootFilesystem: true`
- writable Apache runtime paths were only mounted when telemetry was enabled
- the CI smoke test deliberately installed the chart with telemetry disabled
- the deployment then failed to become ready because Apache no longer had the writable runtime paths it needed

That is exactly the kind of failure mode a deployability test is supposed to catch. The manifests were valid. The security scan was satisfied. But the workload still could not boot under the actual runtime combination used in CI.

This is why the smoke test is a real value add even for a small proof of concept:

- it validates behavior, not just structure
- it catches interaction effects between "good" changes
- it proves that hardening and deployability still coexist

## Why Diagnostics Matter Almost As Much As Pass/Fail

The first smoke-test failure only told us that rollout timed out. That was not enough.

A failing deployment check without diagnostics creates a bad operator experience:

- you know something is broken
- you do not know whether it is scheduling, readiness, security context, image startup, or service wiring
- you lose time rebuilding context that the CI job could have captured automatically

Adding targeted diagnostics to the workflow made the smoke test much more useful. On failure, the job now emits:

- deployment status
- pod state
- `describe` output
- recent container logs

That is a much saner pattern than treating CI as a binary gate with no operational evidence.

The practical lesson is that runtime validation should not only answer "did this deploy?" It should also help answer "why did this fail?" in a way that reduces time to diagnosis.

## Why This Is Worth Keeping

Even in a deliberately small demo repository, the Trivy scan and smoke test proved that CI tooling is not just compliance theater. It materially improved the Kubernetes manifests, exposed a real runtime regression, and made the system more realistic as an example of platform engineering discipline.

That is useful for interviews, but it is also just operationally sound:

- safer defaults
- fewer obvious footguns
- better habits encoded in CI instead of left to memory
- faster diagnosis when runtime validation fails

## Practical Takeaway

The lesson is not "add scanners so the pipeline looks advanced."

The lesson is:

1. let scanners find the baseline misses humans gloss over
2. fix the manifests instead of suppressing the findings immediately
3. pair static checks with runtime validation so hardening does not silently break deployability

That is a much closer approximation of real-world SRE and platform engineering than a repo that only proves YAML can render.
