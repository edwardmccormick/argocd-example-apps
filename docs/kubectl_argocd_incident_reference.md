# kubectl + Argo CD CLI Quick Reference

**Incident management and troubleshooting**

Compiled March 23, 2026 from the official Kubernetes and Argo CD command references.

## General incident flow

1. **Confirm context**
   - `kubectl config current-context`
   - `kubectl get ns`
   - `argocd context`
   - `argocd version`
   - Make sure you are in the right cluster, namespace, and Argo CD control plane before touching anything.

2. **Check GitOps health first**
   - `argocd app get <app>`
   - `argocd app resources <app>`
   - `argocd app history <app>`
   - If Argo CD already shows `OutOfSync`, `Degraded`, or a bad revision, start by treating it as a release problem.

3. **Determine blast radius**
   - `kubectl get pods -n <ns>`
   - `kubectl get svc,endpoints,endpointslices -n <ns>`
   - `kubectl get events -n <ns> --sort-by=.metadata.creationTimestamp`
   - `kubectl get nodes -o wide`
   - Decide whether the issue is pod-local, workload-level, namespace-wide, or broader cluster trouble.

4. **Drill into the symptom**
   - Pending -> `kubectl describe pod <pod> -n <ns>`
   - CrashLoopBackOff -> `kubectl logs <pod> -n <ns> --previous`
   - Traffic failing -> `kubectl describe svc <svc> -n <ns>`
   - Rollout stuck -> `kubectl rollout status deploy/<deploy> -n <ns>`

5. **Mitigate carefully**
   - `argocd app sync <app>`
   - `argocd app rollback <app> [history-id]`
   - `kubectl rollout undo deploy/<deploy> -n <ns>`
   - `kubectl scale deploy/<deploy> -n <ns> --replicas=<n>`
   - Prefer the smallest reversible change.

6. **Normalize and record**
   - `argocd app diff <app>`
   - `kubectl get <resource> -n <ns> -o yaml`
   - `argocd app history <app>`
   - Reconcile temporary fixes back to Git and capture the exact root cause.

## Start here

### What is broken right now?
```bash
kubectl get pods -A
kubectl get deploy,statefulset,daemonset -A
kubectl get events -A --sort-by=.metadata.creationTimestamp
kubectl top nodes
kubectl top pods -A
```

### Which app is unhealthy in Argo CD?
```bash
argocd app list
argocd app get <app>
argocd app resources <app>
```

### Why is one pod failing?
```bash
kubectl describe pod <pod> -n <ns>
kubectl logs <pod> -n <ns> --previous
kubectl get pod <pod> -n <ns> -o yaml
```

### Why is service traffic failing?
```bash
kubectl get svc,endpoints,endpointslices -n <ns>
kubectl describe svc <svc> -n <ns>
kubectl get ingress -n <ns>
kubectl describe ingress <ingress> -n <ns>
```

## kubectl reference

### Context and scope
```bash
kubectl config current-context
kubectl config get-contexts
kubectl cluster-info
kubectl get ns
kubectl get nodes -o wide
```

### Read-heavy inspection
```bash
kubectl get pods -n <ns>
kubectl get deploy,statefulset,daemonset -n <ns>
kubectl describe <kind> <name> -n <ns>
kubectl get <kind> <name> -n <ns> -o yaml
kubectl get events -n <ns> --sort-by=.metadata.creationTimestamp
kubectl top pods -n <ns>
```

### Logs and live debugging
```bash
kubectl logs <pod> -n <ns>
kubectl logs <pod> -n <ns> --previous
kubectl logs <pod> -n <ns> -c <container>
kubectl exec -it <pod> -n <ns> -- /bin/sh
kubectl port-forward pod/<pod> -n <ns> 8080:8080
kubectl port-forward svc/<svc> -n <ns> 8080:80
```

### Rollout control
```bash
kubectl rollout status deploy/<deploy> -n <ns>
kubectl rollout history deploy/<deploy> -n <ns>
kubectl rollout undo deploy/<deploy> -n <ns>
kubectl scale deploy/<deploy> -n <ns> --replicas=<n>
kubectl set image deploy/<deploy> <container>=<image> -n <ns>
```

## Symptom-based triage

### Pending
```bash
kubectl describe pod <pod> -n <ns>
kubectl get events -n <ns> --sort-by=.metadata.creationTimestamp
kubectl get nodes -o wide
```
Look for insufficient CPU or memory, taints and tolerations mismatch, PVC binding issues, or image pull secret problems.

### CrashLoopBackOff
```bash
kubectl describe pod <pod> -n <ns>
kubectl logs <pod> -n <ns> --previous
kubectl logs <pod> -n <ns> -c <container> --previous
```
Check exit code, OOMKilled, probe failures, and prior-container logs first.

### ImagePullBackOff
```bash
kubectl describe pod <pod> -n <ns>
kubectl get sa <serviceaccount> -n <ns> -o yaml
kubectl get secret -n <ns>
```
Most often a bad image tag, registry auth issue, or service account mismatch.

### Traffic failing
```bash
kubectl get svc,endpoints,endpointslices -n <ns>
kubectl describe svc <svc> -n <ns>
kubectl describe ingress <ingress> -n <ns>
kubectl get pod -l app=<label> -n <ns> -o wide
```
Follow the path Pod -> Service -> Endpoint -> Ingress.

### Rollout stuck
```bash
kubectl rollout status deploy/<deploy> -n <ns>
kubectl rollout history deploy/<deploy> -n <ns>
argocd app history <app>
```
Separate bad release behavior from broader cluster conditions.

## Argo CD reference

### Connectivity and context
```bash
argocd version
argocd context
argocd login <ARGOCD_SERVER>
argocd cluster list
```

### Application health
```bash
argocd app list
argocd app get <app>
argocd app get <app> -o yaml
argocd app resources <app>
```

### Diff, history, and manifests
```bash
argocd app diff <app>
argocd app manifests <app>
argocd app history <app>
```

### Recovery actions
```bash
argocd app get <app> --refresh
argocd app sync <app>
argocd app wait <app>
argocd app terminate-op <app>
argocd app rollback <app> [history-id]
```

## Compact one-screen version

```bash
# First 60 seconds
kubectl config current-context
kubectl get ns
kubectl get nodes -o wide
argocd context
argocd app list

# Is it GitOps or Kubernetes?
argocd app get <app>
argocd app resources <app>
kubectl get pods -n <ns>
kubectl get events -n <ns> --sort-by=.metadata.creationTimestamp

# Pod triage
kubectl describe pod <pod> -n <ns>
kubectl logs <pod> -n <ns> --previous
kubectl get pod <pod> -n <ns> -o yaml

# Traffic triage
kubectl get svc,endpoints,endpointslices -n <ns>
kubectl describe svc <svc> -n <ns>
kubectl describe ingress <ingress> -n <ns>

# Recovery
kubectl rollout undo deploy/<deploy> -n <ns>
argocd app sync <app>
argocd app wait <app>
argocd app rollback <app> [history-id]
```

## Guardrails

- Prefer read commands first: `get`, `describe`, `logs`, `diff`, `history`.
- Verify context and namespace before every write action.
- In GitOps-managed namespaces, expect manual `kubectl` changes to create drift or be reconciled away.
- After recovery, move temporary fixes back into Git.

## Sources

- Kubernetes: kubectl Quick Reference and command reference
- Argo CD: getting started, `argocd app`, `argocd cluster list`, `argocd version`, and `argocd app rollback` command references
