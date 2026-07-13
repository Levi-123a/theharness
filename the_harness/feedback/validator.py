"""Deterministic test validator that runs pytest and captures output."""

import subprocess

from the_harness.models import TestResult


class TestValidator:
    """Runs pytest on a test file and returns a TestResult.

    Attributes:
        workspace: The workspace directory to run tests in.
        timeout: Maximum seconds to wait for pytest to finish.
    """

    # Tell pytest this is not a test class (name starts with "Test")
    __test__ = False

    def __init__(self, workspace: str, timeout: int = 30) -> None:
        self._workspace = workspace
        self._timeout = timeout

    def validate(self, test_path: str) -> TestResult:
        """Run pytest on the given test path and return the result.

        Args:
            test_path: Path to the test file (relative to workspace).

        Returns:
            TestResult with exit_code, stdout, stderr, and passed flag.
        """
        cmd = ["python", "-m", "pytest", "--tb=short", "-v", test_path]
        try:
            proc = subprocess.run(
                cmd,
                cwd=self._workspace,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                exit_code=-1,
                stdout="",
                stderr=f"Test timed out after {self._timeout}s",
                passed=False,
            )
        except FileNotFoundError:
            return TestResult(
                exit_code=-1,
                stdout="",
                stderr="pytest not found",
                passed=False,
            )
        return TestResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            passed=proc.returncode == 0,
        )
