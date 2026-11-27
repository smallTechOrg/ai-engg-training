# Curriculum map

<!-- Generated from curriculum.toml by `./run map`. Do not edit by hand. -->

21 modules, 99 lessons, 26 ready. Each lesson shows a concept on its own, then applies it to the running scenario: **IT helpdesk assistant**.

| Status | Meaning |
|---|---|
| ✅ ready | Written, tested, runnable |
| 🚧 draft | Runnable but still being refined |
| ⬜ planned | Outlined; not written yet |

## Modules

| # | Module | Lessons ready |
|---|---|---|
| 00 | [Setup and Python for AI work](modules/00-setup/README.md) | 5 / 5 |
| 01 | [Foundations: talking to an LLM](modules/01-foundations/README.md) | 7 / 7 |
| 02 | [Tools and agents by hand](modules/02-tools-and-agents-by-hand/README.md) | 1 / 5 |
| 03 | [Embeddings and semantic search](modules/03-embeddings-and-search/README.md) | 1 / 5 |
| 04 | [RAG by hand](modules/04-rag-by-hand/README.md) | 1 / 4 |
| 05 | [Serving AI apps: FastAPI, Streamlit, Gradio](modules/05-serving-ai-apps/README.md) | 1 / 5 |
| 06 | [LangChain core: chains, memory, RAG](modules/06-langchain-core/README.md) | 1 / 5 |
| 07 | [LangChain agents and tool use](modules/07-langchain-agents/README.md) | 1 / 5 |
| 08 | [LangGraph: stateful workflows and routing](modules/08-langgraph-workflows/README.md) | 1 / 4 |
| 09 | [LangGraph: cycles, human-in-the-loop, persistence](modules/09-langgraph-cycles-hitl/README.md) | 1 / 5 |
| 10 | [Tracing, evaluation and testing](modules/10-tracing-and-evaluation/README.md) | 1 / 4 |
| 11 | [MCP: architecture and custom servers](modules/11-mcp-servers/README.md) | 1 / 5 |
| 12 | [MCP: ecosystem integrations](modules/12-mcp-ecosystem/README.md) | 1 / 4 |
| 13 | [Deep agents: reflection, planning, long-term memory](modules/13-deep-agents/README.md) | 1 / 4 |
| 14 | [CrewAI: multi-agent orchestration](modules/14-crewai/README.md) | 1 / 4 |
| 15 | [Agentic RAG and GraphRAG](modules/15-agentic-rag/README.md) | 1 / 5 |
| 16 | [Containers and deployment](modules/16-containers-and-deployment/README.md) | 0 / 5 |
| 17 | [Monitoring, evaluation and fine-tuning](modules/17-monitoring-and-fine-tuning/README.md) | 0 / 5 |
| 18 | [Guardrails and safety](modules/18-guardrails/README.md) | 0 / 5 |
| 19 | [Workflow automation with n8n](modules/19-workflow-automation-n8n/README.md) | 0 / 4 |
| 20 | [Capstone](modules/20-capstone/README.md) | 0 / 4 |

## 00 · Setup and Python for AI work

Get a reproducible environment and the Python habits AI work needs.

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 00.1 | [The AI engineering landscape and this repo](modules/00-setup/01-the-ai-engineering-landscape-and-this-repo/README.md) | ✅ ready | - |
| 00.2 | [Environments and dependencies: uv, venv, pip, pyenv, conda](modules/00-setup/02-environments-and-dependencies/README.md) | ✅ ready | - |
| 00.3 | [Secrets and configuration with .env](modules/00-setup/03-secrets-and-configuration-with-env/README.md) | ✅ ready | - |
| 00.4 | [Git and GitHub essentials for AI projects](modules/00-setup/04-git-and-github-essentials-for-ai-projects/README.md) | ✅ ready | - |
| 00.5 | [Async Python: concurrent LLM calls](modules/00-setup/05-async-python/README.md) | ✅ ready | chat |

## 01 · Foundations: talking to an LLM

