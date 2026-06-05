import os
import requests
from job_queue import Job


def create_pr(job: Job, branch: str) -> str:
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPO"]
    resp = requests.post(
        f"https://api.github.com/repos/{repo}/pulls",
        json={
            "title": job.prompt_name.replace("-", " ").title(),
            "body": job.prompt_content[:500],
            "head": branch,
            "base": job.base_branch,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["html_url"]
