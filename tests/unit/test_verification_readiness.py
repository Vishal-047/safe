import pytest
from httpx import HTTPError, Response
from unittest.mock import patch, AsyncMock
from safelane.contracts import AnalysisRequest, RepoContext
from safelane.evidence.verification_readiness import run


@pytest.fixture
def repo_context():
    return RepoContext(owner="test", repo="testrepo", gh_token="valid_token")


@pytest.mark.unit
async def test_all_files_have_tests(repo_context):
    req = AnalysisRequest(
        pr_number=1,
        repository="test/testrepo",
        changed_files=["src/app.py"],
        diff="""--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-a\n+b"""
    )
    
    class MockClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            return Response(200)

    with patch("httpx.AsyncClient", return_value=MockClient()):
        result = await run(req, repo_context)
        
    assert result.status == "pass"
    assert result.risk_score_modifier == 0
    assert not result.findings


@pytest.mark.unit
async def test_missing_test_for_changed_file(repo_context):
    req = AnalysisRequest(
        pr_number=1,
        repository="test/testrepo",
        changed_files=["src/app.py"],
        diff="""--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-a\n+b"""
    )
    
    class MockClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            return Response(404)

    with patch("httpx.AsyncClient", return_value=MockClient()):
        result = await run(req, repo_context)
        
    assert result.status == "warning"
    assert result.risk_score_modifier == 30
    assert "Missing test for src/app.py" in result.findings


@pytest.mark.unit
async def test_multiple_missing_tests(repo_context):
    req = AnalysisRequest(
        pr_number=1,
        repository="test/testrepo",
        changed_files=["src/app.py", "src/utils.py", "src/helpers.py"],
        diff="fake diff"
    )
    
    class MockClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            return Response(404)

    with patch("httpx.AsyncClient", return_value=MockClient()):
        result = await run(req, repo_context)
        
    assert result.status == "critical"
    assert result.risk_score_modifier == 60
    assert len(result.findings) == 3


@pytest.mark.unit
async def test_deleted_test_file_detected(repo_context):
    req = AnalysisRequest(
        pr_number=1,
        repository="test/testrepo",
        changed_files=["tests/test_app.py"],
        diff="""--- a/tests/test_app.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-def test_x(): pass"""
    )
    
    result = await run(req, repo_context)
        
    assert result.status == "critical"
    assert result.risk_score_modifier == 60
    assert "Deleted test file detected: tests/test_app.py" in result.findings


@pytest.mark.unit
async def test_no_github_token():
    req = AnalysisRequest(pr_number=1, repository="test/testrepo", changed_files=["src/app.py"])
    context = RepoContext(owner="test", repo="testrepo", gh_token=None)
    
    result = await run(req, context)
        
    assert result.status == "warning"
    assert result.risk_score_modifier == 25
    assert "No GitHub token — cannot verify test coverage" in result.findings[0]


@pytest.mark.unit
async def test_github_api_error(repo_context):
    req = AnalysisRequest(
        pr_number=1,
        repository="test/testrepo",
        changed_files=["src/app.py"]
    )
    
    class MockClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            raise HTTPError("API failed")

    with patch("httpx.AsyncClient", return_value=MockClient()):
        result = await run(req, repo_context)
        
    assert result.status == "warning"
    assert result.risk_score_modifier == 25
    assert "GitHub API error — manual test review recommended" in result.findings[0]


@pytest.mark.unit
async def test_non_python_files_skipped(repo_context):
    req = AnalysisRequest(
        pr_number=1,
        repository="test/testrepo",
        changed_files=["README.md", "data.json"],
        diff=""
    )
    
    result = await run(req, repo_context)
        
    assert result.status == "pass"
    assert result.risk_score_modifier == 0
    assert not result.findings
