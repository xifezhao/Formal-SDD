/-
Copyright (c) 2026 Formal-SDD Authors. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Formal-SDD Research Team
-/

import FormalSDD.Trace

namespace FormalSDD

namespace LTL

  /-
    ## Linear Temporal Logic on Finite Traces (LTL_f)
    
    We define operators that lift State Predicates (`α → Prop`) 
    to Trace Predicates (`Trace α → Prop`).
  -/

  variable {α : Type}

  /--
    **Globally (Box) Operator: □P**
    
    The property `P` holds for **every** state in the execution trace.
    Used for **Safety** invariants (e.g., "Queue size never exceeds limit").
    
    Syntax: `LTL.always (λ s => s.val > 0) trace`
  -/
  def always (P : α → Prop) (τ : Trace α) : Prop :=
    ∀ s, s ∈ τ → P s

  /--
    **Eventually (Diamond) Operator: ◇P**
    
    The property `P` holds for **at least one** state in the execution trace.
    Used for **Liveness** properties (e.g., "A response is eventually received").
    
    Syntax: `LTL.eventually (λ s => s.is_committed) trace`
  -/
  def eventually (P : α → Prop) (τ : Trace α) : Prop :=
    ∃ s, s ∈ τ ∧ P s

  /--
    **Implication: P → Q**
    
    Standard logical implication lifted to traces. 
    If P holds for the trace, Q must also hold.
  -/
  def implies (P Q : Trace α → Prop) (τ : Trace α) : Prop :=
    P τ → Q τ

  /- 
    ## Helper Theorems for Proof Automation
    
    These theorems are often used by the `Synthesizer Agent` (via Lean's `simp` tactic)
    to break down complex verification goals into simpler sub-goals.
  -/

  /--
    Distributivity of `always` over conjunction.
    Prove `Safety1` AND `Safety2` independently.
  -/
  theorem always_and_distrib (P Q : α → Prop) (τ : Trace α) :
    always (λ s => P s ∧ Q s) τ ↔ always P τ ∧ always Q τ := by
    constructor
    . intro h
      constructor
      . intro s hs; exact (h s hs).left
      . intro s hs; exact (h s hs).right
    . intro h s hs
      exact ⟨h.left s hs, h.right s hs⟩

  /--
    Monotonicity of `eventually`.
    If P implies Q, and P happens, then Q happens.
  -/
  theorem eventually_mono (P Q : α → Prop) (h : ∀ s, P s → Q s) (τ : Trace α) :
    eventually P τ → eventually Q τ := by
    intro h_ev
    rcases h_ev with ⟨s, hs_in, hs_p⟩
    exists s
    exact ⟨hs_in, h s hs_p⟩

  /--
    Refinement mapping helper.
    Useful when proving property preservation across state transformations.
  -/
  def map_trace (f : α → α) (τ : Trace α) : Trace α :=
    τ.map f

  theorem always_map (P : α → Prop) (f : α → α) (τ : Trace α) :
    always P (map_trace f τ) ↔ always (P ∘ f) τ := by
    simp [always, map_trace]

end LTL

end FormalSDD