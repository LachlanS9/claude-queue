from config import Config
from job_queue import Job
from pr import github as _github
from pr import azuredevops as _azdo


def create_pr(config: Config, job: Job, branch: str) -> str:
    if config.pr_provider == "github":
        return _github.create_pr(job, branch)
    if config.pr_provider == "azuredevops":
        return _azdo.create_pr(config, job, branch)
    raise ValueError(f"Unknown pr_provider: {config.pr_provider!r}. Use 'github' or 'azuredevops'.")
