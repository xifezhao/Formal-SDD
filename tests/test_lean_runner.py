"""
tests/test_lean_runner.py

Unit Tests for the Verification Oracle (LeanVerifier).

This module validates the integration between the Python Orchestrator and the
external Lean 4 compiler process. It uses mocking to simulate various
verification scenarios (Success, Failure, Timeout) without requiring a live
Lean installation.
"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import subprocess

# Add project root to path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.verification.lean_runner import LeanVerifier
from src.lmgpa.state_manager import LogicalSpec, Artifact, VerificationResult, Status

class TestLeanVerifier(unittest.TestCase):

    def setUp(self):
        """Setup a verifier instance and test artifacts."""
        self.verifier = LeanVerifier(project_root="mock_lean_lib")
        
        self.mock_spec = LogicalSpec(
            theorem_name="test_thm",
            lean_code="theorem test_thm : True := ?",
            imports=["FormalSDD.Test"]
        )
        
        self.mock_artifact = Artifact(
            program_code="def p := 1",
            proof_script="by trivial",
            language="lean"
        )

    @patch("src.verification.lean_runner.subprocess.run")
    @patch("src.verification.lean_runner.open") # Prevent actual file IO
    def test_verify_success(self, mock_open, mock_subprocess):
        """
        Test Case: Verification Success (Top).
        Simulates `lake build` returning 0.
        """
        # Configure Mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Building test_thm... [OK]"
        mock_process.stderr = ""
        mock_subprocess.return_value = mock_process

        # Execute
        result = self.verifier.verify(self.mock_spec, self.mock_artifact)

        # Assert
        self.assertEqual(result.status, Status.OK)
        self.assertEqual(result.unsolved_goals_count, 0)
        self.assertIn("correct", result.feedback.lower())

    @patch("src.verification.lean_runner.subprocess.run")
    @patch("src.verification.lean_runner.open")
    def test_verify_logic_error(self, mock_open, mock_subprocess):
        """
        Test Case: Logic Error (Err_lg).
        Simulates `lake build` returning 1 with 'unsolved goals'.
        """
        # Configure Mock
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = "error: unsolved goals\ncase goal\n⊢ True"
        mock_process.stderr = ""
        mock_subprocess.return_value = mock_process

        # Execute
        result = self.verifier.verify(self.mock_spec, self.mock_artifact)

        # Assert
        self.assertEqual(result.status, Status.ERR_LG)
        self.assertGreater(result.unsolved_goals_count, 0)
        self.assertIn("Proof State", result.feedback)

    @patch("src.verification.lean_runner.subprocess.run")
    @patch("src.verification.lean_runner.open")
    def test_verify_timeout(self, mock_open, mock_subprocess):
        """
        Test Case: Tool Error (Err_tool).
        Simulates subprocess timeout exception.
        """
        # Configure Mock to raise TimeoutExpired
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=["lake", "build"], timeout=30)

        # Execute
        result = self.verifier.verify(self.mock_spec, self.mock_artifact)

        # Assert
        self.assertEqual(result.status, Status.ERR_TOOL)
        self.assertIn("Timeout", result.summary)

    @patch("src.verification.lean_runner.subprocess.run")
    @patch("src.verification.lean_runner.open")
    def test_verify_system_error(self, mock_open, mock_subprocess):
        """
        Test Case: System Error (Missing Dependencies).
        Simulates `lake build` returning 1 with unknown package error.
        """
        # Configure Mock
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = "error: unknown package 'FormalSDD'"
        mock_process.stderr = ""
        mock_subprocess.return_value = mock_process

        # Execute
        result = self.verifier.verify(self.mock_spec, self.mock_artifact)

        # Assert
        # The parser logic treats "unknown package" as ERR_TOOL
        self.assertEqual(result.status, Status.ERR_TOOL)
        self.assertIn("Environment Error", result.summary)

if __name__ == "__main__":
    unittest.main()