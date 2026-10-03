# Deploying to Azure Kubernetes Service

This guide runs the monitoring API/dashboard as one container and scales the server simulator with Kubernetes. **Powershell commands**.

## 1. Install and log in

Install Docker Desktop, Azure CLI, and `kubectl`, then run:

```powershell
az login
az aks install-cli
docker version
kubectl version --client
```

## 2. Create Azure resources

Resource group
  > Azure Container Resource
  > Azure Kubernetes Service

Go to AKS service, run `az aks get-credentials --resource-group rg-aks-telemetry-demo --name aks-telemetry-demo --overwrite-existing`

## 3. Build and push the images

Build the images from the repository root:

`az acr show --name [PUT ACR NAME IN HERE] --query loginServer --output tsv` - this gets login server
`az acr login --name [PUT ACR NAME IN HERE]`

```powershell
$env:ACR_LOGIN_SERVER = "PUT LOGIN SERVER HERE"
docker build -f Dockerfile.monitoring -t "$env:ACR_LOGIN_SERVER/telemetry-monitor:1" .
docker build -f Dockerfile.server -t "$env:ACR_LOGIN_SERVER/telemetry-server:1" .
docker push "$env:ACR_LOGIN_SERVER/telemetry-monitor:1"
docker push "$env:ACR_LOGIN_SERVER/telemetry-server:1"
```

## 4. Create the Kubernetes manifest

The ready-to-apply manifests are in `k8s\`. Replace
`YOUR_ACR_LOGIN_SERVER` with `$env:ACR_LOGIN_SERVER` in the two deployment
files:

Replace the image placeholders and deploy:

```powershell
(Get-Content k8s\monitoring-deployment.yaml -Raw).Replace(
  "YOUR_ACR_LOGIN_SERVER",
  $env:ACR_LOGIN_SERVER
) | Set-Content k8s\monitoring-deployment.yaml
(Get-Content k8s\server-deployment.yaml -Raw).Replace(
  "YOUR_ACR_LOGIN_SERVER",
  $env:ACR_LOGIN_SERVER
) | Set-Content k8s\server-deployment.yaml

kubectl apply -f k8s
kubectl -n telemetry-demo get pods --watch
```

If image pulling is failing, go to ARC > Access Control IAM and add role assignment for AcrPull.

Or if it's to do with agent pool, go to agent pool and Azure Role Assignments and grant it ArcPull then refresh.

Can force a refresh with:

```
kubectl rollout restart deployment/server -n telemetry-demo
kubectl rollout restart deployment/monitoring -n telemetry-demo
```

## 5. Scale and inspect

Expose public IP:
`kubectl -n telemetry-demo get svc monitoring`

Save to powershell env with:
```
$env:APP_IP = kubectl -n telemetry-demo get svc monitoring `
  --output jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

So can then test endpoints with:

```Invoke-RestMethod "http://${env:APP_IP}:8000/health"```

```Invoke-RestMethod "http://$env:APP_IP`:8000/nodes"```

**Scaling commands:**
```powershell
kubectl -n telemetry-demo scale deployment/server --replicas=5
kubectl -n telemetry-demo get pods
kubectl -n telemetry-demo logs deployment/monitoring
kubectl -n telemetry-demo logs deployment/server
kubectl -n telemetry-demo get svc monitoring
```

## 6. Clean up

Assign env:

`$env:RESOURCE_GROUP = "YOUR RESOURCE GROUP NAME"`

```powershell
kubectl delete namespace telemetry-demo
az group delete --name $env:RESOURCE_GROUP --yes --no-wait
```
