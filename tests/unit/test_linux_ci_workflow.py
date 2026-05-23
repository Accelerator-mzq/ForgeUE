from pathlib import Path


def test_linux_ci_workflow_declares_ubuntu_and_pytest():
    """Linux CI 需要明确跑在 Ubuntu 上，并执行全量 pytest。"""
    workflow = Path(".github/workflows/linux-ci.yml")
    assert workflow.exists(), "Linux CI workflow 还没有落地"

    text = workflow.read_text(encoding="utf-8")
    assert "ubuntu-latest" in text
    assert "python -m pytest -q" in text
    assert "actions/checkout" in text
    assert "actions/setup-python" in text


def test_yaml_parsers_are_declared_as_runtime_dependencies():
    """Linux CI 的干净环境必须装上项目实际 import 的解析库。"""
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "PyYAML" in text
    assert "ruamel.yaml" in text
    assert "beautifulsoup4" in text
