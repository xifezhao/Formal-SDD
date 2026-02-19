"""
src/lmgpa/orchestrator.py

The Central Controller of the LMGPA Engine.

This module implements the Stochastic State Machine described in Section 3.3 of the paper.
It manages the transition dynamics of the synthesis process:
    State x_t = (spec, program, proof, history)
    Transition: Driven by the Verification Oracle (V) and the LLM Kernel (K_theta).

Key Responsibilities:
1. Initialize the Intent (I) -> Trace Spec (S_tr) via the Formalizer.
2. Embed Trace Spec -> Logical Spec (S_lg) via the Mapper.
3. Run the Refinement Loop:
   - Sample K_theta( . | history ) -> (p, pi)
   - Query V(S_lg, p, pi) -> {ok, Err_lg, Err_tool}
   - Update history h' = h + feedback
"""

import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

# Internal modules (Assumed to exist based on the file tree)
from .state_manager import SynthesisState, Artifact, VerificationResult, Status
from src.agents.formalizer import FormalizerAgent
from src.agents.synthesizer import SynthesizerAgent
from src.embedding.mapper import EmbeddingMapper
from src.verification.lean_runner import LeanVerifier

# Configure Logger
logger = logging.getLogger("LMGPA.Orchestrator")

@dataclass
class LMGPAConfig:
    """Configuration for the synthesis run."""
    max_refinement_steps: int = 15  # Upper bound T (Theorem 2)
    timeout_per_verification: int = 30 # Seconds
    backoff_factor: float = 1.5     # For Err_tool recovery
    model_name: str = "claude-3-5-sonnet-20240620" # The stochastic kernel

@dataclass
class SynthesisLog:
    """Data structure for plotting the Convergence Graph (Fig 5)."""
    iterations: List[int] = field(default_factory=list)
    semantic_potential: List[int] = field(default_factory=list) # Phi(x)
    events: List[str] = field(default_factory=list)

class Orchestrator:
    def __init__(
        self,
        config: LMGPAConfig,
        formalizer: FormalizerAgent,
        synthesizer: SynthesizerAgent,
        mapper: EmbeddingMapper,
        verifier: LeanVerifier
    ):
        self.config = config
        self.formalizer = formalizer
        self.synthesizer = synthesizer
        self.mapper = mapper
        self.verifier = verifier
        self.metrics = SynthesisLog()

    def solve(self, natural_language_intent: str) -> Optional[Artifact]:
        """
        Main entry point for the Formal-SDD workflow (Section 2.3).
        
        Args:
            natural_language_intent: The user's prompt (I).
            
        Returns:
            A Verified Artifact (p, pi) if successful (Top), else None (Bot).
        """
        logger.info(f"Starting LMGPA Synthesis for intent: {natural_language_intent[:50]}...")

        # --- Step 1: Formalization (I -> S_tr) ---
        # Agent: Formalizer
        trace_spec = self.formalizer.formalize(natural_language_intent)
        logger.info(f"Generated Trace Specification: {trace_spec.name}")

        # --- Step 2: Logical Embedding (S_tr -> S_lg) ---
        # Component: Embedding Function (mu) - Section 3.2
        logical_spec = self.mapper.embed(trace_spec)
        logger.info(f"Embedded into Lean 4 Theorem: {logical_spec.theorem_name}")

        # --- Step 3: Initialize State Machine ---
        # State x_0 = (s, empty_prog, empty_proof, empty_history)
        current_state = SynthesisState(
            trace_spec=trace_spec,
            logical_spec=logical_spec,
            history=[]
        )

        # --- Step 4: Refinement Loop (Section 3.3) ---
        result_artifact = self._refinement_loop(current_state)

        if result_artifact:
            logger.info("Synthesis Successful: Reached State Top (Success).")
        else:
            logger.error("Synthesis Failed: Reached State Bot (Failure).")
        
        return result_artifact

    def _refinement_loop(self, state: SynthesisState) -> Optional[Artifact]:
        """
        Executes the Stochastic State Machine transitions.
        
        Corresponds to the loop: 
        1. Sample (p, pi) ~ K_theta
        2. Verify V(p, pi)
        3. Update history or Terminate
        """
        step = 0
        
        while step < self.config.max_refinement_steps:
            logger.info(f"--- Refinement Step {step} ---")
            
            # 1. Stochastic Transition: Sample Kernel K_theta
            # The LLM proposes a candidate program and proof based on current history
            candidate: Artifact = self.synthesizer.sample_kernel(state)
            
            # 2. Oracle Query: Verify V(S_lg, p, pi)
            # This is the deterministic check against the Lean kernel
            verification_result: VerificationResult = self.verifier.verify(
                state.logical_spec, 
                candidate, 
                timeout=self.config.timeout_per_verification
            )

            # 3. Metric Logging (For Evaluation RQ2)
            # Phi(x) = number of unsolved goals (or 0 if success)
            phi_x = verification_result.unsolved_goals_count
            self.metrics.iterations.append(step)
            self.metrics.semantic_potential.append(phi_x)
            logger.debug(f"Semantic Potential Phi(x_{step}) = {phi_x}")

            # 4. State Transition Logic
            if verification_result.status == Status.OK:
                # Case: Success (Top)
                # Axiom 2 (Soundness) guarantees this artifact is correct.
                return candidate

            elif verification_result.status == Status.ERR_LG:
                # Case: Logical Error (Refinement)
                # We update the history h' = h + feedback
                # The feedback is parsed structured data (e.g., counter-example trace)
                logger.warning(f"Logical Error: {verification_result.summary}")
                
                state.history.append({
                    "step": step,
                    "artifact": candidate,
                    "feedback": verification_result.feedback, # Structured prompt
                    "raw_error": verification_result.raw_stderr
                })
                
                # Proceed to next iteration (Implicitly handled by loop)

            elif verification_result.status == Status.ERR_TOOL:
                # Case: Tooling Error (Timeout/Crash)
                # Deterministic Recovery Strategy (Section 4.2)
                logger.warning(f"Tool Error: {verification_result.summary}. Backing off.")
                time.sleep(self.config.backoff_factor ** (step + 1))
                # Do NOT increment step count for transient tool errors if desired,
                # but here we increment to bound total wall time.
                state.history.append({
                    "step": step,
                    "error_type": "TOOL_ERROR",
                    "feedback": "System timeout. Optimize proof efficiency."
                })

            step += 1

        # Reached Max Steps -> State Bot
        logger.error(f"Exceeded max refinement steps ({self.config.max_refinement_steps}).")
        return None