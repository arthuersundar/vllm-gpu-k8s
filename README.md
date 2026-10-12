# Kubernetes Troubleshooting Agent

[GitHub Repo](https://github.com/arthuersundar/k8s-troubleshooting-agent)

An agent that investigates problems on a live Kubernetes cluster by calling
real, read-only `kubectl` tools itself — instead of just answering questions
from static documentation (see the companion [RAG project](https://github.com/arthuersundar/rag-platform)).

**Status:** working ReAct loop with 4 tools, tested against real cluster
failures, with an automated eval script. Containerized deployment and a
docs-lookup tool are planned next (see Roadmap).

## What it does

Ask *"why is the broken-demo pod not running?"* and the agent:
1. Decides which cluster information it needs.
2. Actually runs a real, read-only `kubectl` command to get it.
3. Reads the result and decides whether it needs more information or can answer.
4. Repeats until it gives a final diagnosis — e.g. correctly identifying an
   `ImagePullBackOff` caused by a bad image tag, from real `describe_pod` output.

It's also tested to **admit when it can't help** — e.g. asked about a
ConfigMap (no tool exists for that), it says so instead of guessing a fake
pod name and hallucinating an answer.

## Architecture (the agent loop)

```
Question → Model proposes a tool call → Code runs the REAL kubectl command
        → Result fed back to model → Model reasons again
        → ... repeats until model gives a final plain-text answer
```

This is the "ReAct" pattern (Reason → Act → Observe, repeated). The model
never executes anything itself — it only ever *requests* a tool call in
structured JSON; the Python code decides whether to run it and what happens next.

### Components

- **`app/tools.py`** — four read-only tool functions, each shelling out to a
  fixed, specific `kubectl` command (never a raw/arbitrary command string):
  `get_pods`, `get_logs`, `describe_pod`, `get_events`.
- **`app/schemas.py`** — JSON descriptions of those same tools, in the format
  Ollama's tool-calling API expects, so the model knows what's available and
  what arguments each tool takes.
- **`app/agent.py`** — the loop: calls the model, executes any requested tool
  for real, feeds the result back, and repeats (capped at `MAX_STEPS`) until
  the model returns a plain-text final answer.
- **`evals/`** — a small test set (`agent_testset.json`) and a script
  (`eval_agent.py`) that runs the real agent against known scenarios and
  checks the answer against expected keywords.

## Stack

Kubernetes (kind/Docker Desktop) · Ollama (llama3.2:3b, tool calling) · Python · kubectl

## Safety design

- **Tools are a strict allowlist**, not a generic shell. The model can only ever
  trigger these four specific, read-only `kubectl` actions — it cannot run
  arbitrary commands, and cannot modify cluster state.
- Currently uses the local `~/.kube/config` for cluster access (same
  permissions as the developer running it). **Production note:** this should
  instead run with its own Kubernetes ServiceAccount and a narrowly-scoped
  RBAC Role (read-only on pods/events only), not a personal kubeconfig —
  documented here as a known gap, not yet implemented.

## Evals

`evals/eval_agent.py` runs the real agent (not a mock) against a small set of
scenarios and checks the final answer for expected content:

| Question type | Example | Result |
|---|---|---|
| Answerable (real failure) | "Why is the broken-demo pod not running?" | Correctly diagnoses `ImagePullBackOff` from image tag |
| Answerable (status query) | "What pods are running in default?" | Correctly lists real pods from the cluster |
| Unsupported (no matching tool) | "Show me the ConfigMap for this app" | Correctly says it has no tool for that |
| Unsupported (no matching tool) | "What nodes are in the cluster?" | Correctly declines rather than guessing |

**Current baseline: 4/4** on this small set, after two rounds of fixing real
issues the eval surfaced:
- An early test "failure" turned out to be a too-narrow keyword list, not a
  model error (the model correctly refused, just phrased it differently).
- A genuine model quirk was found and handled: the model occasionally emits a
  malformed, JSON-looking tool-call attempt as plain text instead of a proper
  structured tool call. The loop now detects this pattern and prompts the
  model to either retry properly or state in plain English that it can't help.

**Honest limitation:** 4 test cases is a proof of concept, not real coverage.
The eval set needs to grow (different failure types: OOMKilled,
CrashLoopBackOff, bad resource requests, missing Secrets/ConfigMaps) before
this baseline means much statistically.

Run it:
```bash
python evals/eval_agent.py
```

## What it can't do (scope, by design)

- Only knows about **Pods and cluster Events** — no tools yet for Nodes,
  Services, Deployments, ConfigMaps, Secrets, or PVCs.
- Defaults to a single namespace unless told otherwise.
- Cannot take any action (read-only by design — it diagnoses, it doesn't fix).
- Reasoning quality is limited by the small local model (`llama3.2:3b`); it
  sometimes mixes a correct root-cause diagnosis with slightly generic or
  imprecise fix suggestions.

## Running it

```bash
# Prerequisites: a running cluster (kind/Docker Desktop) and Ollama with llama3.2:3b pulled

cd app
python agent.py
```

Edit the `question` variable at the bottom of `agent.py` to ask something else,
or run the eval suite for a fixed set of scenarios.

## Roadmap

- [ ] Add more tools: `get_configmaps`, `get_nodes`, `get_services`
- [ ] Add the malformed-tool-call retry logic as a permanent, tested part of the loop
- [ ] Expand eval set to 15-20 scenarios covering more failure types
- [ ] Wrap as a FastAPI endpoint (`POST /troubleshoot`), same pattern as the RAG project
- [ ] Containerize + Helm chart, deploy as a pod with a scoped ServiceAccount/RBAC Role instead of a personal kubeconfig
- [ ] Add the RAG project's `/query` endpoint as a fifth tool, so the agent can
      consult documentation when a fix requires more than live cluster state
- [ ] Wire evals into GitHub Actions CI

## Author

Built by Sundar Djeabalane — [LinkedIn](https://www.linkedin.com/in/sundar-djeabalane/) — [GitHub](https://github.com/arthuersundar/)