Everything a single model call can do, before any tool or framework.

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 01.1 | [Your first LLM call](modules/01-foundations/01-first-llm-call/README.md) | ✅ ready | chat, stream |
| 01.2 | [Messages, roles and multi-turn conversation](modules/01-foundations/02-messages-roles-and-multi-turn-conversation/README.md) | ✅ ready | chat |
| 01.3 | [Streaming and sampling parameters](modules/01-foundations/03-streaming-and-sampling-parameters/README.md) | ✅ ready | chat, stream |
| 01.4 | [Tokens, context windows and cost](modules/01-foundations/04-tokens-context-windows-and-cost/README.md) | ✅ ready | chat |
| 01.5 | [Prompt engineering: zero-shot, few-shot, chain-of-thought](modules/01-foundations/05-prompt-engineering/README.md) | ✅ ready | chat |
| 01.6 | [Structured output: JSON mode and schemas](modules/01-foundations/06-structured-output/README.md) | ✅ ready | chat, json |
| 01.7 | [Capstone: helpdesk ticket triage with one call](modules/01-foundations/07-capstone-helpdesk-ticket-triage-with-one-call/README.md) | ✅ ready | chat, json |

## 02 · Tools and agents by hand

Tool calling and the agent loop in plain Python, so frameworks hold no mystery.

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 02.1 | [Function calling: letting the model ask for a tool](modules/02-tools-and-agents-by-hand/01-function-calling/README.md) | ✅ ready | chat, tools |
| 02.2 | The agent loop: reason, act, observe | ⬜ planned | chat, tools |
| 02.3 | Conversation memory and context management | ⬜ planned | chat |
| 02.4 | Tool failures, retries and iteration limits | ⬜ planned | chat, tools |
| 02.5 | Capstone: helpdesk agent that looks up tickets and resets passwords | ⬜ planned | chat, tools |

## 03 · Embeddings and semantic search

Turn text into vectors and search by meaning.

Optional packages: `rag`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 03.1 | [What embeddings are: similarity by hand](modules/03-embeddings-and-search/01-what-embeddings-are/README.md) | ✅ ready | embeddings |
| 03.2 | Chunking strategies | ⬜ planned | embeddings |
| 03.3 | Vector stores: ChromaDB and FAISS | ⬜ planned | embeddings |
| 03.4 | Hybrid search: keywords plus vectors | ⬜ planned | embeddings |
| 03.5 | Capstone: semantic search over the helpdesk knowledge base | ⬜ planned | embeddings |

## 04 · RAG by hand

Retrieval-augmented generation built from parts you already understand.

Optional packages: `rag`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 04.1 | [The RAG pipeline: retrieve, augment, generate](modules/04-rag-by-hand/01-the-rag-pipeline/README.md) | ✅ ready | chat, embeddings |
| 04.2 | Grounding, citations and saying 'I don't know' | ⬜ planned | chat, embeddings |
| 04.3 | Measuring retrieval and answer quality | ⬜ planned | chat, embeddings |
| 04.4 | Capstone: helpdesk answers grounded in the knowledge base | ⬜ planned | chat, embeddings |

## 05 · Serving AI apps: FastAPI, Streamlit, Gradio

Put a model behind an API and a simple user interface.

Optional packages: `apps`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 05.1 | [REST and FastAPI basics with Pydantic models](modules/05-serving-ai-apps/01-rest-and-fastapi-basics-with-pydantic-models/README.md) | ✅ ready | chat |
| 05.2 | Streaming responses with Server-Sent Events | ⬜ planned | chat, stream |
| 05.3 | A chat UI in Streamlit | ⬜ planned | chat, stream |
| 05.4 | A demo UI in Gradio; choosing between the two | ⬜ planned | chat |
| 05.5 | Capstone: helpdesk assistant as an API with a chat front-end | ⬜ planned | chat, stream |

## 06 · LangChain core: chains, memory, RAG

The same ideas as modules 01-04, expressed with LangChain.

Optional packages: `langchain`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 06.1 | [Runnables and LCEL: prompt | model | parser](modules/06-langchain-core/01-runnables-and-lcel/README.md) | ✅ ready | chat |
| 06.2 | Prompt templates and output parsers | ⬜ planned | chat, json |
| 06.3 | Conversation memory across turns and sessions | ⬜ planned | chat |
| 06.4 | Loaders, splitters and retrievers: RAG with LangChain | ⬜ planned | chat, embeddings |
| 06.5 | Capstone: the helpdesk RAG chain | ⬜ planned | chat, embeddings |

## 07 · LangChain agents and tool use

Agents that choose and call tools, built with LangChain.

