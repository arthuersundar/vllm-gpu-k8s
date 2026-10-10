# vLLM GPU Serving on Kubernetes

[GitHub Repo](https://github.com/arthuersundar/vllm-gpu-k8s)

A Helm chart for serving open LLMs with [vLLM](https://github.com/vllm-project/vllm)
on Kubernetes GPU nodes, plus a throughput and cost benchmark showing when
self-hosting pays off.

**Status:** benchmark complete (RunPod GPU). Helm chart built and validated on a
local cluster. Deployment on a Kubernetes GPU node (EKS) pending GPU quota.

## Why this project

My other projects ([RAG platform](https://github.com/arthuersundar/rag-platform),
[K8s troubleshooting agent](https://github.com/arthuersundar/k8s-troubleshooting-agent))
run models through Ollama on a laptop: simple, but one request at a time. Production
serving needs many concurrent users on expensive GPUs. vLLM addresses this with
continuous batching and PagedAttention (GPU KV-cache memory managed in pages, like
OS virtual memory), so far more requests fit on one GPU at once.

This repo answers two questions:

1. How much does batching actually help, and what does it do to cost per token?
2. What does a correct Kubernetes deployment of a GPU model server look like?

## Benchmark results

**Setup:** RunPod pod, `vllm/vllm-openai:latest`, NVIDIA RTX A5000 (24GB, $0.27/hr),
model `Qwen/Qwen3-8B`, ~150-word answers (`max_tokens` 256, thinking disabled,
~175 output tokens per request).

| Concurrency | Total tok/s | Avg latency | Cost per 1M output tokens |
|---|---|---|---|
| 1  | 40    | 4.37s | ~$1.88 |
| 4  | 145   | 4.54s | ~$0.52 |
| 8  | 281   | 4.62s | ~$0.27 |
| 16 | 558   | 4.81s | ~$0.13 |
| 32 | 1,050 | 4.92s | ~$0.07 |
| 64 | 1,904 | 5.54s | ~$0.04 |

Cost = GPU $/hr ÷ (tok/s × 3600) × 1,000,000

**Findings**

- Throughput scaled **~48x** from 1 to 64 concurrent requests while latency rose
  only **~27%**: continuous batching at work.
- Not yet saturated at 64. Latency began to bend between 32 and 64 (+13% vs +3%
  before), so the knee is likely somewhere above that.
- **Self-hosting is only cheap when the GPU is busy.** A single user costs ~45x
  more per token than 64 concurrent users on the same hardware.
- Practical target: ~32-64 concurrent requests per A5000. On Kubernetes, scaling
  should key on in-flight requests per pod, not CPU usage.
- Caveat: an 8B open model is not a quality match for frontier hosted models.
  This compares cost per token, not capability.

## Helm chart

`charts/vllm` deploys a single vLLM model server:

- **Deployment** requesting `nvidia.com/gpu`, with `Recreate` strategy (with one
  GPU, a rolling update would leave the new pod Pending while the old one holds it)
- **PVC** for the Hugging Face model cache, so weights download once, kept on
  `helm uninstall` (`helm.sh/resource-policy: keep`) to avoid re-downloading
- **Secret** for the API key (`VLLM_API_KEY`), created with kubectl, never in git
- **Service** exposing the OpenAI-compatible API on port 8000
- **`/dev/shm` memory volume**, the Kubernetes equivalent of Docker's `--ipc=host`

### Design decisions

| Decision | Reason |
|---|---|
| `startupProbe`: 60 checks × 10s | Up to 10 minutes to download and load the model before liveness checks can restart it |
| CPU/memory requests (2 CPU, 16Gi) | Without them the pod is `BestEffort`: scheduled blindly and evicted first under memory pressure. With them it is `Burstable` |
| No CPU limit | Avoids throttling request handling; the request alone secures scheduling and QoS |
| GPU taint toleration | GPU nodes are commonly tainted `nvidia.com/gpu:NoSchedule` to keep ordinary pods off them |
| Model and context length in `values.yaml` | Swap models without editing templates |

### Validation on a local cluster (no GPU)

Installed on a 2-node kind cluster to verify the chart before paying for GPU nodes:

- Initially the pod was `BestEffort` and the scheduler only reported the missing GPU.
- After adding requests, the pod became `Burstable` and the scheduler correctly
  reported both constraints:
  `0/2 nodes are available: 1 Insufficient memory, 1 Insufficient nvidia.com/gpu, 1 node(s) had untolerated taint(s)`

The chart is correct; it needs a node with a GPU and ≥16Gi allocatable memory.

## Deploying

Prerequisites: a cluster with a GPU node (e.g. EKS `g5.xlarge`) and the
[NVIDIA device plugin](https://github.com/NVIDIA/k8s-device-plugin) or GPU Operator
installed, so nodes advertise `nvidia.com/gpu`.

```bash
# API key: any random string, shared by the server and its clients
kubectl create secret generic vllm-secret --from-literal=VLLM_API_KEY=<random-key>

helm install llm charts/vllm
kubectl get pods -w        # first start downloads the model; can take several minutes

kubectl port-forward svc/llm-vllm 8000:8000
curl http://localhost:8000/v1/models -H "Authorization: Bearer <random-key>"
```

To change the model: `helm install llm charts/vllm --set model=<hf-model-id>`.

**Cleanup:** `helm uninstall llm` keeps the model cache PVC by design. Delete it
with `kubectl delete pvc llm-vllm-cache` when no longer needed. Always scale down
or delete GPU nodes after testing; they bill by the hour.

## Roadmap

- [x] GPU benchmark: throughput, latency and cost per token across concurrency
- [x] Helm chart with GPU scheduling, model cache, probes and QoS
- [x] Chart validated on a local cluster
- [ ] Deploy on EKS with a GPU node group and the NVIDIA device plugin
- [ ] Find the saturation point (128-256 concurrency)
- [ ] Same-prompt comparison against Ollama on CPU
- [ ] Prometheus metrics from vLLM's `/metrics` endpoint, Grafana dashboard
- [ ] Autoscaling on in-flight requests (KEDA) instead of CPU
- [ ] Point the RAG platform and the troubleshooting agent at this server

## Author

Built by Sundar Djeabalane ·
[LinkedIn](https://www.linkedin.com/in/sundar-djeabalane/) ·
[GitHub](https://github.com/arthuersundar/)
