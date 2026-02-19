"""
src/verification/potential.py

Semantic Potential Function (Phi).

This module implements the logic to calculate the 'Semantic Potential' of a 
synthesis state, denoted as Phi(x) in the Formal-SDD paper (Section 5.3).

The potential function serves two purposes:
1. Theoretical: It acts as the Lyapunov function for the convergence proof (Theorem 2).
2. Empirical: It provides the y-axis metric for the convergence graphs in the evaluation.

Definition:
    Phi(x) = w_1 * count(unsolved_goals) + w_2 * count(sorry_admissions) + w_3 * is_error
    
Where 'sorry' is the Lean 4 keyword for an admitted (unproven) goal.
"""

import re
import logging
from typing import Optional

from src.lmgpa.state_manager import Artifact, VerificationResult, Status

logger = logging.getLogger("LMGPA.Potential")

class PotentialCalculator:
    """
    Computes the scalar 'energy' of a synthesis state.
    Goal: Minimize Phi(x) -> 0.
    """
    
    def __init__(self, weight_goals: float = 1.0, weight_sorry: float = 2.0, penalty_error: float = 5.0):
        self.w_goals = weight_goals
        self.w_sorry = weight_sorry
        self.w_error = penalty_error

    def compute(self, artifact: Artifact, result: Optional[VerificationResult] = None) -> float:
        """
        Calculates Phi(x) based on the artifact's source code and verification feedback.
        
        Args:
            artifact: The candidate code (p, pi).
            result: The output from the verification oracle (optional).
            
        Returns:
            A non-negative float representing the distance to correctness.
        """
        # 1. Base Potential: Static Analysis (Count 'sorry')
        # Using 'sorry' is a valid tactic to defer proof, but represents non-zero potential.
        sorry_count = self._count_sorry_tokens(artifact.proof_script)
        potential = sorry_count * self.w_sorry
        
        # 2. Dynamic Potential: Verification Feedback
        if result:
            if result.status == Status.OK:
                # If verified successfully AND no 'sorry' in code (checked by compiler too), potential is 0.
                # Note: Lean accepts 'sorry' as valid logic, but prints warnings.
                # We trust the compiler's warning check, but here we enforce strictness.
                if sorry_count == 0:
                    return 0.0
                else:
                    # Technically valid Lean, but not a complete proof.
                    pass 
            
            elif result.status == Status.ERR_LG:
                # Add the count of explicit goals reported by Lean
                potential += result.unsolved_goals_count * self.w_goals
                
            elif result.status == Status.ERR_TOOL:
                # Tool errors (timeout) are high-potential states (infinite distance conceptually)
                # We assign a heuristic penalty to represent "bad state".
                potential += self.w_error

        # 3. Fallback / Parsing Failures
        if result and result.status == Status.ERR_LG and result.unsolved_goals_count == 0:
            # If it's a logical error but parsing failed to find "goals",
            # it might be a syntax error preventing goal display.
            # Treat as a generic high penalty.
            potential += self.w_error

        return potential

    def _count_sorry_tokens(self, lean_code: str) -> int:
        """
        Statically counts the occurrences of the 'sorry' tactic.
        """
        # Simple regex matching whole word 'sorry'
        # Ignores comments (--) roughly
        code_without_comments = re.sub(r'--.*', '', lean_code)
        matches = re.findall(r'\bsorry\b', code_without_comments)
        return len(matches)