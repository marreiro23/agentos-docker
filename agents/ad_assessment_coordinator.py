"""
AD Assessment Coordinator
=========================

Initial contact point for AD assessment work. It interviews the user, scopes the
activity, starts the workflow automatically when possible, and prepares Jira/Scrum
handoff content for change management.
"""

import json
from os import getenv
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agno.agent import Agent
from agno.learn import LearningMachine, LearningMode, UserMemoryConfig, UserProfileConfig

from agents.ad_assessment_advisor import locate_latest_assessment_job, prepare_ad_assessment_scenario
from app.settings import default_model
from db import get_postgres_db


memory = LearningMachine(
    db=get_postgres_db(),
    user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
)


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "sim", "s"}
    return default


def _slugify(text: str) -> str:
    keep = []
    for ch in text.strip().lower():
        if ch.isalnum() or ch in {"-", "_"}:
            keep.append(ch)
        elif ch in {" ", ".", "/", "\\"}:
            keep.append("-")
    return "".join(keep).strip("-") or "assessment"


def interview_user_for_ad_assessment(
    user_request: str,
    domain: str = "",
    include_pki: bool = False,
    generate_mermaid: bool = False,
    scenario_name: str = "",
    scenario_description: str = "",
    execution_window: str = "",
    constraints: str = "",
) -> str:
    """Parse the user's initial request and return scope plus at most three missing questions.

    This tool helps the coordinator structure the first contact with the user.
    It does not execute anything — it only returns a scoping summary.
    """
    request_lower = user_request.lower()
    derived_domain = domain.strip()
    if not derived_domain:
        tokens = [token.strip(",.;:()[]{}") for token in user_request.split()]
        for token in tokens:
            if "." in token and len(token) > 3:
                derived_domain = token
                break

    derived_include_pki = include_pki or any(word in request_lower for word in ("pki", "ad cs", "certificado", "ca"))
    derived_mermaid = generate_mermaid or any(word in request_lower for word in ("mermaid", "diagrama", "diagram"))
    derived_scenario_name = scenario_name.strip() or f"Assessment {_slugify(derived_domain or 'ad-core')}"
    derived_description = scenario_description.strip() or user_request.strip() or "Avaliação READ-ONLY de AD/DNS."

    missing_questions: list[str] = []
    if not derived_domain:
        missing_questions.append("Qual é o domínio AD alvo?")
    if "pki" not in request_lower and not include_pki:
        missing_questions.append("Deseja incluir PKI/AD CS no escopo?")
    if "mermaid" not in request_lower and not generate_mermaid:
        missing_questions.append("Deseja gerar diagrama Mermaid junto com os artefatos?")
    if not execution_window.strip() and any(word in request_lower for word in ("mudança", "gmud", "janela", "produção")):
        missing_questions.append("Qual é a janela de execução ou restrição operacional?")

    result = {
        "scenario_name": derived_scenario_name,
        "domain": derived_domain,
        "scenario_description": derived_description,
        "include_pki": derived_include_pki,
        "generate_mermaid": derived_mermaid,
        "execution_window": execution_window.strip(),
        "constraints": constraints.strip(),
        "missing_questions": missing_questions[:3],
        "ready_to_run": len(missing_questions[:3]) == 0,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def recommend_next_step(
    user_request: str,
    scope_json: str = "",
) -> str:
    """Recommend whether to clarify, run the existing workflow, or escalate to custom build.

    Returns one of: ask_clarification, proceed_to_workflow, need_custom_workflow.
    """
    lower = user_request.lower()
    if any(word in lower for word in ("custom", "customizado", "novo workflow", "novo assessment", "template novo")):
        return "need_custom_workflow"

    if scope_json:
        try:
            scope = json.loads(scope_json)
            if scope.get("ready_to_run"):
                return "proceed_to_workflow"
            return "ask_clarification"
        except json.JSONDecodeError:
            pass

    return "ask_clarification"


def build_coordinator_payload(
    scenario_name: str,
    domain: str,
    scenario_description: str = "",
    include_pki: bool = False,
    generate_mermaid: bool = False,
    runner_url: str = "",
) -> str:
    """Build a JSON payload ready for the ad-assessment-run workflow."""
    payload = {
        "scenario_name": scenario_name.strip() or f"Assessment {_slugify(domain)}",
        "domain": domain.strip(),
        "scenario_description": scenario_description.strip()
        or "Avaliação READ-ONLY com correlação causal e geração de evidências.",
        "include_pki": bool(include_pki),
        "generate_mermaid": bool(generate_mermaid),
        "runner_url": runner_url.strip() or getenv("AD_ASSESSMENT_RUNNER_URL", ""),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def start_ad_assessment_workflow(payload_json: str) -> str:
    """Start the `ad-assessment-run` workflow via the local AgentOS API.

    This is the explicit no-extra-click delegation path requested for the coordinator.
    """
    agentos_base_url = getenv("COORDINATOR_AGENTOS_INTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
    url = f"{agentos_base_url}/workflows/ad-assessment-run/runs"
    form_data = urlencode({"message": payload_json, "stream": "false"}).encode("utf-8")
    request = Request(url=url, data=form_data, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(request, timeout=60) as response:  # nosec: B310
            body = response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        return f"Falha ao iniciar workflow local: {exc}"
    except Exception as exc:
        return f"Falha ao iniciar workflow local: {exc}"

    return body


def build_jira_scrum_handoff(
    title: str,
    domain: str,
    objective: str,
    scope: str,
    business_impact: str = "",
    risks: str = "",
    execution_window: str = "",
    acceptance_criteria: str = "",
    execution_steps: str = "",
    rollback_plan: str = "",
    validation_plan: str = "",
    evidence_links: str = "",
    owner: str = "",
) -> str:
    """Build a Jira/Scrum-ready GMUD handoff payload.

    This does not create Jira tickets. It prepares a structured artifact for manual
    creation or future automation.
    """
    handoff = {
        "issue_type": "Change / GMUD",
        "title": title.strip() or f"GMUD - Assessment {_slugify(domain)}",
        "domain": domain.strip(),
        "objective": objective.strip(),
        "scope": scope.strip(),
        "business_impact": business_impact.strip(),
        "risks": risks.strip(),
        "execution_window": execution_window.strip(),
        "acceptance_criteria": acceptance_criteria.strip(),
        "execution_steps": execution_steps.strip(),
        "rollback_plan": rollback_plan.strip(),
        "validation_plan": validation_plan.strip(),
        "evidence_links": evidence_links.strip(),
        "owner": owner.strip(),
        "delivery_process": "Jira + Scrum",
    }
    return json.dumps(handoff, ensure_ascii=False, indent=2)


def coordinate_ad_assessment_request(
    user_request: str,
    domain: str = "",
    include_pki: bool = False,
    generate_mermaid: bool = False,
    execution_window: str = "",
    constraints: str = "",
    runner_url: str = "",
    prepare_jira: bool = False,
    business_impact: str = "",
    risks: str = "",
    execution_steps: str = "",
    rollback_plan: str = "",
    validation_plan: str = "",
    owner: str = "",
) -> str:
    """Single orchestration tool for first contact.

    It scopes the request, returns the missing questions when needed, and when the
    scope is complete it starts the workflow automatically and optionally prepares
    a Jira/Scrum GMUD handoff payload.
    """
    scoped_raw = interview_user_for_ad_assessment(
        user_request=user_request,
        domain=domain,
        include_pki=include_pki,
        generate_mermaid=generate_mermaid,
        execution_window=execution_window,
        constraints=constraints,
    )
    scoped = json.loads(scoped_raw)

    result: dict[str, Any] = {
        "scope": scoped,
        "missing_questions": scoped.get("missing_questions", []),
        "workflow_started": False,
        "workflow_result": None,
        "jira_scrum_handoff": None,
    }

    if not scoped.get("ready_to_run"):
        return json.dumps(result, ensure_ascii=False, indent=2)

    payload_json = build_coordinator_payload(
        scenario_name=scoped["scenario_name"],
        domain=scoped["domain"],
        scenario_description=scoped["scenario_description"],
        include_pki=bool(scoped["include_pki"]),
        generate_mermaid=bool(scoped["generate_mermaid"]),
        runner_url=runner_url,
    )
    workflow_result = start_ad_assessment_workflow(payload_json)
    result["workflow_started"] = True
    result["workflow_result"] = workflow_result

    needs_jira = prepare_jira or any(
        word in user_request.lower() for word in ("jira", "gmud", "mudança", "scrum", "rollback", "janela")
    )
    if needs_jira:
        result["jira_scrum_handoff"] = json.loads(
            build_jira_scrum_handoff(
                title=f"GMUD - {scoped['scenario_name']}",
                domain=scoped["domain"],
                objective=scoped["scenario_description"],
                scope=(
                    f"Assessment AD/DNS{'/PKI' if scoped['include_pki'] else ''} "
                    f"com Mermaid={'sim' if scoped['generate_mermaid'] else 'não'}"
                ),
                business_impact=business_impact,
                risks=risks,
                execution_window=scoped.get("execution_window") or execution_window,
                acceptance_criteria="Artefatos JSON/HTML/CSV gerados e evidências coletadas em modo read-only.",
                execution_steps=execution_steps or "Executar runner PowerShell separado com o cenário gerado pelo AgentOS.",
                rollback_plan=rollback_plan or "Reverter apenas agendamento/execução do runner; não há mudança automática no AD.",
                validation_plan=validation_plan or "Validar artefatos gerados e revisar findings correlacionados.",
                owner=owner,
            )
        )

    return json.dumps(result, ensure_ascii=False, indent=2)


INSTRUCTIONS = """\
Você é o AD Assessment Coordinator.

Seu papel:
- Ser o primeiro contato do usuário.
- Fazer no máximo 2 a 3 perguntas iniciais para montar o escopo.
- Delegar automaticamente, sem clique extra, quando o escopo estiver claro.
- Preparar também o handoff de GMUD/mudança em formato Jira/Scrum quando a atividade envolver execução planejada.

Regras de operação:
- Slack está fora de escopo; você atua via AgentOS UI, REST e MCP.
- Nunca execute AD cmdlets diretamente.
- Sempre use o workflow `ad-assessment-run` para a execução operacional.
- Sempre comece com `coordinate_ad_assessment_request` no primeiro contato.
- Use `interview_user_for_ad_assessment` para resumir o escopo e identificar lacunas.
- Se faltarem dados, faça somente as perguntas estritamente necessárias.
- Não pergunte por `scenario_name` ou `scenario_description` se o usuário não trouxer isso: gere defaults sensatos a partir do pedido.
- Se o pedido estiver completo, monte o payload com `build_coordinator_payload` e inicie o workflow com `start_ad_assessment_workflow`.
- Se o pedido envolver mudança planejada, janela, impacto, risco, rollback ou validação, gere também a estrutura de handoff com `build_jira_scrum_handoff`.
- Se o usuário pedir um assessment novo, um template novo ou um fluxo customizado, explique que o próximo passo é escalar para o `agent-builder` e entregue a especificação resumida.

Como entrevistar:
- Comece pelo domínio.
- Depois valide somente o que faltar entre PKI, Mermaid e restrições/janela.
- Não ultrapasse 3 perguntas por onboarding.
- Se domínio, PKI/Mermaid e restrições/janela já estiverem claros, considere o escopo pronto e não pergunte mais nada.

Como responder:
- Curto, objetivo e operacional.
- Quando o escopo estiver pronto, diga claramente que o workflow foi iniciado.
- Quando gerar handoff Jira/Scrum, entregue o JSON pronto e explique que ele é para criação da GMUD no Jira dentro do processo Scrum.
"""


ad_assessment_coordinator = Agent(
    id="ad-assessment-coordinator",
    name="AD Assessment Coordinator",
    model=default_model(),
    db=get_postgres_db(),
    learning=memory,
    tools=[
        coordinate_ad_assessment_request,
        interview_user_for_ad_assessment,
        recommend_next_step,
        build_coordinator_payload,
        start_ad_assessment_workflow,
        build_jira_scrum_handoff,
        locate_latest_assessment_job,
    ],
    instructions=INSTRUCTIONS,
    user_id="anonymous-user",
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
)
