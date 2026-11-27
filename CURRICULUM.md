# Curriculum map

<!-- Generated from curriculum.toml by `./run map`. Do not edit by hand. -->

21 modules, 99 lessons, 99 ready. Each lesson shows a concept on its own, then applies it to the running scenario: **IT helpdesk assistant**.

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
| 02 | [Tools and agents by hand](modules/02-tools-and-agents-by-hand/README.md) | 5 / 5 |
| 03 | [Embeddings and semantic search](modules/03-embeddings-and-search/README.md) | 5 / 5 |
| 04 | [RAG by hand](modules/04-rag-by-hand/README.md) | 4 / 4 |
| 05 | [Serving AI apps: FastAPI, Streamlit, Gradio](modules/05-serving-ai-apps/README.md) | 5 / 5 |
| 06 | [LangChain core: chains, memory, RAG](modules/06-langchain-core/README.md) | 5 / 5 |
| 07 | [LangChain agents and tool use](modules/07-langchain-agents/README.md) | 5 / 5 |
| 08 | [LangGraph: stateful workflows and routing](modules/08-langgraph-workflows/README.md) | 4 / 4 |
| 09 | [LangGraph: cycles, human-in-the-loop, persistence](modules/09-langgraph-cycles-hitl/README.md) | 5 / 5 |
| 10 | [Tracing, evaluation and testing](modules/10-tracing-and-evaluation/README.md) | 4 / 4 |
| 11 | [MCP: architecture and custom servers](modules/11-mcp-servers/README.md) | 5 / 5 |
| 12 | [MCP: ecosystem integrations](modules/12-mcp-ecosystem/README.md) | 4 / 4 |
| 13 | [Deep agents: reflection, planning, long-term memory](modules/13-deep-agents/README.md) | 4 / 4 |
| 14 | [CrewAI: multi-agent orchestration](modules/14-crewai/README.md) | 4 / 4 |
| 15 | [Agentic RAG and GraphRAG](modules/15-agentic-rag/README.md) | 5 / 5 |
| 16 | [Containers and deployment](modules/16-containers-and-deployment/README.md) | 5 / 5 |
| 17 | [Monitoring, evaluation and fine-tuning](modules/17-monitoring-and-fine-tuning/README.md) | 5 / 5 |
| 18 | [Guardrails and safety](modules/18-guardrails/README.md) | 5 / 5 |
| 19 | [Workflow automation with n8n](modules/19-workflow-automation-n8n/README.md) | 4 / 4 |
| 20 | [Capstone](modules/20-capstone/README.md) | 4 / 4 |

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
| 02.2 | [The agent loop: reason, act, observe](modules/02-tools-and-agents-by-hand/02-the-agent-loop/README.md) | ✅ ready | chat, tools |
| 02.3 | [Conversation memory and context management](modules/02-tools-and-agents-by-hand/03-conversation-memory-and-context-management/README.md) | ✅ ready | chat |
| 02.4 | [Tool failures, retries and iteration limits](modules/02-tools-and-agents-by-hand/04-tool-failures-retries-and-iteration-limits/README.md) | ✅ ready | chat, tools |
| 02.5 | [Capstone: helpdesk agent that looks up tickets and resets passwords](modules/02-tools-and-agents-by-hand/05-capstone-helpdesk-agent-that-looks-up-tickets-an/README.md) | ✅ ready | chat, tools |

## 03 · Embeddings and semantic search

Turn text into vectors and search by meaning.

Optional packages: `rag`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 03.1 | [What embeddings are: similarity by hand](modules/03-embeddings-and-search/01-what-embeddings-are/README.md) | ✅ ready | embeddings |
| 03.2 | [Chunking strategies](modules/03-embeddings-and-search/02-chunking-strategies/README.md) | ✅ ready | embeddings |
| 03.3 | [Vector stores: ChromaDB and FAISS](modules/03-embeddings-and-search/03-vector-stores/README.md) | ✅ ready | embeddings |
| 03.4 | [Hybrid search: keywords plus vectors](modules/03-embeddings-and-search/04-hybrid-search/README.md) | ✅ ready | embeddings |
| 03.5 | [Capstone: semantic search over the helpdesk knowledge base](modules/03-embeddings-and-search/05-capstone-semantic-search-over-the-helpdesk-knowl/README.md) | ✅ ready | embeddings |

