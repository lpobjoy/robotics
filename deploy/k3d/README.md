# deploy/k3d

CLAUDE.md build-sequence step 13: everything from `deploy/docker-compose.yml`
running on a local k3d cluster instead. Kustomize manifests (`kubectl
apply -k`, no separate `kustomize` binary needed), one Deployment +
Service pair per component, matching `docker-compose.yml`'s service
list and the same reasoning for what's excluded -- see that file's
"Not included here, and why" comment, which applies here unchanged.

## What's here

- `namespace.yaml` -- the `robot-router` namespace everything else lives in.
- `mosquitto.yaml`, `eam.yaml`, `mcp-server.yaml`, `telemetry.yaml`,
  `console.yaml` -- one Deployment + Service (+ a PersistentVolumeClaim
  for the two that write to sqlite files) per component.
- `agent-job.yaml` -- a one-shot Job template, the k8s equivalent of
  `docker compose run --rm agent <work_order_id>`. Not part of
  `kustomization.yaml`'s always-on set; applied by hand per work order.
  See its own header comment.
- `kustomization.yaml` -- ties the always-on set together.

## Running it

```bash
k3d cluster create robot-router

# Build the same images docker-compose.yml builds, tagged for this
# cluster -- kustomization.yaml expects `robot-router/<name>:local`.
docker build -f deploy/eam/Dockerfile -t robot-router/eam:local .
docker build -f deploy/mcp_server/Dockerfile -t robot-router/mcp-server:local .
docker build -f deploy/telemetry/Dockerfile -t robot-router/telemetry:local .
docker build -f deploy/console/Dockerfile -t robot-router/console:local .
docker build -f deploy/agent/Dockerfile -t robot-router/agent:local .

# k3d's cluster can't see the host's local Docker images by default --
# import them directly into it (no registry needed for a demo cluster).
k3d image import robot-router/eam:local robot-router/mcp-server:local \
  robot-router/telemetry:local robot-router/console:local \
  robot-router/agent:local -c robot-router

kubectl apply -k deploy/k3d

kubectl -n robot-router wait --for=condition=available --timeout=120s \
  deployment/eam deployment/mcp-server deployment/telemetry deployment/console

# Port-forward what a browser or curl needs -- these ports match what
# the console image was built expecting (VITE_EAM_URL, VITE_HTTP_API_URL
# both default to localhost:8000/8001, same as docker-compose.yml).
kubectl -n robot-router port-forward svc/eam 8000:8000 &
kubectl -n robot-router port-forward svc/mcp-server 8001:8001 &
kubectl -n robot-router port-forward svc/console 5173:5173 &
```

Open `http://localhost:5173`. Releasing a work order and running the
agent against it is the same two-step reproduction as docker-compose's
(see the root README): release it in the console, then apply
`agent-job.yaml` with a real work order id and `ANTHROPIC_API_KEY`
substituted in (see that file's header comment for the exact command).

Tear down with:

```bash
k3d cluster delete robot-router
```

## Not covered

Same list as `deploy/docker-compose.yml`'s "Not included here, and
why" -- the ROS 2 + Gazebo + Nav2 half of `adapters/vda5050_amr`,
`adapters/unitree` and `adapters/spot` (no long-running server
component to containerize), and the agent's lack of an automatic
trigger. Additionally here: no Ingress, no TLS, no resource
requests/limits, no HorizontalPodAutoscaler -- this is a one-node local
demo cluster, not a production-shaped deployment, and CLAUDE.md section
1 says plainly this repo isn't fleet-scale.
