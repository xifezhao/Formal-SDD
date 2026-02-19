"""
src/verification/lean_runner.py

The Lean 4 Verification Oracle (V).

This module implements the deterministic verification step described in Section 4.1.
It acts as the interface between the Python-based LMGPA engine and the external 
Lean 4 process.

Responsibilities:
1. File Injection: Writes the candidate (p, pi) into a temporary .lean file.
2. Execution: Invokes the Lean compiler (via `lake build`) with a strict timeout.
3. Capture: Collects stdout/stderr for the Feedback Parser.
"""

import subprocess
import logging
import os
import time
from pathlib import Path
from typing import Optional

from src.lmgpa.state_manager import LogicalSpec, Artifact, VerificationResult, Status
from src.verification.feedback_parser import FeedbackParser

logger = logging.getLogger("LMGPA.Verifier")

# Paths relative to the project root (assuming execution from root)
LEAN_PROJECT_ROOT = Path("lean_lib")
TARGET_FILE = LEAN_PROJECT_ROOT / "Main.lean"

class LeanVerifier:
    """
    Wrapper around the Lean 4 compiler (lake).
    Executes: V(S_lg, p, pi) -> {ok, Err_lg, Err_tool}
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.parser = FeedbackParser()
        
        # Ensure the Lean project exists
        if not (self.project_root / "lakefile.lean").exists():
            logger.warning(f"lakefile.lean not found in {self.project_root}. Verification may fail.")

    def verify(self, logical_spec: LogicalSpec, artifact: Artifact, timeout: int = 30) -> VerificationResult:
        """
        Runs the verification oracle on the candidate artifact.
        
        Args:
            logical_spec: The theorem to prove (S_lg).
            artifact: The candidate implementation and proof (p, pi).
            timeout: Max execution time in seconds.
            
        Returns:
            A structured VerificationResult.
        """
        logger.info(f"Running Verification Oracle on {logical_spec.theorem_name}...")

        # 1. Inject Code into the Lean Environment
        # We construct a complete .lean file that imports dependencies, defines the program,
        # and states the theorem with the proof script.
        try:
            self._write_candidate_file(logical_spec, artifact)
        except IOError as e:
            logger.error(f"Failed to write candidate file: {e}")
            return VerificationResult(
                status=Status.ERR_TOOL,
                summary="IO Error during injection",
                feedback="System error: Could not write file.",
                raw_stderr=str(e)
            )

        # 2. Execute `lake build`
        # This compiles the injected file. If it compiles without error, the proof is valid.
        try:
            # Note: capturing output is crucial for feedback parsing
            start_time = time.time()
            process = subprocess.run(
                ["lake", "build"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            duration = time.time() - start_time
            
            stdout = process.stdout
            stderr = process.stderr
            return_code = process.returncode

            logger.debug(f"Lean process finished in {duration:.2f}s with code {return_code}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Verification timed out after {timeout}s.")
            return VerificationResult(
                status=Status.ERR_TOOL,
                summary="Timeout",
                feedback="The verification process timed out. The proof might be inefficient or looping.",
                raw_stderr=f"TimeoutExpired: {timeout}s"
            )
        except Exception as e:
            logger.error(f"Subprocess error: {e}")
            return VerificationResult(
                status=Status.ERR_TOOL,
                summary="Subprocess Error",
                feedback=f"System error: {str(e)}",
                raw_stderr=str(e)
            )

        # 3. Parse the Output
        # Delegate the raw compiler output to the FeedbackParser (Section 4.2)
        # to distinguish between Logical Errors (Err_lg) and success.
        return self.parser.parse(stdout, stderr, return_code)

    def _write_candidate_file(self, logical_spec: LogicalSpec, artifact: Artifact):
        """
        Constructs the content of Main.lean.
        
        Format:
        [Imports]
        [Program Definition p] -- Note: Python p is usually modeled or translated here.
                                  For the prototype, we assume p is defined in Lean directly
                                  or the artifact contains the Lean model of p.
        [Theorem S_lg]
        [Proof pi]
        """
        
        # In a full Neuro-Symbolic system, we might need to "transpile" the Python code
        # to a Lean model. For this experiment, we assume the Synthesizer outputs
        # the Lean model of the program directly in the `proof_script` or `program_code` 
        # (if it's a dual-output model).
        
        # For simplicity in this runner, we assume the artifact.proof_script contains
        # the FULL Lean content (Definitions + Proof) or we concatenate them.
        
        # NOTE: The logical_spec.lean_code has the theorem statement with a hole `:= ?`.
        # We need to replace `:= ?` with `:= by \n artifact.proof_script`.
        
        # Reconstruct imports
        imports = "\n".join([f"import {imp}" for imp in logical_spec.imports])
        
        # Construct the file content
        file_content = f"""
{imports}

-- Generated Program Model (p)
-- (In a real system, this would be the Lean definition of the Python code)
-- For now, we assume the Synthesizer includes necessary definitions in the proof script blocks.

-- The Proof (pi) and Theorem
-- We expect the Synthesizer to have provided the full proof block or tactic script.
"""
        
        # If the logical spec is just the theorem signature, we append the proof.
        # But usually, we want to construct: "theorem ... := by ..."
        
        # Heuristic injection:
        # 1. The imports
        # 2. The code/definitions (from artifact or implicit)
        # 3. The logical spec (theorem statement)
        # 4. The proof script
        
        # Let's assume logical_spec.lean_code is:
        # "theorem foo : ... := by sorry"
        # We strip the "sorry" and append the artifact.proof_script.
        
        theorem_base = logical_spec.lean_code.split(":= by")[0]
        
        full_content = f"""
{imports}

{theorem_base} := by
  {artifact.proof_script}
"""
        
        # Write to disk
        target_path = self.project_root / "FormalSDD" / "Main.lean" # Assuming structure
        # Or just overwrite the main entry point defined in lakefile
        # Let's try to write to where 'Main.lean' usually is.
        
        # Ensure directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target_path, "w") as f:
            f.write(full_content)
        
        logger.debug(f"Wrote candidate verification file to {target_path}")