## 04 · RAG by hand

Retrieval-augmented generation built from parts you already understand.

Optional packages: `rag`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 04.1 | [The RAG pipeline: retrieve, augment, generate](modules/04-rag-by-hand/01-the-rag-pipeline/README.md) | ✅ ready | chat, embeddings |
| 04.2 | [Grounding, citations and saying 'I don't know'](modules/04-rag-by-hand/02-grounding-citations-and-saying-i-don-t-know/README.md) | ✅ ready | chat, embeddings |
| 04.3 | [Measuring retrieval and answer quality](modules/04-rag-by-hand/03-measuring-retrieval-and-answer-quality/README.md) | ✅ ready | chat, embeddings |
| 04.4 | [Capstone: helpdesk answers grounded in the knowledge base](modules/04-rag-by-hand/04-capstone-helpdesk-answers-grounded-in-the-knowle/README.md) | ✅ ready | chat, embeddings |

## 05 · Serving AI apps: FastAPI, Streamlit, Gradio

Put a model behind an API and a simple user interface.

Optional packages: `apps`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 05.1 | [REST and FastAPI basics with Pydantic models](modules/05-serving-ai-apps/01-rest-and-fastapi-basics-with-pydantic-models/README.md) | ✅ ready | chat |
| 05.2 | [Streaming responses with Server-Sent Events](modules/05-serving-ai-apps/02-streaming-responses-with-server-sent-events/README.md) | ✅ ready | chat, stream |
| 05.3 | [A chat UI in Streamlit](modules/05-serving-ai-apps/03-a-chat-ui-in-streamlit/README.md) | ✅ ready | chat, stream |
| 05.4 | [A demo UI in Gradio; choosing between the two](modules/05-serving-ai-apps/04-a-demo-ui-in-gradio-choosing-between-the-two/README.md) | ✅ ready | chat |
| 05.5 | [Capstone: helpdesk assistant as an API with a chat front-end](modules/05-serving-ai-apps/05-capstone-helpdesk-assistant-as-an-api-with-a-cha/README.md) | ✅ ready | chat, stream |

## 06 · LangChain core: chains, memory, RAG

The same ideas as modules 01-04, expressed with LangChain.

Optional packages: `langchain`, `langgraph`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 06.1 | [Runnables and LCEL: prompt | model | parser](modules/06-langchain-core/01-runnables-and-lcel/README.md) | ✅ ready | chat |
| 06.2 | [Prompt templates and output parsers](modules/06-langchain-core/02-prompt-templates-and-output-parsers/README.md) | ✅ ready | chat, json |
| 06.3 | [Conversation memory across turns and sessions](modules/06-langchain-core/03-conversation-memory-across-turns-and-sessions/README.md) | ✅ ready | chat |
| 06.4 | [Loaders, splitters and retrievers: RAG with LangChain](modules/06-langchain-core/04-loaders-splitters-and-retrievers/README.md) | ✅ ready | chat, embeddings |
| 06.5 | [Capstone: the helpdesk RAG chain](modules/06-langchain-core/05-capstone-the-helpdesk-rag-chain/README.md) | ✅ ready | chat, embeddings |

## 07 · LangChain agents and tool use

Agents that choose and call tools, built with LangChain.

Optional packages: `langchain`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 07.1 | [Custom tools and input schemas](modules/07-langchain-agents/01-custom-tools-and-input-schemas/README.md) | ✅ ready | chat, tools |
| 07.2 | [ReAct and plan-and-execute agents](modules/07-langchain-agents/02-react-and-plan-and-execute-agents/README.md) | ✅ ready | chat, tools |
| 07.3 | [Agents over SQL data](modules/07-langchain-agents/03-agents-over-sql-data/README.md) | ✅ ready | chat, tools |
| 07.4 | [Structured final answers and streaming intermediate steps](modules/07-langchain-agents/04-structured-final-answers-and-streaming-intermedi/README.md) | ✅ ready | chat, tools, stream |
| 07.5 | [Capstone: helpdesk agent with search, ticket and database tools](modules/07-langchain-agents/05-capstone-helpdesk-agent-with-search-ticket-and-d/README.md) | ✅ ready | chat, tools |

## 08 · LangGraph: stateful workflows and routing

Model a workflow as a graph with explicit state.

Optional packages: `langchain`, `langgraph`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 08.1 | [Why graphs: state, nodes and edges](modules/08-langgraph-workflows/01-why-graphs/README.md) | ✅ ready | chat |
| 08.2 | [Conditional edges and routing to specialists](modules/08-langgraph-workflows/02-conditional-edges-and-routing-to-specialists/README.md) | ✅ ready | chat |
| 08.3 | [Streaming, visualising and testing a graph](modules/08-langgraph-workflows/03-streaming-visualising-and-testing-a-graph/README.md) | ✅ ready | chat, stream |
| 08.4 | [Capstone: helpdesk router with specialist nodes](modules/08-langgraph-workflows/04-capstone-helpdesk-router-with-specialist-nodes/README.md) | ✅ ready | chat |

## 09 · LangGraph: cycles, human-in-the-loop, persistence

Loops, approvals and workflows that survive a restart.

Optional packages: `langchain`, `langgraph` · Services: `REDIS_URL`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 09.1 | [Cycles and self-correction loops](modules/09-langgraph-cycles-hitl/01-cycles-and-self-correction-loops/README.md) | ✅ ready | chat |
| 09.2 | [Human-in-the-loop: interrupt, approve, resume](modules/09-langgraph-cycles-hitl/02-human-in-the-loop/README.md) | ✅ ready | chat |
| 09.3 | [Checkpointers: SQLite and Redis persistence](modules/09-langgraph-cycles-hitl/03-checkpointers/README.md) | ✅ ready | chat |
| 09.4 | [Parallel workers and sub-graphs](modules/09-langgraph-cycles-hitl/04-parallel-workers-and-sub-graphs/README.md) | ✅ ready | chat |
| 09.5 | [Capstone: helpdesk change request with an approval gate](modules/09-langgraph-cycles-hitl/05-capstone-helpdesk-change-request-with-an-approva/README.md) | ✅ ready | chat |

## 10 · Tracing, evaluation and testing

See what an LLM application did and measure whether it is good.

Optional packages: `langchain` · Services: `LANGSMITH_API_KEY`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 10.1 | [Tracing runs: spans, latency and token cost](modules/10-tracing-and-evaluation/01-tracing-runs/README.md) | ✅ ready | chat |
| 10.2 | [Evaluation datasets and heuristic evaluators](modules/10-tracing-and-evaluation/02-evaluation-datasets-and-heuristic-evaluators/README.md) | ✅ ready | chat |
| 10.3 | [LLM-as-judge and regression testing of prompts](modules/10-tracing-and-evaluation/03-llm-as-judge-and-regression-testing-of-prompts/README.md) | ✅ ready | chat |
| 10.4 | [Capstone: an evaluation suite for the helpdesk assistant](modules/10-tracing-and-evaluation/04-capstone-an-evaluation-suite-for-the-helpdesk-as/README.md) | ✅ ready | chat |

## 11 · MCP: architecture and custom servers

The Model Context Protocol and how to write a server.

Optional packages: `mcp`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 11.1 | [MCP architecture: hosts, clients, servers, primitives](modules/11-mcp-servers/01-mcp-architecture/README.md) | ✅ ready | - |
| 11.2 | [A minimal server: tools, resources and prompts](modules/11-mcp-servers/02-a-minimal-server/README.md) | ✅ ready | - |
| 11.3 | [Writing an MCP client; discovery and negotiation](modules/11-mcp-servers/03-writing-an-mcp-client-discovery-and-negotiation/README.md) | ✅ ready | chat, tools |
| 11.4 | [Security, validation and debugging with the Inspector](modules/11-mcp-servers/04-security-validation-and-debugging-with-the-inspe/README.md) | ✅ ready | - |
| 11.5 | [Capstone: a helpdesk MCP server for tickets and assets](modules/11-mcp-servers/05-capstone-a-helpdesk-mcp-server-for-tickets-and-a/README.md) | ✅ ready | chat, tools |

## 12 · MCP: ecosystem integrations

Use existing MCP servers and plug them into agent frameworks.

Optional packages: `mcp`, `langchain`, `langgraph`, `crewai`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 12.1 | [Ready-made servers: SQLite and filesystem](modules/12-mcp-ecosystem/01-ready-made-servers/README.md) | ✅ ready | chat, tools |
| 12.2 | [Chaining several servers in one session](modules/12-mcp-ecosystem/02-chaining-several-servers-in-one-session/README.md) | ✅ ready | chat, tools |
| 12.3 | [MCP tools inside LangChain, LangGraph and CrewAI](modules/12-mcp-ecosystem/03-mcp-tools-inside-langchain-langgraph-and-crewai/README.md) | ✅ ready | chat, tools |
| 12.4 | [Capstone: query-to-report pipeline for the helpdesk](modules/12-mcp-ecosystem/04-capstone-query-to-report-pipeline-for-the-helpde/README.md) | ✅ ready | chat, tools |

## 13 · Deep agents: reflection, planning, long-term memory

Agents that critique their work, plan ahead and remember.

Optional packages: `langchain`, `langgraph`, `rag`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 13.1 | [Reflection: generate, critique, revise](modules/13-deep-agents/01-reflection/README.md) | ✅ ready | chat |
| 13.2 | [Planning and replanning](modules/13-deep-agents/02-planning-and-replanning/README.md) | ✅ ready | chat, tools |
| 13.3 | [Long-term memory: episodic, semantic, procedural](modules/13-deep-agents/03-long-term-memory/README.md) | ✅ ready | chat, embeddings |
| 13.4 | [Capstone: a helpdesk agent that learns from resolved tickets](modules/13-deep-agents/04-capstone-a-helpdesk-agent-that-learns-from-resol/README.md) | ✅ ready | chat, tools, embeddings |

## 14 · CrewAI: multi-agent orchestration

Role-based agents working as a team.

Optional packages: `crewai`, `langgraph`, `mcp`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 14.1 | [Agents, tasks, crews and processes](modules/14-crewai/01-agents-tasks-crews-and-processes/README.md) | ✅ ready | chat |
| 14.2 | [Sequential and hierarchical processes; delegation](modules/14-crewai/02-sequential-and-hierarchical-processes-delegation/README.md) | ✅ ready | chat, tools |
| 14.3 | [Tools, MCP and LangGraph alongside a crew](modules/14-crewai/03-tools-mcp-and-langgraph-alongside-a-crew/README.md) | ✅ ready | chat, tools |
| 14.4 | [Capstone: a helpdesk incident-response crew](modules/14-crewai/04-capstone-a-helpdesk-incident-response-crew/README.md) | ✅ ready | chat, tools |

## 15 · Agentic RAG and GraphRAG

Retrieval that decides, checks and corrects itself.

Optional packages: `rag`, `langgraph`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 15.1 | [RAG failure modes and how to diagnose them](modules/15-agentic-rag/01-rag-failure-modes-and-how-to-diagnose-them/README.md) | ✅ ready | chat, embeddings |
| 15.2 | [Agentic, self- and corrective RAG](modules/15-agentic-rag/02-agentic-self-and-corrective-rag/README.md) | ✅ ready | chat, tools, embeddings |
| 15.3 | [Re-ranking, HyDE and query expansion](modules/15-agentic-rag/03-re-ranking-hyde-and-query-expansion/README.md) | ✅ ready | chat, embeddings |
| 15.4 | [GraphRAG: knowledge graphs and multi-hop questions](modules/15-agentic-rag/04-graphrag/README.md) | ✅ ready | chat, embeddings |
| 15.5 | [Capstone: benchmark agentic against plain RAG on helpdesk questions](modules/15-agentic-rag/05-capstone-benchmark-agentic-against-plain-rag-on/README.md) | ✅ ready | chat, embeddings |

## 16 · Containers and deployment

Package an agent and ship it.

Optional packages: `apps` · Services: `DOCKER`, `REDIS_URL`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 16.1 | [Docker fundamentals and a production Dockerfile](modules/16-containers-and-deployment/01-docker-fundamentals-and-a-production-dockerfile/README.md) | ✅ ready | - |
| 16.2 | [Docker Compose: API, vector store, Redis, worker](modules/16-containers-and-deployment/02-docker-compose/README.md) | ✅ ready | chat |
| 16.3 | [Health checks, configuration and secrets](modules/16-containers-and-deployment/03-health-checks-configuration-and-secrets/README.md) | ✅ ready | - |
| 16.4 | [CI/CD and rollout strategies](modules/16-containers-and-deployment/04-ci-cd-and-rollout-strategies/README.md) | ✅ ready | - |
| 16.5 | [Capstone: the helpdesk stack in containers](modules/16-containers-and-deployment/05-capstone-the-helpdesk-stack-in-containers/README.md) | ✅ ready | chat |

## 17 · Monitoring, evaluation and fine-tuning

Operate an agent: traces, metrics, dashboards, and when to fine-tune.

Optional packages: `observability` · Services: `OTEL_EXPORTER_OTLP_ENDPOINT`, `PROMETHEUS_URL`, `GRAFANA_URL`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 17.1 | [Logs, metrics and traces with OpenTelemetry](modules/17-monitoring-and-fine-tuning/01-logs-metrics-and-traces-with-opentelemetry/README.md) | ✅ ready | chat |
| 17.2 | [Prometheus metrics and Grafana dashboards](modules/17-monitoring-and-fine-tuning/02-prometheus-metrics-and-grafana-dashboards/README.md) | ✅ ready | chat |
| 17.3 | [Cost tracking, budgets and service-level objectives](modules/17-monitoring-and-fine-tuning/03-cost-tracking-budgets-and-service-level-objectiv/README.md) | ✅ ready | chat |
| 17.4 | [Fine-tuning: when it is warranted; LoRA and QLoRA](modules/17-monitoring-and-fine-tuning/04-fine-tuning/README.md) | ✅ ready | - |
| 17.5 | [Capstone: a monitored helpdesk assistant](modules/17-monitoring-and-fine-tuning/05-capstone-a-monitored-helpdesk-assistant/README.md) | ✅ ready | chat |

## 18 · Guardrails and safety

Defend an LLM application against misuse and mistakes.

Optional packages: `guardrails`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 18.1 | [The risk landscape and prompt injection](modules/18-guardrails/01-the-risk-landscape-and-prompt-injection/README.md) | ✅ ready | chat |
| 18.2 | [Input and output rails](modules/18-guardrails/02-input-and-output-rails/README.md) | ✅ ready | chat |
| 18.3 | [Validators and detecting personal data](modules/18-guardrails/03-validators-and-detecting-personal-data/README.md) | ✅ ready | chat |
| 18.4 | [Red-teaming a safety stack](modules/18-guardrails/04-red-teaming-a-safety-stack/README.md) | ✅ ready | chat |
| 18.5 | [Capstone: a guarded helpdesk assistant](modules/18-guardrails/05-capstone-a-guarded-helpdesk-assistant/README.md) | ✅ ready | chat |

## 19 · Workflow automation with n8n

Visual workflows that trigger, call and connect agents.

Services: `N8N_URL`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 19.1 | [n8n concepts: workflows, nodes, triggers, credentials](modules/19-workflow-automation-n8n/01-n8n-concepts/README.md) | ✅ ready | - |
| 19.2 | [Webhooks, HTTP requests and model nodes](modules/19-workflow-automation-n8n/02-webhooks-http-requests-and-model-nodes/README.md) | ✅ ready | chat |
| 19.3 | [Error handling, schedules and expressions](modules/19-workflow-automation-n8n/03-error-handling-schedules-and-expressions/README.md) | ✅ ready | - |
| 19.4 | [Capstone: a helpdesk ticket workflow calling an agent](modules/19-workflow-automation-n8n/04-capstone-a-helpdesk-ticket-workflow-calling-an-a/README.md) | ✅ ready | chat |

## 20 · Capstone

Design, build, deploy and present a complete agentic system.

Optional packages: `all`

| Lesson | Title | Status | Model needs |
|---|---|---|---|
| 20.1 | [Choosing a problem and designing the architecture](modules/20-capstone/01-choosing-a-problem-and-designing-the-architectur/README.md) | ✅ ready | - |
| 20.2 | [Building the core: retrieval, graph, tools, guardrails](modules/20-capstone/02-building-the-core/README.md) | ✅ ready | chat, tools, embeddings |
| 20.3 | [Deploying, monitoring and securing](modules/20-capstone/03-deploying-monitoring-and-securing/README.md) | ✅ ready | chat |
| 20.4 | [Documenting and demonstrating](modules/20-capstone/04-documenting-and-demonstrating/README.md) | ✅ ready | - |
