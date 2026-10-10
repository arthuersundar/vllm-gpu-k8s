\# Project Notes



\## vLLM GPU benchmark (RunPod, Oct 2026)



\*\*Setup\*\*

\- Platform: RunPod pod, "vLLM Latest" template (vllm/vllm-openai:latest)

\- GPU: NVIDIA RTX A5000 (24GB VRAM), $0.27/hr

\- Model: Qwen/Qwen3-8B, max\_model\_len 8128

\- Request: \~150-word answer, max\_tokens 256, thinking disabled

\- Avg output: \~175 tokens per request (no truncation)

\- Client: Python ThreadPoolExecutor, 2 requests per concurrency slot



\*\*Results\*\*



| Concurrency | Total tok/s | Avg latency | Cost per 1M output tokens |

|---|---|---|---|

| 1  | 40    | 4.37s | \~$1.88 |

| 4  | 145   | 4.54s | \~$0.52 |

| 8  | 281   | 4.62s | \~$0.27 |

| 16 | 558   | 4.81s | \~$0.13 |

| 32 | 1,050 | 4.92s | \~$0.07 |

| 64 | 1,904 | 5.54s | \~$0.04 |



Cost formula: $/hr ÷ (tok/s × 3600) × 1,000,000



\*\*Findings\*\*

\- Throughput scaled \~48x from 1 to 64 concurrent requests, while latency rose only \~27%

&#x20; (continuous batching + PagedAttention).

\- Not saturated at 64; latency started bending between 32 and 64 (+13% vs +3% before).

\- Self-hosting is only cheap when the GPU is kept busy: idle/single-user costs \~45x more

&#x20; per token than at 64 concurrency.

\- Sweet spot: \~32-64 concurrent requests per A5000. Candidate autoscaling trigger on K8s:

&#x20; in-flight requests per pod (\~48), not CPU.

\- Comparison caveat: an 8B model is not a quality match for frontier hosted models;

&#x20; this compares cost per token, not capability.



\*\*To do\*\*

\- Measure Ollama (llama3.2:3b, laptop CPU) tok/s for the same prompt, for comparison.

\- Find saturation point (128-256 concurrency).

\- Deploy the same model via the charts/vllm Helm chart on a K8s GPU node.



\## Other findings

\- RAG grounding test: out-of-scope questions (Docker Compose, K8s 1.32 sidecar changes)

&#x20; correctly answered "I don't know".

\- Eval set v1: retrieval 6/6, refusal 3/3, grounded answers 6/6 (small set, same-model judge).

