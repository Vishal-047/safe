import os
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

logger = logging.getLogger('safelane.foundry')

def get_foundry_client():
    """Get a Foundry project connection. Returns None if not configured."""
    conn_str = os.getenv("AZURE_FOUNDRY_PROJECT_CONNECTION_STRING")
    if not conn_str:
        return None
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
        return AIProjectClient.from_connection_string(conn_str, credential=DefaultAzureCredential())
    except Exception:
        logger.debug("Foundry client unavailable, continuing without it")
        return None

def setup_tracing():
    """Initialize OpenTelemetry tracing to Application Insights. No-op if not configured."""
    conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn_str:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=conn_str)
    except Exception:
        logger.debug("Tracing setup skipped")

@contextmanager
def trace_agent_call(agent_name: str):
    """Context manager for tracing an individual agent call. No-op if tracing unavailable."""
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("safelane")
        with tracer.start_as_current_span(f"safelane.agent.{agent_name}") as span:
            span.set_attribute("safelane.agent.name", agent_name)
            yield span
    except Exception:
        yield None

@contextmanager
def trace_orchestrate(pr_number: int, repo: str):
    """Context manager for tracing the full orchestration. No-op if unavailable."""
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("safelane")
        with tracer.start_as_current_span("safelane.orchestrate") as span:
            span.set_attribute("safelane.pr_number", pr_number)
            span.set_attribute("safelane.repo", repo)
            yield span
    except Exception:
        yield None

async def check_content_safety(text: str) -> bool:
    """Screen text through Azure Content Safety. Returns True if safe, True (default-safe) if unavailable."""
    endpoint = os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT")
    key = os.getenv("AZURE_CONTENT_SAFETY_KEY")
    if not endpoint or not key:
        return True
    try:
        from azure.ai.contentsafety import ContentSafetyClient
        from azure.ai.contentsafety.models import AnalyzeTextOptions
        from azure.core.credentials import AzureKeyCredential
        import asyncio
        client = ContentSafetyClient(endpoint, AzureKeyCredential(key))
        result = await asyncio.to_thread(
            client.analyze_text, AnalyzeTextOptions(text=text[:5000])
        )
        # Check if any category severity is above threshold
        for cat in [result.hate_result, result.self_harm_result, result.sexual_result, result.violence_result]:
            if cat and cat.severity > 2:
                return False
        return True
    except Exception:
        return True  # default-safe on failure

def apply_policy_guardrails(verdict_report, pr_payload) -> dict | None:
    """Apply policy guardrails: auto-escalation + audit trail. Returns audit entry or None."""
    audit_entry = {
        "score": verdict_report.confidence_score,
        "decision": verdict_report.decision,
        "escalated": verdict_report.confidence_score < 30,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pr_number": pr_payload.pr_number if hasattr(pr_payload, 'pr_number') else None,
        "repo": pr_payload.repo if hasattr(pr_payload, 'repo') else None,
    }
    logger.info(f"Audit: score={audit_entry['score']} decision={audit_entry['decision']} escalated={audit_entry['escalated']}")
    # If tracing is available, export as a span
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("safelane")
        with tracer.start_as_current_span("safelane.audit") as span:
            for k, v in audit_entry.items():
                span.set_attribute(f"safelane.audit.{k}", str(v))
    except Exception:
        pass
    return audit_entry

async def evaluate_quality(text: str, reference: str) -> dict | None:
    """Evaluate groundedness/relevance of LLM text. Returns scores or None if unavailable."""
    # Optional: use Azure AI Evaluation SDK
    return None
