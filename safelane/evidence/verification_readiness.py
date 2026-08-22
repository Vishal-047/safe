import logging
import httpx
from pathlib import Path

from safelane.contracts import AnalysisRequest, RepoContext, EvidenceResult

logger = logging.getLogger('safelane.verification_readiness')


async def run(request: AnalysisRequest, repo_context: RepoContext | None = None) -> EvidenceResult:
    """
    Checks whether changed Python files have corresponding test files.
    """
    request.skip_autofix = True

    if not repo_context or not repo_context.gh_token:
        return EvidenceResult(
            module="verification_readiness",
            status="warning",
            risk_score_modifier=25,
            findings=["No GitHub token — cannot verify test coverage"],
            recommended_action="Manual test review recommended"
        )

    findings = []
    missing_tests = 0
    deleted_tests = 0

    # 1. Detect deleted test files
    for file_path in request.changed_files:
        path = Path(file_path)
        if path.suffix == ".py" and (path.name.startswith("test_") or path.name.endswith("_test.py")):
            if f"--- a/{file_path}" in request.diff and "+++ /dev/null" in request.diff:
                deleted_tests += 1
                findings.append(f"Deleted test file detected: {file_path}")

    # 2. Check changed python files for missing tests
    changed_py_files = [
        f for f in request.changed_files
        if f.endswith('.py') and not f.endswith('__init__.py')
        and not Path(f).name.startswith("test_")
        and not Path(f).name.endswith("_test.py")
    ]

    repository = request.repository or f"{repo_context.owner}/{repo_context.repo}"

    async with httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {repo_context.gh_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        timeout=10.0
    ) as client:
        for f in changed_py_files:
            path = Path(f)
            basename = path.name
            expected_name = f"test_{basename}"
            
            # Remove leading src/ if present for cleaner paths, but simple check works too.
            possible_paths = [
                f"tests/{expected_name}",
                f"tests/{path.parent}/{expected_name}",
                f"tests/{path.parent.name}/{expected_name}"
            ]
            
            test_exists = False
            try:
                for p in possible_paths:
                    p = p.replace("\\", "/").replace("//", "/")
                    resp = await client.get(f"https://api.github.com/repos/{repository}/contents/{p}")
                    if resp.status_code == 200:
                        test_exists = True
                        break
                    elif resp.status_code == 404:
                        continue
                    else:
                        resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.warning(f"GitHub API error checking {f}: {e}")
                return EvidenceResult(
                    module="verification_readiness",
                    status="warning",
                    risk_score_modifier=25,
                    findings=["GitHub API error — manual test review recommended"],
                    recommended_action="Manual test review recommended"
                )

            if not test_exists:
                missing_tests += 1
                findings.append(f"Missing test for {f}")

    # 3. Scoring
    score = 0
    status = "pass"
    if missing_tests == 0 and deleted_tests == 0:
        score = 0
        status = "pass"
    elif missing_tests in (1, 2) and deleted_tests == 0:
        score = 30
        status = "warning"
    else:
        # 3+ missing tests or any deleted test files
        score = 60
        status = "critical"

    return EvidenceResult(
        module="verification_readiness",
        status=status,
        risk_score_modifier=score,
        findings=findings,
        recommended_action="Add tests for changed files"
    )
