"""
LMGPA: Language Model Guided Proof Automation Engine.

This package implements the core logic for the Formal-SDD framework, orchestrating
the interaction between stochastic Large Language Models (actings as samplable kernels)
and deterministic formal verification kernels (Lean 4).

It corresponds to Section 4 of the Formal-SDD paper.
"""

# 只导入状态管理 (State Space: s, p, pi, h) - 避免循环导入
from .state_manager import SynthesisState

# Orchestrator和Agents应该在需要时显式导入，不在__init__中导入
# 这样可以避免循环导入问题

__all__ = [
    "SynthesisState",
]

# 版本信息
__version__ = "0.1.0-prototype"