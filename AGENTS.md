# AgentOS — Docker template

This file is the source of truth for any agent (Claude Code, Codex, others) working on this repository. `CLAUDE.md` is a symbolic link to this file - edit one, both update.

## Project overview

**AgentOS: FastAPI for agents — an AI backend for every frontend.** AgentOS is an agent server built on [Agno](https://docs.agno.com) that turns your agents into a production API that connects to any client: **REST API** for programmatic use, **chat interfaces** for humans (Slack is connected; WhatsApp/Telegram/Discord mirror the same standard), and **MCP** in `/mcp` for AI applications (claude.ai, ChatGPT, Cursor, Claude Code) — that work *across* the platform, not just on it. The repository itself is designed for coding agents to build and extend. It comes with eight coding agent skills that cover platform configuration, the full agent development lifecycle, and production deployment, plus two platform agents - Agent Builder (creates agents, teams, and workflows) and Platform Manager (understands, monitors, and explains the platform) - and Chief, the one your team scores on ("Boss, what's going on with the radar?" - "Boss, help plan this"): it keeps the common thread - people, projects, decisions, notes alive - learn how each user works and responds with game state from Slack, claude.ai, ChatGPT, or any MCP client. Postgres (pgvector) handles persistence for sessions, memory and knowledge. Runs locally via Docker; This model also runs production with Docker — on any host you control, with no cloud providers in between — and is the self-hosted sibling of the `agents-*` deployment family — see [Portable Core vs. deployment layer](#portable-core-vs-deploy-layer).

## Architecture

```
AgentOS (app/main.py)
├── Chief (agents/chief.py) — team mascot: LearningMachine + notes + web tools
├── Platform Manager (agents/platform_manager.py) — WorkspaceContextProvider + AgentOSTools read-only operations toolkit + user-shared profile/memory
├── Agent Builder (agents/agent_builder.py) — Agno docs MCP + StudioTools + profile/shared memory per user
├── AD Assessment Advisor (agents/ad_assessment_advisor.py) — prepares scenario payloads and executor-facing script locations for AD assessments
├── AD Assessment Coordinator (agents/ad_assessment_coordinator.py) — first contact for assessment work: defines the scope of the activity, asks the minimum questions, triggers the workflow and prepares the transfer of Jira/Scrum changes
├── DeployCheck (workflows/deployment_check.py) — deterministic readiness workflow
└── RunEvals (workflows/run_evals.py) — optional evaluation suite workflow
```

Shared:

- PostgreSQL + pgvector for sessions, memory, knowledge.
- All three reference agents connect the LearningMachine per-user profile and memory stores in the shared database – one human, one self in each agent. Entities and notes remain with the Chief.
- `app.settings.default_model()` returns `OpenAIResponses(id="gpt-5.6-sol")` — put the model in one place.
- `app.registry.registry` exposes the secure Studio registry that Agent Builder can use: Agno MCP documents, web search, reasoning tools, utility functions, the default template, the shared database, and the reference agents (boss, platform manager). At runtime, agno also includes the wiring of each agent registered in the active registry (`studio`, Chief's `filesystem` notes, the `agents` operations toolkit) - the Agent Builder instructions treat them as off-limits for builds unless the user requests the capability by name.
- Scheduler enabled by default (`scheduler=True`); `app/schedules.py` records lifetime schedules. Deployment Check runs daily **on** by default — set `ENABLE_DEPLOY_CHECK=False` to disable it. Scheduling run assessments is always registered, but is provided **off** (it uses template calls) — enable it in the AgentOS UI when you want scheduled assessment runs; the toggle survives reboots.
- Slack interface lights up automatically when `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` are set.
- MCP server enabled by default (`mcp_server=True`) in `/mcp` — see [MCP interface](#mcp-interface).
- MCP OAuth lights up when `MCP_CONNECT_SECRET` is set (integrated authorization server) — how claude.ai and ChatGPT (web) connect; see [MCP interface](#mcp-interface).
- JWT authentication enabled whenever `RUNTIME_ENV` is anything but `dev` (so production deployments, which default to `prd`, are blocked by default).

## Main files

| Archive | Purpose |
| ------ | --------- |
| [`app/main.py`](app/main.py) | AgentOS entry point — lifetime hook, conditional Slack, conditional MCP OAuth, JWT gate. |
| [`app/settings.py`](app/settings.py) | `default_model()` factory. |
| [`app/registry.py`](app/registry.py) | Safe Studio registry used by Agent Builder — MCP documents, web tools, utility functions, reference agents. |
| [`app/config.yaml`](app/config.yaml) | UI manifest per component (typed by `id`): description + quick prompts. |
| [`agents/chief.py`](agents/chief.py) | The team mascot — LearningMachine (profile, memory, entities in agent mode) + FileSystem notes + web tools (Parallel SDK or keyless MCP); the default Slack agent. |
| [`agents/platform_manager.py`](agents/platform_manager.py) | Core Agent - codebase context provider + agno's `AgentOSTools` read-only operations toolkit (traces tool usage, execution and activity metrics, evaluation history, schedules and their execution history, components created at runtime, pending approvals) + deployment verification reports with an on-demand diagnostic run. Connects user-shared profile/memory store. |
| [`agents/agent_builder.py`](agents/agent_builder.py) | Reference Agent — Create, edit, and publish agents, teams, and workflows through StudioTools immediately; only deletes maintain a HITL commit port. Connects user-shared profile/memory store. |
| [`agents/ad_assessment_advisor.py`](agents/ad_assessment_advisor.py) | Assessment Preparation Specialist – Collects scope for AD/DNS/PKI executions and generates payloads/scripts for separate PowerShell executor. |
| [`agents/ad_assessment_coordinator.py`](agents/ad_assessment_coordinator.py) | Assessment gateway – interviews the user, stores scope preferences, starts running ad assessment automatically when possible, and prepares Jira/Scrum change transfer content. |
| [`workflows/deployment_check.py`](workflows/deployment_check.py) | Reference Workflow — a deterministic `Step` that checks database, authentication, scheduler URL, MCP reachability, Slack configuration, schedule state, and component imports; imported into `app/main.py` and passed into `AgentOS(workflows=[...])`. |
| [`workflows/ad_assessment_run.py`](workflows/ad_assessment_run.py) | Secure evaluation bridge to production — generates scenario artifacts and PowerShell scripts, checks llama runtime, and optionally calls a separate runner API. |
| [`workflows/run_evals.py`](workflows/run_evals.py) | Optional workflow – Runs a marked subset of the assessment set and returns a compact report. Your daily schedule is disabled – enable it in the AgentOS interface. |
| [`app/schedules.py`](app/schedules.py) | `register_schedules()` — cron register, called since lifetime (idempotent, fail-soft). |
| [`db/session.py`](db/session.py) | `get_postgres_db()`, `create_knowledge()`. |
| [`db/url.py`](db/url.py) | Constructs the database URL from env. |
| [`evals/cases.py`](evals/cases.py) | Assessment cases (each is a `Case` with optional judge + reliability checks). |
| [`evals/__main__.py`](evals/__main__.py) | `python -m evals` — fine entry point into the agno evaluation suite runner (`agno.eval.cli`). |
| [`.agentes/skills/`](.agentes/skills/) | Development-time encoding agent workflows** (`setup-platform`, `create-agent`, `extend-agent`, `improve-agent`, `create-evals`, `eval-and-improve`, `review-and-improve`, `deploy-platform`) — slash commands that encoding agents execute *in this repository*. `.claude/skills` is a confirmed symbolic link to it - see [Working with coding agents](#working-with-coding-agents). |
| [`README.md`](README.md) | Public entry point — Your Get Started prompt delivers an encoding agent to the `setup-platform` skill (clone to the first agent). |
| [`compose.yaml`](compose.yaml) | Docker Compose for local development. |
| [`compose.prod.yaml`](compose.prod.yaml) | Production replacement — `RUNTIME_ENV=prd` (JWT enabled), no bind mount or hot reload, `AGENTOS_URL` and `MCP_CONNECT_SECRET` from `.env`. |

## Development configuration

### Local with Docker

```bash
cp example.env .env
# Edit .env and set OPENAI_API_KEY

docker compose -d --build
```

`compose.yaml` sets `RUNTIME_ENV=dev`, `AGNO_DEBUG=True` and `WAIT_FOR_DB=True` so that JWT is disabled and the API is blocked in the database before serving. It runs uvicorn with a `--reload` scope (looking at `agents/`, `app/`, `db/`, `evals/`, `workflows/`), then the code edits the hot-reload in a second or two. Restart `agents-api` after dependency or environment changes, or whenever you want a guaranteed clean state.

### Format and validate

The format/validation/evaluation scripts run on the host, so they need a venv. Configure one once:

```bash
./scripts/venv_setup.sh
source .venv/bin/activate
```

So:

```bash
./scripts/format.sh # ruff format + import sort
./scripts/validate.sh # ruff check + mypy (runs both, resumes)
```

CI installs the same pinned `requirements.txt` and runs the same `scripts/validate.sh` - location and CI never fluctuate.

## Conventions

### Agent pattern

Each agent file has the same format:

```python
"""
<Title> Agent
=============
"""

from the import agent agno.agent

from app.settings import default_model
from importing the get_postgres_db database

INSTRUCTIONS = """\
<a short paragraph: what the agent does, what tools it uses, what
rules to follow when responding>
"""

my_agent = Agent(
    id="my-agent",
    name="My Agent",
    model=default_model(),
    database=get_postgres_db(),
    tools=[...],
    instructions = INSTRUCTIONS,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
)
```

Three patterns to copy:

- **Learning agent** — see [`agents/chief.py`](agents/chief.py). Direct tools (the notes toolkit — the agent sees each tool individually) plus `learning=`: LearningMachine attaches tools, guidance, and recall from your stores automatically. Best when the agent must accumulate durable state between sessions. For a simple direct tools agent, use the same form without `learning=`.
- **Context Provider** — see [`agents/platform_manager.py`](agents/platform_manager.py). The agent sees a `query_<thing>` tool which is passed to a subagent. Best for single-source agents and by bringing together many tools into one, it keeps the model focused. Platform Manager also shows the combination of a provider with direct read-only tools – two lenses on one domain.
- **Builder Studio** — see [`agents/agent_builder.py`](agents/agent_builder.py). The agent sees StudioTools, a secure `Registry`, Agno documents MCP and delete-only commit ports: creation/editing/publishing executed immediately (each mutation arrives in the database as a versioned component - inspectable and reversible), while deletions pause for human approval. Best when the user must create or refine UI components from AgentOS, Slack, or an MCP front end.

### Database

```python
# Simple agent – sessions, memory, live agent memory here
from importing the get_postgres_db database
agent_db=get_postgres_db()

# Knowledge base agent (RAG) — pass by `knowledge=`
from importing the create_knowledge database
my_kb = create_knowledge("My knowledge", "my_vectors")
```

Knowledge bases use PgVector with `SearchType.hybrid` and `text-embedding-3-small`. The document content goes into `<table_name>_contents`.

## Adding a new agent

Two options:

1. **Pass to Claude Code** — run the `/create-agent` skill (or just ask it to "create a new agent") in a Claude Code session pointed to this repository. Claude asks the user what the agent should do, generates the file, logs it, performs smoke tests. See [Working with coding agents](#working-with-coding-agents).
2. **Do this manually** — create `agents/<slug>.py`, register in `app/main.py`, add your manifest entry (description + quick prompts) in `app/config.yaml`. Scoped uvicorn reload picks up changes automatically; restart `agents-api` if you changed dependencies or env.

## Iterating on an agent

Two recursive loops over the same agent. Use them together.

- **`/extend-agent`** ([`.agents/skills/extend-agent`](.agents/skills/extend-agent/SKILL.md)) — **you drive.** Add a tool, add a feature, refine the prompt, fix a known bug. Claude is the Agno-aware peer programmer (uses MCP `agno-docs` for any toolkit research). Loop: change → smoke test → "anything else?".
- **`/improve-agent`** ([`.agents/skills/improve-agent`](.agents/skills/improve-agent/SKILL.md)) — **Claude directs.** Derives probes from agent `INSTRUCTIONS` and actual usage in the database (when the platform has any), judges, edits, reruns — reflective self-improvement. No user input is required. Loop: mine → probe → judge → edit → probe again.

Use `/extend-agent` to *change* the agent; use `/improve-agent` to *strengthen* against your stated intent. Most fixes for any loop are a sentence in `INSTRUCTIONS`.

## Reviews

The eval suite resides in [`evals/`](evals/) and runs in the agno eval suite executor (`agno.eval`): the template declares `Case`s, agno executes them. Each case involves agno's [`AgentAsJudgeEval`](https://docs.agno.com/evals/agent-as-judge) (LLM judge against a rubric, binary pass/fail) and/or [`ReliabilityEval`](https://docs.agno.com/evals/reliability) (tool call assertion). Any case whose agent can access Studio's build/edit/publish tools (anything that tests `agent-builder`) must set the builder hooks in `evals/cases.py` (`setup=snapshot_builder_state, teardown=cleanup_new_builder_state`) — the setup records the Studio component IDs plus the learning/grade state before the case, and teardown permanently deletes any new lines afterwards, even in the time limit. Similarly, any other case that probes an agent with learning stores (`chief`, `platform-manager`) must define the learning hooks (`setup=snapshot_learning_state, teardown=cleanup_new_learning_state`) — the capture is not blocked, so entities, memories, and notes actually make it to the shared stores, and teardown removes the rows that appeared while the case was running. Two consequences worth knowing before running the package in the stores people are using it: a row that already existed is never deleted, but an edit *within* one is also never undone; and a line that someone else writes during the case window looks new in the diff and is swept. Run the suite when you are the only writer and provide fixture names that no real team would have on file. As a safeguard, a disassembly that would scan more than 25 rows of learning refuses and errors - that many new rows means the snapshot itself is suspect (a transient database error during setup is read as empty storage) and a `cleanup:` error trumps a silent mass delete. Cases carry tags:

- `smoke` — quick checks that prove that the model's autonomous surfaces still work.
- `release` — broader pre-release confidence checks.
- `live` — current web/source checks that are useful, but should not be deterministic release ports.

Run with `python -m evals --tag smoke`, `python -m evals --tag release` or `python -m evals --name <case>`. Add `--json-output out.json` when a workflow or encoding agent needs machine-readable results. Results are logged to Postgres via `db=eval_db` so the history is visible on os.agno.com.

Two abilities work on this set of opposing sides. To create coverage - especially for agents you build that start with none - run [`/create-evals`](.agents/skills/create-evals/SKILL.md): it maps what an agent promises, pulls real Postgres sessions for scenarios, and writes audited cases to a tagged user case section that it adds to `evals/cases.py` on first use. To diagnose failures and fix the scope, run [`/eval-and-improve`](.agents/skills/eval-and-improve/SKILL.md).

## Reviewing the repository

Run the `/review-and-improve` skill ([`.agents/skills/review-and-improve`](.agents/skills/review-and-improve/SKILL.md)). A recurring scan that compares documents to code: every agent registered, every environment variable documented, every path in a document still exists, every script behaves as advertised. Automatically corrects mechanical deviation; signals something bigger. Best done before a public release or after a refactoring.

## Working with encoding agents

Development-time **encoding agent workflows** reside in [`.agents/skills/`](.agents/skills/) — the vendor-neutral location for encoding agent assets, reflecting how `CLAUDE.md` symlinks to `AGENTS.md`. `.claude/skills` is a committed symlink to it, so Claude Code selects the skills on each clone without any configuration steps; other whips (Codex, Cursor,…) can symbolically link the same folder. (Windows needs developer mode or `core.symlinks=true` for the symbolic link to materialize.) The Claude-specific setting like `.claude/settings.json` remains an actual file in `.claude/`.

These workflows cover platform configuration, agent development lifecycle, and production deployment in this model:

- **`/setup-platform`** — Bring a new clone to a running platform with a first active agent: Docker check, `.env`, initialization, MCP proof, AgentOS UI connection, then a `create-agent` transfer. The README intro prompt and os.agno.com onboarding prompt walk you through.
- **`/create-agent`** — create a new agent: guided discovery or from a concrete idea → generate `agents/<slug>.py`, register it, test it live.
- **`/extend-agent`** — you drive. Add a tool/source, refine `INSTRUCTIONS`, fix a known bug. Uses MCP `agno-docs` for grounded toolkit research.
- **`/improve-agent`** — Claude directs. Derives probes from agent `INSTRUCTIONS` and actual usage in database, judge, edit, rerun. No user input is required.
- **`/create-evals`** — creates evaluation coverage for an agent: maps its promises, extracts real Postgres sessions for scenarios, proposes capabilities, writes and audits `Case` entries. How a user's own agents join the package.
- **`/eval-and-improve`** — run the evaluation suite, diagnose failures, fix the scope until green.
- **`/review-and-improve`** — repository-wide branch scanning (docs vs code vs configuration).
- **`/deploy-platform`** — take the proven local platform to production on your own host: no deployment scripts here, the skill guides instead of drives — it walks through the deployment section of the README with you (public URL, production environment, the main JWT step) and then checks the active platform at its public URL.

Invoke a skill by name (`/extend-agent`) or just describe the task — Claude Code matches the skill's `description`.

## Environment variables

| Variable | Required | Standard | Description |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | yes | — | OpenAI key for models + embeddings. |
| `RUNTIME_ENV` | no | `prd` | `dev` disables JWT. `compose.yaml` sets it to `dev` for local; `compose.prod.yaml` defines `prd` - never configure `dev` manually on a production host, or the platform will serve without authentication. |
| `JWT_VERIFICATION_KEY` | prd | — | Public key of os.agno.com. Required when `RUNTIME_ENV=prd` and `authorization=True` unless `JWT_JWKS_FILE` is set. |
| `JWT_JWKS_FILE` | prd | — | Path to a JWKS file; alternative to `JWT_VERIFICATION_KEY` for production JWT verification. |
| `AGENTS_URL` | no | `http://127.0.0.1:8000` | Scheduler base URL – cron triggers reach AgentOS through this. In production, set it in `.env` to your public URL (domain or tunnel); `compose.prod.yaml` passes through it. Left at default localhost in the prod, the daily deployment check flags the platform as poorly configured and hosted chat applications with no connector URL to point to. Additionally, public source OAuth metadata is derived from when `MCP_CONNECT_SECRET` is set. |
| `MCP_CONNECT_SECRET` | no | — | If set (≥16 characters, e.g. `openssl rand -base64 32`), `/mcp` becomes your own OAuth 2.1 authorization server (integrated layer) so that claude.ai and ChatGPT (web) can connect; the connection requests this secret on a consent page. Requires `AGENTOS_URL`. PAT and JWT holders continue to work side by side. Set it manually in `.env` - dev and prod share this file here, so it also locks the local `/mcp`. |
| `AGENTOS_MCP_SIGNING_KEY` | no | — | Optional high-entropy signature key material (≥32 characters) for OAuth tokens. Undefined, a strong key is generated and persisted in the database. Rotation invalidates outstanding tokens. |
| `ENABLE_DEPLOY_CHECK` | no | `Truth` | The reference deployment check cron (`app/schedules.py`) runs daily by default. Set `False` to disable; the workflow remains executable on demand anyway. |
| `EVALS_TAG` | no | `smoke` | Evaluation label run by the run-evals workflow. |
| `EVALS_CASE_TIMEOUT_SECONDS` | no | `90` | Default timeout per case for execution assessment runs; only applies to cases that don't define their own `timeout_seconds`. |
| `EVALS_SUITE_TIMEOUT_SECONDS` | no | `900` | Entire pool timeout for execution evaluation runs; the timeouts per case are the granular limit. The default limits the worst case of the `smoke` tag (incl. constructor case disassembly). |
| `PARALLEL_API_KEY` | no | — | Authenticates Chief and Studio registry web search tools (parallel SDK when defined; keyless MCP fallback with a lower rate ceiling). |
| `SLACK_BOT_TOKEN` | no | — | Bot token. Set with subscription secret to activate the Slack interface. |
| `SLACK_SIGNING_SECRET` | no | — | Secret signature. Both it and the bot token must be configured for the interface to load. |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_DATABASE` | no | games make up | Postgres connection. |
| `DB_DRIVER` | no | `postgresql+psycopg` | SQLAlchemy Driver. |
| `AGNO_DEBUG` | no | `False` | If `True`, agno outputs detailed debug logs. Compose sets this for dev. |
| `WAIT_FOR_DB` | no | `False` | If `True`, the entry point is locked in the database before starting. Compose defines this. |

## Ports

- API: `8000`
- Database: `5432`

## Scheduler

`scheduler=True` is enabled in [`app/main.py`](app/main.py). A schedule is a cron expression + an HTTP endpoint (a workflow or agent execution); the researcher triggers the necessary work in the background. The registry resides in `register_schedules()` of [`app/schedules.py`](app/schedules.py), called since lifetime - idempotent (`if_exists="update"`, safe on every boot) and fail-soft (bad programming logs a warning instead of crashing the boot).

**Reference examples.** [`workflows/deployment_check.py`](workflows/deployment_check.py) is a one-step **deterministic** workflow — no LLM, no token cost — that returns a deployment readiness report. It checks database tables and connectivity, JWT configuration, scheduler URL, MCP endpoint reachability, Slack environment consistency, scheduling state, and reference component imports. [`app/schedules.py`](app/schedules.py) records a daily cron that hits your endpoint (`POST /workflows/deployment-check/runs`). Because it is deterministic and free, cron runs **on** by default (daily at 1pm UTC); disable it with `ENABLE_DEPLOY_CHECK=False`.

[`workflows/run_evals.py`](workflows/run_evals.py) runs a marked subset of the evaluation set and returns a compact report. Your 14:00 UTC daily schedule is always logged, but is sent **disabled** because it uses template calls — enable it in the AgentOS UI (or `POST /schedules/{id}/enable`) to run smoked cases daily. The enabled toggle is yours after that: registration at boot time updates the schedule definition, but never overwrites it. Enable it with the Evals section's only writer rule in mind: smoke includes learning store cases whose teardown sweeps anything written to the shared stores during the case window, so a scheduled run while the team is talking to the Chief could delete its archives - choose a time when no one is there, or leave the schedule disabled on a busy platform and run the package deliberately.

To add your own: define a `Workflow` in `workflows/`, import it into [`app/main.py`](app/main.py) and add it to `AgentOS(workflows=[...])`, and register a schedule for it in `register_schedules()`. Other common uses: **maintenance** (cleaning up old sessions, vacuum tables), **periodic reevaluation** (running `python -m evals` weekly to catch regressions).

See [agno scheduler docs](https://docs.agno.com/agent-os/scheduler) for the cron API.

## Boss

Chief ([`agents/chief.py`](agents/chief.py)) is the team's mascot — the one everyone tells things to. "Boss, let's use PlanetScale instead of RDS." "Boss, Zak is running the launch." From Slack, the AgentOS UI, or any MCP client: it takes what's said, archives it, and connects the dots when someone asks what's going on. Heat is the surface; underneath it runs on LearningMachine and agno's FileSystem. Three surfaces divide the work: **notes** contain content (decisions with their reasoning, document execution - anything larger than a line), **entities** index the world (people, projects, systems: current one-line values, links, and a `note:` pointer to where the details are), and **profile/memory** hold the self (who each user is, how they like to work). The one-claim-one-home rule in your `INSTRUCTIONS` prevents these surfaces from duplicating each other. Chief also loads **web tools** (parallel SDK when `PARALLEL_API_KEY` is set, keyless MCP otherwise): questions from the outside world are researched and substantiated, and processed pages are archived as **links plus a distilled conclusion - payloads never pasted**, because the notes stay in the database (1MB/file, 20MB/namespace limits) and the web can always be fetched again.

**The world is shared, the self is private.** Notes (`FileSystem` namespace `brain` — files come to Postgres under the `fs` schema) and entities (`global` namespace) are shared by everyone on the platform; user profile and user memory are per user (agent mode, so your tools only exist when a run loads a user ID). Self also spans agents: Agent Builder and Platform Manager connect the same profile/memory store per user, so what Chief learns about a user follows them to each reference agent. Corrections replace rather than accumulate – declaring a new fact removes the contradict (a model call judged in the write path) and the facts are rendered with current dates.

**Identity decides what remains private.** The identity of an execution always wins: Slack runs as sender, production runs as JWT `sub`, PATs as `sa:<name>`. `Agent(user_id="anonymous-user")` is just the fallback for anonymous local runs (dev `/mcp`, evals) — without it they would silently lose the profile/memory tools. Uma advertência a saber: o MCP OAuth integrado identifica o *registro do conector*, não a pessoa — claude.ai e ChatGPT se conectam como diferentes `__oauth__:<client_id>` principais, de modo que o mesmo humano obtém armazenamentos privados separados por aplicativo (notas e entidades compartilhadas não são afetadas). Uma implantação JWT é o que dá a um ser humano um chefe em todos os canais.

Duas notas de implementação: o sinalizador herdado `enable_agentic_memory` permanece **desativado** em todos os três agentes de referência — junto com os armazenamentos de aprendizagem, ele registraria a ferramenta `update_user_memory` do legado MemoryManager, ocultando a ferramenta do armazenamento de aprendizagem de mesmo nome. E os casos de avaliação que investigam um agente de armazenamento de aprendizagem devem definir os ganchos de aprendizagem (consulte [Evals](#evals)) e nomear seus fixtures como coisas que nenhuma equipe real teria em arquivo. Os ganchos diferem na identidade da linha, portanto, eles removem as linhas de um caso *criado*, mas não podem desfazer uma edição *dentro* de uma linha que já existia — um fato substituído, um relacionamento substituído, uma linha de nota reescrita. Nomes distintos são o que mantém um caso fora desse caminho.

## Gerenciador de plataforma

A superfície de operações da plataforma é o agente do Platform Manager ([`agents/platform_manager.py`](agents/platform_manager.py)) — somente leitura por design. Ele combina o provedor de contexto de base de código (como a plataforma é conectada) com o kit de ferramentas `AgentOSTools` do agno sobre Postgres (métricas de uso, atividade de execução e ferramenta de rastreamentos, histórico de avaliação, cronogramas e seu histórico de execução, componentes criados em tempo de execução, aprovações pendentes) além das próprias ferramentas de verificação de implantação deste modelo (relatórios - e execução da verificação sob demanda quando nenhum relatório existe ou o mais recente está obsoleto), diagnostica problemas em ambas as lentes e não corrige: as alterações de código vão para a codificação agentes por meio das habilidades em [`.agents/skills/`](.agents/skills/), as alterações dos componentes vão para o Agent Builder.

Duas dessas ferramentas respondem às perguntas que um operador faz primeiro. `get_platform_metrics` é o livro-razão – execuções, sessões, usuários distintos, gastos com tokens e combinação de modelos por dia. Ele é atualizado antes de ler, porque o agno calcula esses agregados apenas sob demanda (`POST /metrics/refresh`, um botão na UI): uma plataforma implantada em que ninguém clica não reporta absolutamente nada, indefinidamente. A atualização é autolimitada — as datas já concluídas são ignoradas — e grava apenas rollups derivados de sessões já existentes. `get_run_activity` é o cronômetro, agregando os rastreamentos `tracing=True` já registrados em contagens de execução por agente, por equipe e por fluxo de trabalho, latência (média, p95, mais lento) e falhas. Os rastreamentos sem ID de componente são de nível de endpoint (uma chamada `/mcp` envolvendo uma execução de agente) e são relatados em uma chave `endpoint_level` separada para que nunca contem duas vezes a execução que encapsulam; quando uma lista é limitada, as notas da carga dizem isso, em vez de passar uma amostra como a imagem completa. `get_tool_activity` restringe o cronômetro a intervalos: quais ferramentas são mais chamadas, quais são executadas mais lentamente e como as chamadas de modelo estão se comportando - apenas nomes, durações e status, nunca conteúdo de conversa. Desde a versão 2.8.5, eles chegam com o kit de ferramentas `AgentOSTools` do agno — uma linha na lista de ferramentas — e o modelo adiciona apenas o par de verificação de implantação no topo.

Mantenha-o somente leitura. O ponto é o mínimo de privilégios: uma superfície de operações que apenas lê não pode falhar, não precisa de portas de confirmação e permanece segura para ser exposta em qualquer front-end. A visibilidade é a única ressalva: `AgentOSTools` lê Postgres diretamente, então os escopos de endpoint REST nunca se aplicam a ele — qualquer pessoa que possa conversar com o agente vê agregados de toda a plataforma, e `list_pending_approvals` carrega identificadores de usuário, sessão e ferramenta. Essa também é a orientação do kit de ferramentas: expor o agente aos operadores e cortar superfícies com os sinalizadores de ativação do kit de ferramentas para qualquer coisa mais ampla. **Os diagnósticos são o único gatilho sancionado**: o Platform Manager pode executar observações que são determinísticas, gratuitas, idempotentes e não mutantes — qualifica `run_deployment_check` (ele aponta novamente as mesmas verificações que o cron diário executa, e a execução persiste para que o histórico do relatório permaneça coerente); run-evals não (gasto do modelo), e qualquer coisa que grave o estado da plataforma nunca o faz. A atualização de métricas dentro de `get_platform_metrics` fica logo dentro dessa linha e vale a pena afirmar com precisão: é determinística, gratuita e idempotente, e as únicas linhas que ela grava são agregações recomputadas a partir de sessões que a plataforma já possui — ela deriva, não sofre mutação. O perfil por usuário e as gravações de memória do LearningMachine ficam totalmente fora dos limites do estado da plataforma - eles registram quem é o usuário, nunca o que a plataforma faz. Nada que altere o estado de origem se qualifica por esses motivos. A ativação/desativação do agendamento e o gatilho ficam de fora pelo mesmo motivo: agno os expõe (`POST /schedules/{id}/enable`, `/disable`, `/trigger`), então o limite aqui é uma escolha deliberada, não uma capacidade ausente. As aprovações seguem a mesma divisão — `list_pending_approvals` lê a fila; decidir que alguém fica com o humano. As ferramentas de leitura futura (inspeção `git diff`) pertencem aqui; as mutações pertencem aos agentes de codificação por meio do git ou atrás do portão de exclusão do Agent Builder - que um cliente MCP agora pode aprovar no chat via `continue_run`.

## Interface MCP

`mcp_server=True` em [`app/main.py`](app/main.py) monta um servidor MCP (HTTP streamable) em `/mcp`, na mesma porta que a API REST. This is the platform's second interface: chat apps (claude.ai and ChatGPT connectors) and coding agents (Claude Code, Cursor) drive the agents, teams, and workflows through it. The README's setup prompt hands a fresh machine to the [`setup-platform`](.agents/skills/setup-platform/SKILL.md) skill, which takes it from clone to first agent — proving `/mcp` end to end along the way (`scripts/mcp_check.sh`).

- **Tools are generic, not per-agent — eight of them.** `get_agentos_config` (how clients discover valid ids), `run_agent(agent_id, message, session_id)`, `run_team`, `run_workflow`, `continue_run`, `cancel_run`, `get_sessions`, and `get_session_runs`. Sessions are read-only over MCP and there is no memory CRUD. `run_agent` returns a trimmed ToolResult: `content[0].text` is the plain answer, and `structuredContent` carries `{run_id, session_id, status}`. The server needs the `fastmcp` package, which ships with the pinned `agno` dependency.
- **Auth mirrors the REST API, with first-class service accounts.** Dev (`RUNTIME_ENV=dev`) is open (unless MCP OAuth is on — next bullet). In prd the same middleware protects `/mcp`; clients send `Authorization: Bearer <token>`. Two token types work side by side: JWTs minted at os.agno.com, and opaque service-account PATs (`agno_pat_…`) minted via `POST /service-accounts` (the route auto-enables once a db is set). A PAT's default scopes — `agents:run`, `teams:run`, `workflows:run`, `sessions:read`, `config:read` — cover all eight tools, and it attributes as `sa:<name>`. The verified token subject overrides any caller-supplied `user_id`, so identity cannot be spoofed. `uvx agno connect` mints a PAT and registers `/mcp` in Claude Code / Claude Desktop / Codex / Cursor.
- **OAuth for the web chat apps — set `MCP_CONNECT_SECRET` and `/mcp` becomes its own OAuth 2.1 authorization server.** claude.ai and ChatGPT (web) connectors authenticate over OAuth only, so this is what lets them connect to a secured platform: paste `https://<public-url>/mcp` as a custom connector (the form's optional client ID/secret fields stay empty — DCR registers the app), then approve the consent page with the connect secret. The built-in server (`AgentOSBuiltinAuth(url=agentos_url, secret=MCP_CONNECT_SECRET)` in [`app/main.py`](app/main.py), mirroring the Slack conditional) stores clients, single-use codes, and rotating refresh tokens hashed in Postgres; DCR is public-client + PKCE only; tokenless calls get the `401` + `WWW-Authenticate` challenge connectors use for discovery, and `/info`'s `mcp.oauth` block carries the OAuth discovery details (`auth_mode` keeps describing the REST plane). Existing PAT/JWT bearers keep working on the same endpoint (`MultiAuth`), so enabling OAuth never breaks `agno connect` clients. Gates `/mcp` in dev too — the OAuth flow needs a stable public origin (`AGENTOS_URL`) — and dev and prod share `.env` in this template, so setting the secret gates the local `/mcp` as well.
- **HITL pauses resume over MCP via `continue_run`.** A paused `run_agent` returns immediately with `status=PAUSED` and unresolved `requirements` dicts in `structuredContent`; the client sets the resolution field (e.g. `confirmation: true`) and passes them back through `continue_run(run_id, agent_id, session_id, requirements)`. So a confirmation gate is no longer a dead end from chat frontends — this is what lets Agent Builder keep the delete gate usable over MCP. One agno 2.8.5 caveat: a bare `confirmation: true` is dropped on the continue path and audited as a rejection — until the upstream fix lands, also set `tool_execution.confirmed: true` inside each requirement you pass back.

Local smoke check: `./scripts/mcp_check.sh` — handshake, tool count, and one quick tool-free `run_agent` call through `/mcp` (finishes in seconds; pass your own question as an argument), executed inside the container. When `/mcp` is auth-gated (OAuth on, or prd JWT), it retries with a short-lived probe service account that it mints and deletes itself. To register the endpoint, run `uvx agno connect` (auto-detects Claude Code / Claude Desktop / Codex / Cursor and verifies with a real handshake); the manual fallback for Claude Code is `claude mcp add --transport http agentos http://localhost:8000/mcp`.

## Portable core vs. deploy layer

This repo is the self-hosted Docker sibling of the `agentos-*` deployment family ([agentos-railway](https://github.com/agno-agi/agentos-railway) is the reference). Everything that defines the platform is **portable core — identical across the family**: `agents/`, `app/`, `db/`, `workflows/`, `evals/`, the MCP server wiring, the interfaces, and the coding-agent skills in `.agents/skills/`. `Dockerfile`, `compose.yaml`, and `scripts/entrypoint.sh` are shared local-dev/runtime infra, also not deployment-specific.

The **Docker-specific deploy layer** — what a sibling template swaps out — is exactly:

- [`compose.prod.yaml`](compose.prod.yaml)
- the "Running in production on your own host" prose here and the README's "Run in production" section

This is the family's smallest deploy layer — there is no provider CLI, no provisioning script, and nothing to tear down. Siblings that target a cloud swap in a provider config plus `scripts/<provider>/{up,env-sync,redeploy}.sh`.

When editing, keep that boundary crisp: platform behavior belongs in the core, production-hosting mechanics belong in the deploy layer, and nothing in the core should import from or depend on it.

## Running in production on your own host

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

The [`compose.prod.yaml`](compose.prod.yaml) override switches `RUNTIME_ENV` to `prd` (JWT auth on), drops the dev bind mount and hot reload so the container runs the code baked into the image, reads `AGENTOS_URL` (and `MCP_CONNECT_SECRET`, if set) from `.env`, and rebinds Postgres to loopback so the database is not internet-reachable (set a real `DB_PASS` in `.env` — the dev default is `ai`). Both services already carry `restart: unless-stopped`, so the platform survives reboots as long as Docker starts on boot. The override uses the `!reset`/`!override` merge tags, which need Docker Compose v2.24.4+.

JWT auth is on by default in prd and the app refuses to serve without a key. Mint one at os.agno.com (Connect OS → Live with your public URL, name it `Live AgentOS`, and flip Token-Based Authorization (JWT) on right on the connect panel — the UI generates the key; Settings → OS & Security → Token-Based Authorization (JWT) is the fallback if you connected without it) and paste the PEM into `.env` **quoted**, so Docker Compose reads the multi-line value as one variable:

```sh
JWT_VERIFICATION_KEY="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkq...
-----END PUBLIC KEY-----"
```

Live AgentOS Connections are a paid feature; use `PLATFORM30` to get 1 month off. `/health` and `/docs` stay public in prd (they are on the auth middleware's excluded-route list); everything else requires a token.

The public URL comes from whatever you put in front of the host — a domain + reverse proxy, or a tunnel (cloudflared, ngrok, `tailscale funnel`). Set it as `AGENTOS_URL` in `.env` so the scheduler can reach the platform, and use `https://<public-url>/mcp` as the connector URL in chat apps — with `MCP_CONNECT_SECRET` set in `.env`, `/mcp` serves its own OAuth so claude.ai and ChatGPT (web) can connect (see [MCP interface](#mcp-interface)). The full walkthrough lives in the README's [Run in production](README.md#run-in-production) section.

## Common Tasks

```bash
# Add a dependency
# 1. Edit pyproject.toml
./scripts/generate_requirements.sh   # keeps existing pins; add `upgrade` to refresh every pin
docker compor -d --build

# Bump agno (alpha, rc, and final releases are the same flow)
# 1. Edit the agno pin in pyproject.toml
./scripts/generate_requirements.sh agnoctl   # agno follows the pin; agnoctl must be named — agno only floors it at the previous release
docker compor -d --build
./scripts/validate.sh && python -m evals --tag smoke

# Build a multi-arch image (maintainer-only)
./scripts/build_image.sh

# Tail production logs (same host, prod override)
docker compose -f compose.yaml -f compose.prod.yaml logs -f agentos-api
```

## Documentation Links

- [Agno docs](https://docs.agno.com) — full framework reference.
- [Agno LLM-friendly docs](https://docs.agno.com/llms.txt) — concise overview, good for fetching.
- [AgentOS introduction](https://docs.agno.com/agent-os/introduction).
- [Agno tools / toolkits](https://docs.agno.com/tools/toolkits) — 100+ integrations.
- [Agno model providers](https://docs.agno.com/models) — OpenAI, Anthropic, Google, Ollama, Bedrock, Azure, etc.
- [Agno teams](https://docs.agno.com/teams/overview) — multi-agent routing/coordination.
- [Agno workflows](https://docs.agno.com/workflows/overview) — deterministic step-by-step pipelines.
- [Agno interfaces](https://docs.agno.com/agent-os/interfaces/overview) — Slack, Discord, Telegram, WhatsApp, custom UIs.
