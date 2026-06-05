import os
import requests
from config import Config
from job_queue import Job


def create_pr(config: Config, job: Job, branch: str) -> str:
    org = os.environ["AZURE_DEVOPS_ORG"]
    project = os.environ["AZURE_DEVOPS_PROJECT"]
    pat = os.environ["AZURE_DEVOPS_PAT"]
    repo_name = os.path.basename(config.repos[job.repo].rstrip("/"))
    url = (
        f"https://dev.azure.com/{org}/{project}"
        f"/_apis/git/repositories/{repo_name}/pullrequests?api-version=7.1"
    )
    resp = requests.post(
        url,
        json={
            "title": job.prompt_name.replace("-", " ").title(),
            "description": job.prompt_content[:500],
            "sourceRefName": f"refs/heads/{branch}",
            "targetRefName": f"refs/heads/{job.base_branch}",
        },
        auth=("", pat),
        timeout=30,
    )
    resp.raise_for_status()
    pr_id = resp.json()["pullRequestId"]
    return f"https://dev.azure.com/{org}/{project}/_git/{repo_name}/pullrequest/{pr_id}"
