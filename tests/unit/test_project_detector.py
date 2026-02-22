"""Unit tests for project test runner detection."""

import json
from pathlib import Path

import pytest

from issue_resolver.workspace.project_detector import (
    detect_language,
    detect_test_runner,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


class TestDetectLanguage:
    def test_python_pyproject(self, workspace: Path) -> None:
        (workspace / "pyproject.toml").touch()
        assert detect_language(str(workspace)) == "python"

    def test_python_setup_py(self, workspace: Path) -> None:
        (workspace / "setup.py").touch()
        assert detect_language(str(workspace)) == "python"

    def test_javascript_package_json(self, workspace: Path) -> None:
        (workspace / "package.json").write_text("{}")
        assert detect_language(str(workspace)) == "javascript"

    def test_rust_cargo(self, workspace: Path) -> None:
        (workspace / "Cargo.toml").touch()
        assert detect_language(str(workspace)) == "rust"

    def test_go_mod(self, workspace: Path) -> None:
        (workspace / "go.mod").touch()
        assert detect_language(str(workspace)) == "go"

    def test_ruby_gemfile(self, workspace: Path) -> None:
        (workspace / "Gemfile").touch()
        assert detect_language(str(workspace)) == "ruby"

    def test_java_maven(self, workspace: Path) -> None:
        (workspace / "pom.xml").touch()
        assert detect_language(str(workspace)) == "java"

    def test_java_gradle(self, workspace: Path) -> None:
        (workspace / "build.gradle").touch()
        assert detect_language(str(workspace)) == "java"

    def test_unknown_language(self, workspace: Path) -> None:
        assert detect_language(str(workspace)) is None


class TestDetectTestRunner:
    def test_pytest_ini(self, workspace: Path) -> None:
        (workspace / "pytest.ini").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "pytest"
        assert "pytest" in runner.command

    def test_pytest_conftest(self, workspace: Path) -> None:
        (workspace / "conftest.py").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "pytest"

    def test_pytest_pyproject(self, workspace: Path) -> None:
        (workspace / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "pytest"

    def test_python_unittest_fallback(self, workspace: Path) -> None:
        (workspace / "setup.py").touch()
        tests_dir = workspace / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "unittest"

    def test_npm_test(self, workspace: Path) -> None:
        pkg = {"scripts": {"test": "jest"}}
        (workspace / "package.json").write_text(json.dumps(pkg))
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "npm"

    def test_npm_placeholder_script_ignored(self, workspace: Path) -> None:
        """npm's default 'echo Error...' should not be treated as a test suite."""
        pkg = {"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}
        (workspace / "package.json").write_text(json.dumps(pkg))
        runner = detect_test_runner(str(workspace))
        assert runner is None

    def test_cargo_test(self, workspace: Path) -> None:
        (workspace / "Cargo.toml").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "cargo"
        assert runner.timeout == 600

    def test_go_test(self, workspace: Path) -> None:
        (workspace / "go.mod").touch()
        (workspace / "main_test.go").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "go"

    def test_go_no_test_files(self, workspace: Path) -> None:
        (workspace / "go.mod").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is None

    def test_rspec(self, workspace: Path) -> None:
        (workspace / ".rspec").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "rspec"

    def test_maven(self, workspace: Path) -> None:
        (workspace / "pom.xml").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "maven"

    def test_maven_with_wrapper(self, workspace: Path) -> None:
        (workspace / "pom.xml").touch()
        (workspace / "mvnw").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert "./mvnw" in runner.command

    def test_gradle(self, workspace: Path) -> None:
        (workspace / "build.gradle").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert runner.runner_name == "gradle"

    def test_gradle_with_wrapper(self, workspace: Path) -> None:
        (workspace / "build.gradle.kts").touch()
        (workspace / "gradlew").touch()
        runner = detect_test_runner(str(workspace))
        assert runner is not None
        assert "./gradlew" in runner.command

    def test_no_test_suite(self, workspace: Path) -> None:
        runner = detect_test_runner(str(workspace))
        assert runner is None
