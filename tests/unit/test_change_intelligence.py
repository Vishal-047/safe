import pytest
import os
from unittest.mock import patch

from safelane.contracts import AnalysisRequest, RepoContext, EvidenceResult
from safelane.evidence.change_intelligence import run

@pytest.fixture
def base_request():
    return AnalysisRequest(
        pr_number=1,
        repository="owner/repo",
        diff="+ new line",
    )

@pytest.mark.unit
async def test_clean_diff(base_request):
    base_request.diff = "+ def foo():\n+     pass\n"
    result = await run(base_request)
    assert result.status == "pass"
    assert result.risk_score_modifier == 0
    assert len(result.findings) == 0

@pytest.mark.unit
async def test_empty_diff(base_request):
    base_request.diff = "   \n"
    result = await run(base_request)
    assert result.status == "warning"
    assert result.risk_score_modifier == 20
    assert "no diff content" in result.findings[0]

@pytest.mark.unit
async def test_large_diff(base_request):
    base_request.diff = "\n".join(["+ line"] * 501)
    result = await run(base_request)
    assert result.status == "warning"
    assert result.risk_score_modifier == 30
    assert any("Large change detected" in f for f in result.findings)

@pytest.mark.unit
async def test_removed_try_except(base_request):
    base_request.diff = "- try:\n-     do_something()\n- except Exception:\n-     pass"
    result = await run(base_request)
    assert result.status == "warning"
    assert result.risk_score_modifier == 30
    assert any("error handling" in f for f in result.findings)

@pytest.mark.unit
async def test_removed_retry(base_request):
    base_request.diff = "- @retry(max_retries=3)\n+ def no_retry_foo():"
    result = await run(base_request)
    assert result.status == "warning"
    assert result.risk_score_modifier == 30
    assert any("retry" in f.lower() for f in result.findings)

@pytest.mark.unit
async def test_drop_table(base_request):
    base_request.diff = "+ DROP TABLE users;"
    result = await run(base_request)
    assert result.status == "critical"
    assert result.risk_score_modifier == 60
    assert any("schema" in f.lower() for f in result.findings)

@pytest.mark.unit
async def test_alter_column_warning(base_request):
    base_request.diff = "+ ALTER COLUMN status TYPE varchar;"
    result = await run(base_request)
    assert result.status == "warning"
    assert result.risk_score_modifier == 30
    assert any("ALTER" in f for f in result.findings)

@pytest.mark.unit
async def test_multiple_findings(base_request):
    base_request.diff = "- try:\n-     pass\n- @retry\n- def foo():"
    result = await run(base_request)
    assert result.status == "critical"
    assert result.risk_score_modifier == 60

@pytest.mark.unit
async def test_llm_failure_fallback(base_request):
    base_request.diff = "- try:\n-     pass"
    
    with patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": "https://fake"}):
        with patch("safelane.evidence.change_intelligence._reword_findings_with_llm", side_effect=Exception("LLM down")):
            result = await run(base_request)
            assert result.status == "warning"
            assert result.risk_score_modifier == 30
            assert any("error handling" in f for f in result.findings)

@pytest.mark.unit
async def test_llm_failure_fallback_integration(base_request):
    base_request.diff = "- try:\n-     pass"
    
    with patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": "https://fake"}):
        # Let's mock AzureOpenAI to raise an error when initialized
        with patch("openai.AzureOpenAI", side_effect=Exception("API error"), create=True):
            result = await run(base_request)
            assert result.status == "warning"
            assert result.risk_score_modifier == 30
            assert any("error handling" in f for f in result.findings)

