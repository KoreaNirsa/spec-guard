from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path


WORKFLOW_ROOT = Path(".github") / "workflows"


@dataclass(frozen=True)
class WorkflowInstallResult:
    name: str
    path: Path
    installed: bool
    overwritten: bool


WORKFLOWS = {
    "readiness-gate": ("SpecGuard Readiness Gate", "specguard-readiness-gate.yml"),
    "pr-review": ("SpecGuard PR Review", "specguard-pr-review.yml"),
}


def install_workflow(repo_root: Path, workflow: str, *, force: bool = False) -> WorkflowInstallResult:
    if workflow not in WORKFLOWS:
        raise ValueError(f"Unknown SpecGuard workflow: {workflow}")

    name, filename = WORKFLOWS[workflow]
    destination = repo_root / WORKFLOW_ROOT / filename
    existed = destination.exists()
    if existed and not force:
        return WorkflowInstallResult(name=name, path=destination, installed=False, overwritten=False)

    source = resources.files("tools").joinpath("resources", "workflows", filename)
    if not source.is_file():
        raise FileNotFoundError(f"Packaged workflow template is missing: {filename}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    return WorkflowInstallResult(name=name, path=destination, installed=True, overwritten=existed)

