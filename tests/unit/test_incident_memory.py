import pytest
from safelane.contracts import AnalysisRequest, RepoContext, EvidenceResult
from safelane.evidence import incident_memory

@pytest.fixture
def base_request():
    return AnalysisRequest(
        pr_number=1,
        repository="test/repo",
        changed_files=["src/payment/processor.py"],
        diff="test diff",
        received_at="2024-01-01T00:00:00Z",
        head_sha="abcdef",
        skip_autofix=False
    )

@pytest.fixture
def repo_context_mock():
    return RepoContext(
        registration_id="reg1",
        owner="testowner",
        repo="testrepo",
        gh_token="token",
        azure_search_endpoint="mock",
        azure_search_key="key",
        azure_tenant_id="tenant"
    )

@pytest.mark.unit
async def test_no_repo_context(base_request):
    result = await incident_memory.run(base_request)
    assert result.status == "pass"
    assert result.risk_score_modifier == 0
    assert result.findings[0] == "No deployment connection — no relevant incident history available."

@pytest.mark.unit
async def test_no_azure_config(base_request):
    context = RepoContext(
        registration_id="reg1",
        owner="testowner",
        repo="testrepo",
        gh_token="token"
    )
    result = await incident_memory.run(base_request, context)
    assert result.status == "pass"
    assert result.findings[0] == "No deployment connection — no relevant incident history available."

@pytest.mark.unit
async def test_with_mock_incidents_critical(base_request, repo_context_mock):
    result = await incident_memory.run(base_request, repo_context_mock)
    assert result.status == "critical"
    assert result.risk_score_modifier in range(50, 71)
    assert len(result.findings) == 1
    assert "INC-101" in result.findings[0]

@pytest.mark.unit
async def test_with_mock_incidents_warning(repo_context_mock):
    request = AnalysisRequest(
        pr_number=2,
        repository="test/repo",
        changed_files=["src/auth/middleware.py"],
        diff="test diff",
        received_at="2024-01-01T00:00:00Z",
        head_sha="abcdef",
        skip_autofix=False
    )
    result = await incident_memory.run(request, repo_context_mock)
    assert result.status == "warning"
    assert result.risk_score_modifier in range(25, 41)
    assert len(result.findings) == 1
    assert "INC-102" in result.findings[0]

@pytest.mark.unit
async def test_unrelated_filename(repo_context_mock):
    request = AnalysisRequest(
        pr_number=3,
        repository="test/repo",
        changed_files=["src/ui/button.tsx"],
        diff="test diff",
        received_at="2024-01-01T00:00:00Z",
        head_sha="abcdef",
        skip_autofix=False
    )
    result = await incident_memory.run(request, repo_context_mock)
    assert result.status == "pass"
    assert result.risk_score_modifier == 0
    assert len(result.findings) == 0

@pytest.mark.unit
async def test_azure_error(base_request, monkeypatch):
    context = RepoContext(
        registration_id="reg1",
        owner="testowner",
        repo="testrepo",
        gh_token="token",
        azure_search_endpoint="https://real.endpoint",
        azure_search_key="key",
        azure_tenant_id="tenant"
    )
    
    async def mock_run(*args, **kwargs):
        raise RuntimeError("Network error")
        
    monkeypatch.setattr("asyncio.to_thread", mock_run)
    
    result = await incident_memory.run(base_request, context)
    assert result.status == "warning"
    assert "Incident search temporarily unavailable" in result.findings[0]

@pytest.mark.unit
def test_derive_index_name():
    assert incident_memory.derive_index_name("MyOwner", "My_Repo.git") == "myowner-my-repo-git"
    assert incident_memory.derive_index_name("User123", "Project-A") == "user123-project-a"
