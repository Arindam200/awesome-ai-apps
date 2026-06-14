# Production reference — MCP Toolbox on GKE

These manifests are the **reference architecture** (not auto-applied by the demo).
They show how the same Toolbox security model runs in production on GKE, with the
hardening that local docker-compose can't demonstrate.

## What's different from local compose

| Concern    | Local (compose)                     | GKE (these manifests)                         |
|------------|-------------------------------------|-----------------------------------------------|
| Postgres   | `kind: postgres` + password         | `kind: cloud-sql-postgres`, **no password** (IAM) |
| DB auth    | role password in `.env`             | **Workload Identity** KSA→GSA, IAM DB users   |
| Secrets    | `.env` file                         | K8s Secret / **Secret Manager** (CSI / ESO)   |
| `tools.yaml`| bind-mounted file                  | mounted from a **Secret** (`toolbox-tools`)   |
| Network    | compose bridge                      | **NetworkPolicy** (agent→Toolbox→DB only)     |
| Telemetry  | `--telemetry-otlp` → collector      | `--telemetry-gcp` → Cloud Trace/Monitoring    |
| Identity   | local Keycloak                      | Google Sign-In (`authService: kind: google`)  |
| Scaling    | single container                    | **HPA** 2–10 replicas, pooled connections     |

The customer/admin tools, authenticated parameters, and least-privilege roles are
**identical** — only the `sources:` block in `tools.yaml` changes (see
`deploy/k8s/tools.yaml`, generated from `toolbox/tools.yaml`).

## Prerequisites (one-time)

```bash
# 1. Workload Identity: bind the KSA to a GSA, grant Cloud SQL access
gcloud iam service-accounts add-iam-policy-binding \
  toolbox-gsa@PROJECT.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:PROJECT.svc.id.goog[groceries/toolbox-sa]"
gcloud projects add-iam-policy-binding PROJECT \
  --member serviceAccount:toolbox-gsa@PROJECT.iam.gserviceaccount.com \
  --role roles/cloudsql.client

# 2. Create the IAM DB users on the instance and grant them the least-priv roles
#    from db/postgres/01_roles.sql (toolbox_app / toolbox_admin).

# 3. Mount tools.yaml + non-IAM secrets
kubectl create namespace groceries
kubectl -n groceries create secret generic toolbox-tools \
  --from-file=tools.yaml=deploy/k8s/tools.yaml
kubectl -n groceries apply -f deploy/k8s/toolbox-secret.example.yaml   # edit first!
```

## Apply

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/serviceaccount.yaml
kubectl apply -f deploy/k8s/toolbox-deployment.yaml
kubectl apply -f deploy/k8s/toolbox-service.yaml
kubectl apply -f deploy/k8s/networkpolicy.yaml
kubectl apply -f deploy/k8s/hpa.yaml
kubectl apply -f deploy/k8s/agent-web.yaml
```

Replace `PROJECT_ID` / `REGISTRY` / `groceries.example.com` placeholders first.

> No official Helm chart exists for Toolbox today — these are raw manifests. They
> are intentionally minimal; add your Ingress/Gateway + TLS, PodDisruptionBudgets,
> and Secret Manager CSI wiring per your platform standards.
