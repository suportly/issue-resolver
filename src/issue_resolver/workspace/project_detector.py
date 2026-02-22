"""Detect test runner and language for a project workspace."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DetectedTestRunner:
    """Detected test runner configuration."""

    command: str
    timeout: int
    language: str
    runner_name: str


@dataclass
class DetectedInstaller:
    """Detected dependency installer configuration."""

    command: str
    timeout: int
    language: str


def detect_install_command(workspace_path: str) -> DetectedInstaller | None:
    """Detect the project's dependency install command.

    Returns None if no package manager is detected.
    """
    root = Path(workspace_path)

    # Python - prefer pyproject.toml (editable install), then requirements.txt
    if (root / "pyproject.toml").exists():
        pip_cmd = (
            "pip install -e '.[dev,test,tests]' 2>/dev/null"
            " || pip install -e '.[dev]' 2>/dev/null"
            " || pip install -e . 2>/dev/null"
            " || pip install -r requirements.txt 2>/dev/null"
            " || true"
        )
        return DetectedInstaller(
            command=pip_cmd, timeout=300, language="python",
        )
    if (root / "setup.py").exists() or (root / "setup.cfg").exists():
        pip_cmd = (
            "pip install -e '.[dev,test]' 2>/dev/null"
            " || pip install -e . 2>/dev/null"
            " || true"
        )
        return DetectedInstaller(
            command=pip_cmd, timeout=300, language="python",
        )
    if (root / "requirements.txt").exists():
        return DetectedInstaller(
            command="pip install -r requirements.txt",
            timeout=300,
            language="python",
        )

    # JavaScript / Node.js
    if (root / "package-lock.json").exists():
        return DetectedInstaller(
            command="npm ci", timeout=300, language="javascript",
        )
    if (root / "yarn.lock").exists():
        return DetectedInstaller(
            command="yarn install --frozen-lockfile",
            timeout=300,
            language="javascript",
        )
    if (root / "pnpm-lock.yaml").exists():
        return DetectedInstaller(
            command="pnpm install --frozen-lockfile",
            timeout=300,
            language="javascript",
        )
    if (root / "package.json").exists():
        return DetectedInstaller(
            command="npm install", timeout=300, language="javascript",
        )

    # Ruby
    if (root / "Gemfile").exists():
        return DetectedInstaller(command="bundle install", timeout=300, language="ruby")

    # Go (modules download)
    if (root / "go.mod").exists():
        return DetectedInstaller(command="go mod download", timeout=180, language="go")

    # Rust (cargo build fetches deps)
    if (root / "Cargo.toml").exists():
        return DetectedInstaller(command="cargo fetch", timeout=300, language="rust")

    return None


def detect_language(workspace_path: str) -> str | None:
    """Detect the primary programming language of a project.

    Uses marker files for detection (fast, no execution required).
    """
    root = Path(workspace_path)

    # Check in priority order
    if _has_any(root, ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"]):
        return "python"
    if _has_any(root, ["package.json"]):
        return "javascript"
    if _has_any(root, ["Cargo.toml"]):
        return "rust"
    if _has_any(root, ["go.mod"]):
        return "go"
    if _has_any(root, ["Gemfile", ".ruby-version"]):
        return "ruby"
    if _has_any(root, ["pom.xml"]):
        return "java"
    if _has_any(root, ["build.gradle", "build.gradle.kts"]):
        return "java"

    return None


def detect_test_runner(workspace_path: str) -> DetectedTestRunner | None:
    """Detect the project's test runner using priority-ordered file heuristics.

    Returns None if no test suite is detected.
    """
    root = Path(workspace_path)

    # Python / pytest
    if _has_any(root, ["pytest.ini", "conftest.py"]) or _pyproject_has_pytest(root):
        return DetectedTestRunner(
            command="python -m pytest -v --tb=short",
            timeout=300,
            language="python",
            runner_name="pytest",
        )

    # Python / unittest (fallback)
    if _has_any(root, ["pyproject.toml", "setup.py"]) and _has_test_files(root, "test_*.py"):
        return DetectedTestRunner(
            command="python -m unittest discover -v",
            timeout=300,
            language="python",
            runner_name="unittest",
        )

    # JavaScript / npm
    if (root / "package.json").exists():
        if _npm_has_test_script(root):
            return DetectedTestRunner(
                command="npm test",
                timeout=300,
                language="javascript",
                runner_name="npm",
            )

    # Rust / cargo
    if (root / "Cargo.toml").exists():
        return DetectedTestRunner(
            command="cargo test",
            timeout=600,
            language="rust",
            runner_name="cargo",
        )

    # Go
    if (root / "go.mod").exists() and _has_test_files(root, "*_test.go"):
        return DetectedTestRunner(
            command="go test -timeout 120s ./...",
            timeout=180,
            language="go",
            runner_name="go",
        )

    # Ruby / RSpec
    if _has_any(root, [".rspec"]) or (root / "spec").is_dir():
        return DetectedTestRunner(
            command="bundle exec rspec",
            timeout=300,
            language="ruby",
            runner_name="rspec",
        )

    # Java / Maven
    if (root / "pom.xml").exists():
        mvnw = root / "mvnw"
        cmd = "./mvnw test -B" if mvnw.exists() else "mvn test -B"
        return DetectedTestRunner(
            command=cmd,
            timeout=600,
            language="java",
            runner_name="maven",
        )

    # Java / Gradle
    if _has_any(root, ["build.gradle", "build.gradle.kts"]):
        gradlew = root / "gradlew"
        cmd = "./gradlew test" if gradlew.exists() else "gradle test"
        return DetectedTestRunner(
            command=cmd,
            timeout=600,
            language="java",
            runner_name="gradle",
        )

    logger.info("No test runner detected in %s", workspace_path)
    return None


def _has_any(root: Path, filenames: list[str]) -> bool:
    """Check if any of the given files exist in the root directory."""
    return any((root / f).exists() for f in filenames)


def _has_test_files(root: Path, pattern: str) -> bool:
    """Check if any test files matching the pattern exist (recursive)."""
    return any(root.rglob(pattern))


def _pyproject_has_pytest(root: Path) -> bool:
    """Check if pyproject.toml contains pytest configuration."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        content = pyproject.read_text()
        return "[tool.pytest" in content
    except OSError:
        return False


def _npm_has_test_script(root: Path) -> bool:
    """Check if package.json has a real test script (not the placeholder)."""
    import json

    pkg = root / "package.json"
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text())
        test_script = data.get("scripts", {}).get("test", "")
        # npm's default placeholder is not a real test script
        if "echo" in test_script and "Error" in test_script:
            return False
        return bool(test_script)
    except (json.JSONDecodeError, OSError):
        return False
