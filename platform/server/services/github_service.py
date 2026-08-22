import httpx
import base64
import logging

logger = logging.getLogger('safelane.platform')

WORKFLOW_TEMPLATE = """name: SafeLane PR Gate
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  safelane_analysis:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Trigger SafeLane Orchestrator
        env:
          EVENT_PAYLOAD: ${{ toJson(github.event) }}
        run: |
          printf '%s' "$EVENT_PAYLOAD" | curl -X POST "{orchestrator_url}/webhook/pr" -H "Content-Type: application/json" -H "X-GitHub-Event: pull_request" --data-binary @- --fail-with-body
"""

async def validate_token(token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        if response.status_code != 200:
            raise ValueError("Invalid GitHub token")
        return response.json()

async def commit_workflow_file(owner: str, repo: str, token: str, orchestrator_url: str):
    workflow_content = WORKFLOW_TEMPLATE.replace("{orchestrator_url}", orchestrator_url)
    
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Check if file exists to get sha
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/safelane-gate.yml"
        
        get_resp = await client.get(url, headers=headers)
        
        data = {
            "message": "Add SafeLane PR Gate workflow",
            "content": base64.b64encode(workflow_content.encode()).decode()
        }
        
        if get_resp.status_code == 200:
            data["sha"] = get_resp.json()["sha"]
            
        put_resp = await client.put(url, headers=headers, json=data)
        if put_resp.status_code not in (200, 201):
            raise Exception(f"Failed to commit workflow: {put_resp.text}")
