"""
AD Assessment Advisor
=====================

Agent focused on preparing assessment scenarios and producing execution scripts
for a separate PowerShell runner (safe production pattern).
"""

import json
from os import getenv
from pathlib import Path
from typing import Any

from agno.agent import Agent

from app.settings import default_model
from db import get_postgres_db


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def prepare_ad_assessment_scenario(
    scenario_name: str,
    domain: str,
    scenario_description: str = "",
    include_pki: bool = False,
    generate_mermaid: bool = False,
) -> str:
    """Create a scenario payload the user can run through workflow `ad-assessment-run`.

    Returns JSON payload ready to paste in workflow/message calls.
    """
    payload = {
        "scenario_name": scenario_name,
        "domain": domain,
        "scenario_description": scenario_description
        or "Avaliação READ-ONLY com correlação causal e geração de evidências.",
        "include_pki": bool(include_pki),
        "generate_mermaid": bool(generate_mermaid),
        "runner_url": getenv("AD_ASSESSMENT_RUNNER_URL", ""),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def locate_latest_assessment_job() -> str:
    """Locate latest generated job folder from ad-assessment-run workflow."""
    output_root = Path(getenv("AD_ASSESSMENT_OUTPUT_PATH", "/tmp/ad-assessment-output"))
    jobs_root = output_root / "jobs"

    if not jobs_root.exists():
        return "Nenhum job encontrado. Execute o workflow `ad-assessment-run` primeiro."

    job_dirs = [p for p in jobs_root.iterdir() if p.is_dir()]
    if not job_dirs:
        return "Nenhum job encontrado. Execute o workflow `ad-assessment-run` primeiro."

    latest = sorted(job_dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    scripts = latest / "scripts"
    artifacts = latest / "artifacts"
    scenario = latest / "scenario.json"

    return (
        f"Job mais recente: {latest}\n"
        f"- scenario: {scenario}\n"
        f"- run script: {scripts / 'run-ad-assessment.ps1'}\n"
        f"- verify llama script: {scripts / 'verify-llama-cuda.ps1'}\n"
        f"- runner submit script: {scripts / 'submit-to-runner.ps1'}\n"
        f"- artifacts dir: {artifacts}"
    )


INSTRUCTIONS = """\
Você é o AD Assessment Advisor.

Objetivo:
- Coletar o cenário a ser avaliado (domínio, escopo, PKI, mermaid, restrições).
- Gerar payload estruturado para o workflow `ad-assessment-run`.
- Guiar o usuário para execução segura via runner separado.

Regras operacionais:
- Não execute AD cmdlets no container principal do AgentOS.
- Sempre priorize padrão seguro: workflow gera scripts PowerShell; usuário/runner executa no ambiente com RSAT.
- Antes de recomendar execução, peça/valide:
  1) domínio alvo,
  2) se incluir PKI,
  3) se gerar Mermaid,
  4) janela de execução e restrições.

Formato de resposta:
- Curto, objetivo, com checklist e payload JSON pronto quando solicitado.
- Quando o usuário pedir "rodar", diga para acionar `ad-assessment-run` com o payload.
"""


ad_assessment_advisor = Agent(
    id="ad-assessment-advisor",
    name="AD Assessment Advisor",
    model=default_model(),
    db=get_postgres_db(),
    tools=[prepare_ad_assessment_scenario, locate_latest_assessment_job],
    instructions=INSTRUCTIONS,
    user_id="anonymous-user",
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
)
