"""
src/lmgpa/embedding/mapper.py

The Embedding Function (mu): TraceSpec -> LogicalSpec.

This module implements the semantic mapping described in Section 3.2 of the paper.
It transforms high-level behavioral predicates (S_tr) into rigid logical obligations (S_lg)
that can be checked by the Lean 4 kernel.

Key Features:
1. Template Expansion: Maps standard predicates (Mono, Live) to Lean library calls.
2. Context Management: Injects necessary imports (e.g., `import FormalSDD.Trace`).
3. Theorem Naming: Deterministically generates theorem names for stability.
"""

import logging
from typing import List, Dict

from src.lmgpa.state_manager import TraceSpec, LogicalSpec

logger = logging.getLogger("LMGPA.Embedding")

# Section 3.2: Standard Embedding Templates
# These templates correspond to the formal definitions in the 'FormalSDD' Lean library.
PREDICATE_TEMPLATES = {
    "Mono": "Trace.is_monotonic trace (λ s => s.val)",
    "Live": "LTL.eventually (λ s => s.response_received) trace",
    "Safe": "LTL.always (λ s => s.queue_size <= 10) trace",
    "Consist": "Trace.linearizable trace"
}

# The boilerplate for the Lean file structure
LEAN_HEADER = """
import FormalSDD.Trace
import FormalSDD.LTL
import FormalSDD.Concurrency

open FormalSDD

-- The user-defined State and Event types (Synthesized or Fixed)
structure State where
  val : Nat
  queue_size : Nat
  response_received : Bool
  deriving Repr, DecidableEq

-- The target theorem derived from Trace Predicates
"""

class EmbeddingMapper:
    """
    Implements the function mu: S_tr -> S_lg.
    """

    def __init__(self):
        logger.info("Initializing Embedding Mapper (mu)...")

    def embed(self, trace_spec: TraceSpec) -> LogicalSpec:
        """
        Lifts a TraceSpec to a LogicalSpec.
        
        Args:
            trace_spec: The behavioral specification (S_tr).
            
        Returns:
            A fully formed LogicalSpec (S_lg) ready for verification.
        """
        logger.info(f"Embedding TraceSpec '{trace_spec.name}' into Lean 4...")

        theorem_name = f"{trace_spec.name}_Correctness"
        
        # 1. Translate Predicates to Lean Terms
        # We iterate through the raw strings like "Mono: ..." and map them.
        lean_propositions = []
        
        for raw_pred in trace_spec.predicates:
            # Simple parsing: "Type: Definition"
            if ":" in raw_pred:
                pred_type, _ = raw_pred.split(":", 1)
                pred_type = pred_type.strip()
                
                # Apply Embedding Template mu(p)
                if pred_type in PREDICATE_TEMPLATES:
                    lean_propositions.append(PREDICATE_TEMPLATES[pred_type])
                else:
                    # Fallback: Treat unknown predicates as comments or custom defs
                    # In a full version, this would use an LLM to auto-formalize the definition.
                    logger.warning(f"Unknown predicate type '{pred_type}'. Using generic embedding.")
                    lean_propositions.append(f"-- Custom Property: {raw_pred}")
            else:
                 lean_propositions.append(f"-- Unparsed: {raw_pred}")

        # 2. Construct the Conjunction of Properties
        # Theorem: forall trace, P1(trace) /\ P2(trace) ...
        if lean_propositions:
            # Join with Logic AND
            conjunction = " ∧ ".join(lean_propositions)
        else:
            conjunction = "True" # Trivial fallback

        # 3. Assemble the Full Lean Code
        # We quantify over all valid execution traces produced by the program 'p'
        # Note: The program 'p' is injected as a hypothesis or definition in the verification step.
        lean_code = LEAN_HEADER + f"""
theorem {theorem_name} (trace : List State) :
  {conjunction} := by
  sorry -- The proof obligation (hole) to be filled by the Synthesizer
"""

        logger.debug(f"Generated Lean Code:\n{lean_code}")

        return LogicalSpec(
            theorem_name=theorem_name,
            lean_code=lean_code,
            imports=["FormalSDD.Trace", "FormalSDD.LTL"]
        )