# Local Environment

This environment represents the local `k3d/k3s` cluster used for interview practice.

Apply this environment directly with:

```powershell
kubectl apply -k .\environments\local
```

Or bootstrap through ArgoCD with:

```powershell
kubectl apply -f .\platform\argocd\root-application.yaml
```

The guestbook Helm application is defined here with manual sync semantics for now. That avoids collision with the older non-Helm guestbook application already running in the cluster.