Optional packages: `langchain`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 07.1 | [Custom tools and input schemas](modules/07-langchain-agents/01-custom-tools-and-input-schemas/README.md) | ✅ ready | chat, tools |
| 07.2 | ReAct and plan-and-execute agents | ⬜ planned | chat, tools |
| 07.3 | Agents over SQL data | ⬜ planned | chat, tools |
| 07.4 | Structured final answers and streaming intermediate steps | ⬜ planned | chat, tools, stream |
| 07.5 | Capstone: helpdesk agent with search, ticket and database tools | ⬜ planned | chat, tools |

## 08 · LangGraph: stateful workflows and routing

Model a workflow as a graph with explicit state.

Optional packages: `langgraph`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 08.1 | [Why graphs: state, nodes and edges](modules/08-langgraph-workflows/01-why-graphs/README.md) | ✅ ready | chat |
| 08.2 | Conditional edges and routing to specialists | ⬜ planned | chat |
| 08.3 | Streaming, visualising and testing a graph | ⬜ planned | chat, stream |
| 08.4 | Capstone: helpdesk router with specialist nodes | ⬜ planned | chat |

## 09 · LangGraph: cycles, human-in-the-loop, persistence

Loops, approvals and workflows that survive a restart.

Optional packages: `langgraph` · Services: `REDIS_URL`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 09.1 | [Cycles and self-correction loops](modules/09-langgraph-cycles-hitl/01-cycles-and-self-correction-loops/README.md) | ✅ ready | chat |
| 09.2 | Human-in-the-loop: interrupt, approve, resume | ⬜ planned | chat |
| 09.3 | Checkpointers: SQLite and Redis persistence | ⬜ planned | chat |
| 09.4 | Parallel workers and sub-graphs | ⬜ planned | chat |
| 09.5 | Capstone: helpdesk change request with an approval gate | ⬜ planned | chat |

## 10 · Tracing, evaluation and testing

See what an LLM application did and measure whether it is good.

Optional packages: `langchain` · Services: `LANGSMITH_API_KEY`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 10.1 | [Tracing runs: spans, latency and token cost](modules/10-tracing-and-evaluation/01-tracing-runs/README.md) | ✅ ready | chat |
| 10.2 | Evaluation datasets and heuristic evaluators | ⬜ planned | chat |
| 10.3 | LLM-as-judge and regression testing of prompts | ⬜ planned | chat |
| 10.4 | Capstone: an evaluation suite for the helpdesk assistant | ⬜ planned | chat |

## 11 · MCP: architecture and custom servers

The Model Context Protocol and how to write a server.

Optional packages: `mcp`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 11.1 | [MCP architecture: hosts, clients, servers, primitives](modules/11-mcp-servers/01-mcp-architecture/README.md) | ✅ ready | - |
| 11.2 | A minimal server: tools, resources and prompts | ⬜ planned | - |
| 11.3 | Writing an MCP client; discovery and negotiation | ⬜ planned | chat, tools |
| 11.4 | Security, validation and debugging with the Inspector | ⬜ planned | - |
| 11.5 | Capstone: a helpdesk MCP server for tickets and assets | ⬜ planned | chat, tools |

## 12 · MCP: ecosystem integrations

Use existing MCP servers and plug them into agent frameworks.

Optional packages: `mcp`, `langgraph`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 12.1 | [Ready-made servers: SQLite and filesystem](modules/12-mcp-ecosystem/01-ready-made-servers/README.md) | ✅ ready | chat, tools |
| 12.2 | Chaining several servers in one session | ⬜ planned | chat, tools |
| 12.3 | MCP tools inside LangChain, LangGraph and CrewAI | ⬜ planned | chat, tools |
| 12.4 | Capstone: query-to-report pipeline for the helpdesk | ⬜ planned | chat, tools |

## 13 · Deep agents: reflection, planning, long-term memory

Agents that critique their work, plan ahead and remember.

Optional packages: `langgraph`, `rag`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 13.1 | [Reflection: generate, critique, revise](modules/13-deep-agents/01-reflection/README.md) | ✅ ready | chat |
| 13.2 | Planning and replanning | ⬜ planned | chat, tools |
| 13.3 | Long-term memory: episodic, semantic, procedural | ⬜ planned | chat, embeddings |
| 13.4 | Capstone: a helpdesk agent that learns from resolved tickets | ⬜ planned | chat, tools, embeddings |

