# Capability: curriculum map

`curriculum.toml` is the single source of truth. `CURRICULUM.md` is generated from it and
a test fails when they drift.

Modules (client-neutral; by-hand modules precede frameworks):

| # | Module | Extra | Services |
|---|---|---|---|
| 00 | Setup and Python for AI work | — | — |
| 01 | Foundations: talking to an LLM | — | — |
| 02 | Tools and agents by hand | — | — |
| 03 | Embeddings and semantic search | rag | — |
| 04 | RAG by hand | rag | — |
| 05 | Serving AI apps: FastAPI, Streamlit, Gradio | apps | — |
| 06 | LangChain core: chains, memory, RAG | langchain | — |
| 07 | LangChain agents and tool use | langchain | — |
| 08 | LangGraph: stateful workflows and routing | langgraph | — |
| 09 | LangGraph: cycles, human-in-the-loop, persistence | langgraph | — |
| 10 | Tracing, evaluation and testing | langchain | LangSmith |
| 11 | MCP: architecture and custom servers | mcp | — |
| 12 | MCP: ecosystem integrations | mcp | — |
| 13 | Deep agents: reflection, planning, long-term memory | langgraph | — |
| 14 | CrewAI: multi-agent orchestration | crewai | — |
| 15 | Agentic RAG and GraphRAG | rag, langgraph | — |
| 16 | Containers and deployment | apps | Docker, Redis |
| 17 | Monitoring, evaluation and fine-tuning | observability | Jaeger, Prometheus, Grafana |
| 18 | Guardrails and safety | guardrails | — |
| 19 | Workflow automation with n8n | — | n8n |
| 20 | Capstone | all | all |

Every module folder exists from Phase 1 with a README outline; lessons not yet written
are `planned` and say so.
