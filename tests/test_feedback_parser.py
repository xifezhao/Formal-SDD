"""
tests/test_feedback_parser.py

Unit Tests for the Feedback Parser.

This module validates the error classification logic described in Section 4.2.
It ensures that raw compiler logs are correctly transformed into structured
signals (Status, Phi(x), Feedback Prompt) for the LMGPA engine.
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.verification.feedback_parser import FeedbackParser
from src.lmgpa.state_manager import Status

class TestFeedbackParser(unittest.TestCase):

    def setUp(self):
        self.parser = FeedbackParser()

    def test_parse_success(self):
        """
        Test Case: Compilation Success.
        Input: Return code 0.
        Expected: Status.OK.
        """
        stdout = "Building FormalSDD.Main... [OK]"
        stderr = ""
        rc = 0
        
        result = self.parser.parse(stdout, stderr, rc)
        
        self.assertEqual(result.status, Status.OK)
        self.assertEqual(result.unsolved_goals_count, 0)
        self.assertIn("correct", result.feedback.lower())

    def test_parse_logical_error_tactic(self):
        """
        Test Case: Tactic Failure (Logical Error).
        Input: Return code 1, 'tactic failed' message.
        Expected: Status.ERR_LG.
        """
        stdout = """
error: tactic 'simp' failed, nested error:
tactic 'rfl' failed, equality lhs
  1
is not definitionally equal to rhs
  2
"""
        stderr = ""
        rc = 1
        
        result = self.parser.parse(stdout, stderr, rc)
        
        self.assertEqual(result.status, Status.ERR_LG)
        self.assertIn("Tactic Failure", result.summary)
        # Check if the specific error context was extracted
        self.assertIn("tactic 'simp' failed", result.feedback)

    def test_parse_logical_error_unsolved_goals(self):
        """
        Test Case: Unsolved Goals (Incomplete Proof).
        Input: Return code 1, 'unsolved goals' message with proof state.
        Expected: Status.ERR_LG, extracted goal state in feedback.
        """
        stdout = """
/path/to/Main.lean:10:2: error: unsolved goals
case goal
trace : List State
⊢ Trace.is_monotonic trace
"""
        stderr = ""
        rc = 1
        
        result = self.parser.parse(stdout, stderr, rc)
        
        self.assertEqual(result.status, Status.ERR_LG)
        # Parser heuristic should count cases
        self.assertEqual(result.unsolved_goals_count, 1)
        # Verify extraction of the goal state (crucial for LLM prompting)
        self.assertIn("Trace.is_monotonic trace", result.feedback)

    def test_parse_multiple_goals(self):
        """
        Test Case: Multiple Unsolved Goals.
        Input: Multiple 'case' markers.
        Expected: Correct count of Phi(x).
        """
        stdout = """
error: unsolved goals
case goal_1
⊢ 1 = 1
case goal_2
⊢ 2 = 2
"""
        rc = 1
        result = self.parser.parse(stdout, "", rc)
        
        self.assertEqual(result.status, Status.ERR_LG)
        self.assertEqual(result.unsolved_goals_count, 2)

    def test_parse_tool_error_timeout(self):
        """
        Test Case: Deterministic Timeout.
        Input: 'deterministic timeout' message.
        Expected: Status.ERR_TOOL (Should trigger backoff, not refinement).
        """
        stdout = ""
        stderr = "Error: (deterministic) timeout at 'simp', maximum number of steps exceeded"
        rc = 1
        
        result = self.parser.parse(stdout, stderr, rc)
        
        self.assertEqual(result.status, Status.ERR_TOOL)
        self.assertIn("Timeout", result.summary)

    def test_parse_tool_error_missing_pkg(self):
        """
        Test Case: Environment/Dependency Error.
        Input: 'unknown package'.
        Expected: Status.ERR_TOOL.
        """
        stderr = "error: unknown package 'FormalSDD'"
        rc = 1
        
        result = self.parser.parse("", stderr, rc)
        
        self.assertEqual(result.status, Status.ERR_TOOL)
        self.assertIn("Environment Error", result.summary)

if __name__ == "__main__":
    unittest.main()