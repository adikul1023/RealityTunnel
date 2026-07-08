import yaml
import pytest
from pathlib import Path

def test_ci_workflow_lint_steps_do_not_ignore_failures():
    ci_path = Path(".github/workflows/ci.yml")
    if not ci_path.exists():
        pytest.skip("CI workflow not found")
        
    with open(ci_path, "r") as f:
        content = f.read()
        
    # We shouldn't use `yaml.safe_load` here just to check for `|| true` in the exact strings
    # But it's safer to parse it properly
    parsed = yaml.safe_load(content)
    
    lint_job = parsed.get("jobs", {}).get("lint-and-typecheck", {})
    steps = lint_job.get("steps", [])
    
    # We should have at least 1 step
    assert len(steps) > 0
    
    for step in steps:
        run_cmd = step.get("run", "")
        if "ruff check" in run_cmd or "black" in run_cmd or "mypy" in run_cmd:
            assert "|| true" not in run_cmd, f"Lint step '{step.get('name')}' must not ignore failures (|| true)"

def test_all_workflows_have_explicit_permissions():
    workflows_dir = Path(".github/workflows")
    if not workflows_dir.exists():
        pytest.skip("Workflows directory not found")
        
    for workflow_file in workflows_dir.glob("*.yml"):
        with open(workflow_file, "r") as f:
            parsed = yaml.safe_load(f.read())
            
            assert "permissions" in parsed, f"Workflow {workflow_file.name} is missing explicit top-level 'permissions:' block"
