"""
baselines/baseline_2_tdd.py

Baseline 2: LLM + Unit Tests (Test-Driven Development).

This module implements the "Industrial Standard" baseline described in Section 5.2.
It represents the workflow of autonomous coding agents that rely on iterative 
unit testing (execution-based feedback) to ensure correctness.

Methodology:
1. Input: Natural Language Intent (I) + A suite of Python Unit Tests (T).
2. Process: Iterative Refinement Loop (Max 10 iterations).
   - Generate/Refine Code.
   - Run `pytest`.
   - If Pass -> Success.
   - If Fail -> Feed stdout/stderr back to LLM as feedback.
3. Output: Python source code that passes the provided tests.

Hypothesis (RQ1):
While this baseline outperforms Zero-shot, it is expected to fail on 
"Heisenbugs" (race conditions) that are probabilistically hard to catch 
with standard unit tests but are caught by Formal-SDD's verification.
"""

import logging
import subprocess
import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Reuse the Agent infrastructure
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.base import Agent, AgentConfig

logger = logging.getLogger("Baselines.TDD")

# TDD System Prompt: Instructs the agent to fix bugs based on test output
TDD_SYSTEM_PROMPT = """
You are a Senior Python Developer practicing Test-Driven Development.
Your goal is to write a Python class that passes a specific set of Unit Tests.

Process:
1. You will receive a problem description and the current Unit Test failures.
2. You must modify the code to FIX the errors reported by pytest.
3. Do NOT simply delete the tests; you must satisfy them.
4. Pay attention to edge cases and concurrency if mentioned.

Output Format:
Return the complete, fixed Python code in a ```python``` block.
"""

class TDDAgent(Agent):
    """
    An agent that refines code based on pytest feedback.
    """
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.config.system_prompt = TDD_SYSTEM_PROMPT

class TDDRunner:
    """
    Executes the TDD baseline loop.
    """

    def __init__(self, max_iterations: int = 10, output_dir: str = "results/baseline_2"):
        self.max_iterations = max_iterations
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure the agent for iterative debugging
        config = AgentConfig(
            model_name="claude-3-5-sonnet-20240620",
            temperature=0.5, # Lower temperature for stability during debugging
            system_prompt=TDD_SYSTEM_PROMPT
        )
        self.agent = TDDAgent(config)

    def run_benchmark(self, benchmark_id: str, prompt_path: Path, test_path: Path):
        """
        Runs the TDD loop for a specific benchmark.
        
        Args:
            benchmark_id: Unique ID (e.g., "01_speculative_stream").
            prompt_path: Path to the requirement (prompt.txt).
            test_path: Path to the provided unit tests (tests.py).
        """
        logger.info(f"Starting Baseline 2 (TDD) on {benchmark_id}...")

        # 1. Setup Workspace (Isolated environment for execution)
        work_dir = self.output_dir / benchmark_id
        work_dir.mkdir(exist_ok=True, parents=True)
        
        # Copy the provided unit tests to the workspace
        # We assume the test file imports `solution` (e.g., `from solution import SpeculativeStream`)
        target_test_file = work_dir / "tests.py"
        try:
            with open(test_path, "r") as src, open(target_test_file, "w") as dst:
                dst.write(src.read())
        except FileNotFoundError:
            logger.error(f"Test file not found: {test_path}")
            return

        # Read Intent
        with open(prompt_path, "r") as f:
            intent = f.read().strip()

        # 2. Refinement Loop
        current_code = ""
        # Initial feedback is just the instruction
        feedback = "Initial Request: Write code to satisfy the requirements and pass the tests."
        
        # Maintain conversation history
        messages = []

        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")

            # Construct Prompt with Feedback
            user_msg = f"""
Requirement: {intent}

Current Status/Feedback:
{feedback}

Please provide the implementation in `solution.py`.
"""
            messages.append({"role": "user", "content": user_msg})

            # Sample LLM
            response = self.agent.sample_kernel(messages)
            current_code = self._extract_python_code(response)
            
            # Handle cases where LLM refuses or fails to generate code
            if not current_code:
                logger.warning("No code generated. Retrying with explicit instruction...")
                feedback = "Error: You did not output a valid Python code block. Please output the code inside ```python``` tags."
                # Don't add to history to avoid polluting context with empty turns
                continue

            # Save Candidate to disk
            solution_path = work_dir / "solution.py"
            with open(solution_path, "w") as f:
                f.write(current_code)

            # 3. Run Tests (The Oracle)
            success, test_output = self._run_pytest(work_dir)

            if success:
                logger.info(f"Tests Passed at iteration {iteration + 1}!")
                # Save final artifact
                with open(work_dir / "final_solution.py", "w") as f:
                    f.write(current_code)
                return

            # If failed, update feedback for next loop
            logger.info(f"Tests Failed. Feedback size: {len(test_output)} chars")
            
            # Truncate feedback to fit context window, focusing on the end (summary)
            truncated_output = test_output[-2000:] if len(test_output) > 2000 else test_output
            feedback = f"pytest output (failures):\n...\n{truncated_output}" 
            
            # Append assistant response to history to maintain conversation context
            messages.append({"role": "assistant", "content": response})

        # End of Loop
        logger.warning(f"Failed to converge after {self.max_iterations} iterations. Saving last attempt.")
        with open(work_dir / "failed_solution.py", "w") as f:
            f.write(current_code)

    def _run_pytest(self, work_dir: Path) -> Tuple[bool, str]:
        """
        Runs pytest in the workspace.
        
        Returns: 
            (passed: bool, output: str)
        """
        try:
            # Command: pytest tests.py --tb=short (short tracebacks for cleaner prompting)
            result = subprocess.run(
                ["pytest", "tests.py", "--tb=short"], 
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=10 # Prevent infinite loops in generated code
            )
            return (result.returncode == 0, result.stdout + result.stderr)
        
        except subprocess.TimeoutExpired:
            return (False, "Timeout: Tests took too long to execute. Check for infinite loops.")
        except Exception as e:
            return (False, f"System Error running pytest: {e}")

    def _extract_python_code(self, text: str) -> str:
        """
        Extracts the python code block.
        """
        matches = re.findall(r"```python(.*?)```", text, re.DOTALL)
        if matches:
            return max(matches, key=len).strip()
        
        # Fallback: check for generic code blocks
        matches_generic = re.findall(r"```(.*?)```", text, re.DOTALL)
        if matches_generic:
             # Heuristic: verify it looks like python
             candidate = max(matches_generic, key=len).strip()
             if "def " in candidate or "class " in candidate:
                 return candidate
                 
        return ""

if __name__ == "__main__":
    # Test Driver
    logging.basicConfig(level=logging.INFO)
    print("Baseline 2 (TDD) Runner Initialized.")