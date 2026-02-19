"""
baselines/baseline_1_zeroshot.py

Baseline 1: Standard LLM Zero-shot Direct Synthesis.

This module implements the control group for the comparative evaluation (Section 5.2).
It represents the traditional workflow where a developer prompts an LLM with a 
requirement and accepts the generated code without formal verification.

Methodology:
1. Input: Natural Language Intent (I) from the benchmark.
2. Process: Single-turn query to the LLM (Claude 3.5 Sonnet).
3. Output: Python source code.

Hypothesis (RQ1):
This baseline is expected to fail on concurrency invariants (Safety Violations)
due to the lack of a semantic feedback loop.
"""

import logging
import re
import os
from pathlib import Path
from typing import Optional

# Reuse the Agent infrastructure, configured for direct synthesis
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.base import Agent, AgentConfig

logger = logging.getLogger("Baselines.ZeroShot")

# System prompt for direct synthesis without formal constraints
# Note: It encourages confidence ("You are an expert") which may mask hallucinations.
DIRECT_SYNTHESIS_PROMPT = """
You are an expert Python software engineer specializing in high-performance systems.
Your task is to implement the user's requirements as a self-contained Python class.

Instructions:
- Write clean, idiomatic, and efficient code.
- Handle edge cases intuitively.
- Do NOT explain your reasoning verboseley; just provide the code.
- Wrap the code in a ```python block.
"""

class DirectSynthesisAgent(Agent):
    """
    A concrete implementation of the Agent for the Zero-shot baseline.
    Performs direct synthesis without Lean 4 verification or feedback loops.
    """
    def run(self, input_state: str) -> str:
        # Not used in this simple baseline
        pass

class ZeroShotRunner:
    """
    Executes the Zero-shot baseline on a given benchmark.
    """

    def __init__(self, output_dir: str = "results/baseline_1"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize the LLM
        config = AgentConfig(
            model_name="claude-3-5-sonnet-20240620",
            system_prompt=DIRECT_SYNTHESIS_PROMPT,
            temperature=0.7 # Standard creative sampling
        )
        self.agent = DirectSynthesisAgent(config)

    def run_benchmark(self, benchmark_id: str, prompt_path: Path):
        """
        Runs the baseline on a specific benchmark problem.
        
        Args:
            benchmark_id: Unique ID (e.g., "01_speculative_stream").
            prompt_path: Path to the prompt.txt file.
        """
        logger.info(f"Running Baseline 1 (Zero-shot) on {benchmark_id}...")

        # 1. Read the Intent (I)
        try:
            with open(prompt_path, "r") as f:
                user_intent = f.read().strip()
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {prompt_path}")
            return

        # 2. Construct the Prompt
        # Pure Zero-shot strategy: Direct requirement-to-code mapping
        # No intermediate formalization or iterative refinement
        messages = [
            {"role": "user", "content": f"Requirement:\n{user_intent}\n\nImplement this in Python."}
        ]

        # 3. Query the LLM (Direct synthesis without verification)
        raw_response = self.agent.sample_kernel(messages)

        # 4. Extract Code
        code = self._extract_python_code(raw_response)
        
        # 5. Save Artifact
        self._save_result(benchmark_id, code)

    def _extract_python_code(self, text: str) -> str:
        """
        Extracts Python code from LLM-generated text.
        
        Uses heuristic pattern matching to identify code blocks.
        If multiple blocks are present, selects the longest as the primary implementation.
        """
        matches = re.findall(r"```python(.*?)```", text, re.DOTALL)
        if matches:
            # Select the longest block (heuristic for main implementation)
            return max(matches, key=len).strip()
        
        # Fallback: If no markdown formatting, check for code patterns
        if "def " in text or "class " in text:
            return text.strip()
            
        logger.warning("No code block detected in baseline response.")
        return ""

    def _save_result(self, benchmark_id: str, code: str):
        """
        Saves the generated code to solution.py.
        """
        benchmark_dir = self.output_dir / benchmark_id
        benchmark_dir.mkdir(exist_ok=True)
        
        file_path = benchmark_dir / "solution.py"
        
        with open(file_path, "w") as f:
            f.write(code)
            
        logger.info(f"Baseline solution saved to {file_path}")

if __name__ == "__main__":
    # Simple test driver
    logging.basicConfig(level=logging.INFO)
    
    # Initialize baseline runner for local testing
    runner = ZeroShotRunner()
    # In a real run, this would be called by experiments/run_all.py
    print("Baseline 1 Runner initialized. Ready to execute benchmarks.")