## 14 · CrewAI: multi-agent orchestration

Role-based agents working as a team.

Optional packages: `crewai`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 14.1 | [Agents, tasks, crews and processes](modules/14-crewai/01-agents-tasks-crews-and-processes/README.md) | ✅ ready | chat |
| 14.2 | Sequential and hierarchical processes; delegation | ⬜ planned | chat, tools |
| 14.3 | Tools, MCP and LangGraph alongside a crew | ⬜ planned | chat, tools |
| 14.4 | Capstone: a helpdesk incident-response crew | ⬜ planned | chat, tools |

## 15 · Agentic RAG and GraphRAG

Retrieval that decides, checks and corrects itself.

Optional packages: `rag`, `langgraph`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 15.1 | [RAG failure modes and how to diagnose them](modules/15-agentic-rag/01-rag-failure-modes-and-how-to-diagnose-them/README.md) | ✅ ready | chat, embeddings |
| 15.2 | Agentic, self- and corrective RAG | ⬜ planned | chat, tools, embeddings |
| 15.3 | Re-ranking, HyDE and query expansion | ⬜ planned | chat, embeddings |
| 15.4 | GraphRAG: knowledge graphs and multi-hop questions | ⬜ planned | chat, embeddings |
| 15.5 | Capstone: benchmark agentic against plain RAG on helpdesk questions | ⬜ planned | chat, embeddings |

## 16 · Containers and deployment

Package an agent and ship it.

Optional packages: `apps` · Services: `DOCKER`, `REDIS_URL`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 16.1 | Docker fundamentals and a production Dockerfile | ⬜ planned | - |
| 16.2 | Docker Compose: API, vector store, Redis, worker | ⬜ planned | chat |
| 16.3 | Health checks, configuration and secrets | ⬜ planned | - |
| 16.4 | CI/CD and rollout strategies | ⬜ planned | - |
| 16.5 | Capstone: the helpdesk stack in containers | ⬜ planned | chat |

## 17 · Monitoring, evaluation and fine-tuning

Operate an agent: traces, metrics, dashboards, and when to fine-tune.

Optional packages: `observability` · Services: `OTEL_EXPORTER_OTLP_ENDPOINT`, `PROMETHEUS_URL`, `GRAFANA_URL`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 17.1 | Logs, metrics and traces with OpenTelemetry | ⬜ planned | chat |
| 17.2 | Prometheus metrics and Grafana dashboards | ⬜ planned | chat |
| 17.3 | Cost tracking, budgets and service-level objectives | ⬜ planned | chat |
| 17.4 | Fine-tuning: when it is warranted; LoRA and QLoRA | ⬜ planned | - |
| 17.5 | Capstone: a monitored helpdesk assistant | ⬜ planned | chat |

## 18 · Guardrails and safety

Defend an LLM application against misuse and mistakes.

Optional packages: `guardrails`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 18.1 | The risk landscape and prompt injection | ⬜ planned | chat |
| 18.2 | Input and output rails | ⬜ planned | chat |
| 18.3 | Validators and detecting personal data | ⬜ planned | chat |
| 18.4 | Red-teaming a safety stack | ⬜ planned | chat |
| 18.5 | Capstone: a guarded helpdesk assistant | ⬜ planned | chat |

## 19 · Workflow automation with n8n

Visual workflows that trigger, call and connect agents.

Services: `N8N_URL`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 19.1 | n8n concepts: workflows, nodes, triggers, credentials | ⬜ planned | - |
| 19.2 | Webhooks, HTTP requests and model nodes | ⬜ planned | chat |
| 19.3 | Error handling, schedules and expressions | ⬜ planned | - |
| 19.4 | Capstone: a helpdesk ticket workflow calling an agent | ⬜ planned | chat |

## 20 · Capstone

Design, build, deploy and present a complete agentic system.

Optional packages: `all`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 20.1 | Choosing a problem and designing the architecture | ⬜ planned | - |
| 20.2 | Building the core: retrieval, graph, tools, guardrails | ⬜ planned | chat, tools, embeddings |
| 20.3 | Deploying, monitoring and securing | ⬜ planned | chat |
| 20.4 | Documenting and demonstrating | ⬜ planned | - |
