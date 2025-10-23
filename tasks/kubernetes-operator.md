# Kubernetes Operator for Multi-Account Worker Pods

**Priority:** P2 - Medium (Production infrastructure)
**Status:** Design complete, not implemented
**Estimated effort:** 12-16 hours

---

## Overview

Implement a Kubernetes operator that watches the `accounts` table and automatically creates/manages worker pods for each active Airbnb account. This enables multi-tenant operation where each account runs in its own isolated pod.

---

## Architecture

### Components

**1. Admin API** (`MODE=admin`)
- Manages accounts via REST API
- Creates account records in database
- **NO** direct Kubernetes API access (security boundary)
- Runs as a single deployment

**2. Kubernetes Operator** (separate service/controller)
- Watches `accounts` table for `is_active=true`
- Creates worker Deployment with `ACCOUNT_ID` and `MODE=worker`
- Scoped ServiceAccount (only deployment CRUD permissions)
- Handles scaling, updates, and cleanup
- Written in Go (kubebuilder) or Python (kopf)

**3. Worker Pods** (auto-created by operator)
- Start with `ACCOUNT_ID` from environment
- Startup sync runs in background thread (non-blocking)
- Check `last_sync_at` on startup: If NULL, run immediate sync (25 week backfill)
- Configure scheduler for daily syncs (5:00 UTC)
- Self-contained, no cross-pod communication
- Each pod manages exactly one Airbnb account

---

## Security Benefits

- **Isolation:** Admin API breach ≠ cluster breach
- **Least Privilege:** Operator has minimal, scoped RBAC permissions
- **Single Source of Truth:** Database drives all pod creation decisions
- **Audit Trail:** All pod creations logged and tracked
- **Credential Isolation:** Each worker pod has only its own account credentials

---

## Implementation Tasks

### 1. Operator Development
- [ ] Choose framework (kubebuilder vs kopf)
- [ ] Implement database watcher (poll `accounts` table every 30s)
- [ ] Create Deployment template with proper labels
- [ ] Implement pod lifecycle management (create/update/delete)
- [ ] Add RBAC manifests (ServiceAccount, Role, RoleBinding)
- [ ] Handle edge cases (pod crashes, database unavailable)

### 2. Migration Strategy
- [ ] Migrations run as separate Kubernetes Job (not in worker pods)
- [ ] Job runs before operator starts
- [ ] Avoids race conditions with multiple pods
- [ ] Faster pod startup (no migration wait)

### 3. Worker Pod Configuration
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sync-airbnb-worker-{{ account_id }}
  namespace: sync-airbnb
  labels:
    app: sync-airbnb-worker
    account-id: "{{ account_id }}"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sync-airbnb-worker
      account-id: "{{ account_id }}"
  template:
    metadata:
      labels:
        app: sync-airbnb-worker
        account-id: "{{ account_id }}"
    spec:
      containers:
      - name: worker
        image: sync-airbnb:latest
        env:
        - name: MODE
          value: "worker"
        - name: ACCOUNT_ID
          value: "{{ account_id }}"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: sync-airbnb-db
              key: url
        # Account credentials fetched from database on startup
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
          timeoutSeconds: 5
```

### 4. RBAC Configuration
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sync-airbnb-operator
  namespace: sync-airbnb
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: sync-airbnb-operator
  namespace: sync-airbnb
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: sync-airbnb-operator
  namespace: sync-airbnb
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: sync-airbnb-operator
subjects:
- kind: ServiceAccount
  name: sync-airbnb-operator
  namespace: sync-airbnb
```

---

## Future Enhancements

### Enhanced Health Endpoint

Add sync status to `/health` and `/health/ready` endpoints:

```json
{
  "status": "healthy",
  "mode": "worker",
  "account_id": "310316675",
  "scheduler": {
    "running": true,
    "next_run": "2025-10-24T05:00:00Z"
  },
  "initial_sync": {
    "complete": true,
    "last_sync_at": "2025-10-23T05:00:00Z"
  }
}
```

**Benefits:**
- Kubernetes readiness probe can verify sync completion
- Operator can monitor worker health more accurately
- Better visibility in monitoring dashboards

---

## Acceptance Criteria

- [ ] Operator creates worker pod when account is created with `is_active=true`
- [ ] Operator deletes worker pod when account is set to `is_active=false`
- [ ] Operator updates worker pod when account credentials change
- [ ] Worker pods start successfully and run initial sync if `last_sync_at` is NULL
- [ ] Worker pods pass readiness probes after startup
- [ ] Operator has minimal RBAC permissions (scoped to sync-airbnb namespace)
- [ ] Database migrations run as separate Job before operator starts
- [ ] All pod creations/deletions logged and auditable

---

## Open Questions

1. **Credential Updates:** How to trigger pod restart when account credentials change?
   - Option A: Operator detects `updated_at` timestamp change and recreates pod
   - Option B: Worker polls database for credential updates periodically

2. **Pod Naming:** Use account_id in pod name or generate unique identifier?
   - Current: `sync-airbnb-worker-{{ account_id }}`
   - Alternative: `sync-airbnb-worker-{{ hash(account_id) }}`

3. **Resource Limits:** What CPU/memory limits per worker pod?
   - Need to profile actual usage during 25-week backfill
   - Current estimate: 512Mi-1Gi memory, 250m-500m CPU

---

## References

- Kubebuilder: https://book.kubebuilder.io/
- Kopf (Python): https://kopf.readthedocs.io/
- Kubernetes Operator Pattern: https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
