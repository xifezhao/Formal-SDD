"""
src/verification/feedback_parser.py

The Feedback Parser: Raw Output -> Structured Prompt.

This module implements the error classification and parsing logic described in 
Section 4.2 of the Formal-SDD paper. It transforms the verbose stdout/stderr 
of the Lean 4 compiler into actionable feedback for the Synthesizer Agent.

Classifications:
- OK: Return code 0.
- Err_lg: Logical failures (proof incomplete, type mismatch).
- Err_tool: System failures (timeout, import error).
"""

import logging
import re
from typing import Tuple

from src.lmgpa.state_manager import Status, VerificationResult

logger = logging.getLogger("LMGPA.FeedbackParser")

class FeedbackParser:
    """
    Parses execution results from the Lean verification process.
    """

    def parse(self, stdout: str, stderr: str, return_code: int) -> VerificationResult:
        """
        Analyzes the process output to determine the verification status.
        
        Args:
            stdout: Standard output from `lake build`.
            stderr: Standard error from `lake build`.
            return_code: The exit code of the subprocess.
            
        Returns:
            A structured VerificationResult used by the Orchestrator.
        """
        full_output = (stdout + "\n" + stderr).strip()

        # --- Case 1: Success (Top) ---
        if return_code == 0:
            return VerificationResult(
                status=Status.OK,
                summary="Verification Successful",
                feedback="The proof is correct. No errors found.",
                raw_stdout=stdout,
                raw_stderr=stderr,
                unsolved_goals_count=0
            )

        # --- Case 2: Tooling Errors (Err_tool) ---
        # These are transient or environmental issues, not logical flaws in the proof.
        lower_output = full_output.lower()
        
        if "timeout" in lower_output or "deadline" in lower_output:
            return VerificationResult(
                status=Status.ERR_TOOL,
                summary="Timeout",
                feedback="The verifier timed out. The proof may be inefficient or infinite looping.",
                raw_stderr=stderr
            )
            
        if "out of memory" in lower_output or "segmentation fault" in lower_output:
            return VerificationResult(
                status=Status.ERR_TOOL,
                summary="Resource Exhaustion",
                feedback="System ran out of memory.",
                raw_stderr=stderr
            )
            
        if "unknown package" in lower_output or "no such file" in lower_output:
             return VerificationResult(
                status=Status.ERR_TOOL,
                summary="Environment Error",
                feedback="Missing imports or dependency configuration error.",
                raw_stderr=stderr
            )

        # --- Case 3: Logical Errors (Err_lg) ---
        # These are semantic failures that the LLM must fix.
        
        # 3.1 Calculate Semantic Potential (Phi)
        unsolved_goals = self._count_unsolved_goals(full_output)
        
        # 3.2 Extract Structured Context
        structured_feedback = self._extract_error_context(full_output)
        
        # Determine specific error subtype for summary
        error_summary = "Logical Error"
        if "tactic" in lower_output and "failed" in lower_output:
            error_summary = "Tactic Failure"
        elif "type mismatch" in lower_output:
            error_summary = "Type Mismatch"
        elif "unknown identifier" in lower_output:
            error_summary = "Syntax/Scope Error"

        return VerificationResult(
            status=Status.ERR_LG,
            summary=f"{error_summary} ({unsolved_goals} goals left)",
            feedback=structured_feedback,
            raw_stdout=stdout,
            raw_stderr=stderr,
            unsolved_goals_count=unsolved_goals
        )

    def _count_unsolved_goals(self, output: str) -> int:
        """
        Estimates the number of remaining proof obligations (Phi).
        Heuristic: Counts distinct 'case' blocks or defaults to 1.
        """
        if "unsolved goals" in output:
            # Lean 4 typically lists "case ..." for each goal
            case_count = output.count("case ")
            return max(1, case_count)
        return 1 # Default penalty for any error

    def _extract_error_context(self, output: str) -> str:
        """
        Extracts the most semantically relevant slice of the error log.
        This is crucial to prevent flooding the LLM context window with noise.
        """
        feedback_lines = []

        # 1. Extract the main error message
        # Regex to find lines starting with "error:" (standard Lean format)
        error_matches = re.findall(r"(?:error:|Error:)\s*(.*)", output)
        if error_matches:
            # Take the first unique error to focus the fix
            feedback_lines.append(f"Compiler Error: {error_matches[0]}")

        # 2. Extract the Proof State (The "Goal")
        # Lean prints "unsolved goals" followed by the hypothesis state.
        if "unsolved goals" in output:
            # Extract text between "unsolved goals" and double newline
            match = re.search(r"unsolved goals\n(.*?)(?:\n\n|\Z)", output, re.DOTALL)
            if match:
                state_snippet = match.group(1).strip()
                # Truncate if too long
                if len(state_snippet) > 1000:
                    state_snippet = state_snippet[:1000] + "... [truncated]"
                feedback_lines.append(f"Proof State at Failure:\n{state_snippet}")

        # 3. Fallback
        if not feedback_lines:
            # If regex fails, give the tail of the log
            snippet = output[-800:].strip()
            feedback_lines.append(f"Raw Output Tail:\n{snippet}")

        return "\n".join(feedback_lines)