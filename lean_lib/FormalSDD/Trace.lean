/-
Copyright (c) 2026 Formal-SDD Authors. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Formal-SDD Research Team
-/

namespace FormalSDD

/--
  ## Trace Semantics (Section 3.1)

  In the Formal-SDD framework, a **Trace** is modeled as a finite sequence of
  observable states produced by an execution. 
  
  While concurrent systems are often theoretically modeled as infinite streams, 
  for the purpose of *Bounded Model Checking* and synthesizing correct-by-construction 
  transitions in our LMGPA engine, we verify properties over finite prefixes 
  and prove invariance via induction.

  We define `Trace α` as a transparent alias for `List α`, where `α` is the 
  domain-specific State type (e.g., `StreamState`).
-/
def Trace (α : Type) := List α

namespace Trace

  variable {α : Type}

  /-- 
    The empty trace. Represents the system state before initialization 
    or any events have occurred.
  -/
  def empty : Trace α := []

  /-- 
    Construct a trace from a single state. 
    Useful for base cases in inductive proofs.
  -/
  def singleton (s : α) : Trace α := [s]

  /--
    Append a new state to the end of the trace (snoc).
    This models the discrete time transition: `trace_next = trace_curr ++ [new_state]`.
  -/
  def snoc (τ : Trace α) (s : α) : Trace α := τ ++ [s]

  /-- 
    Get the length of the trace (number of discrete time steps). 
  -/
  def length (τ : Trace α) : Nat := List.length τ

  /-- 
    Access the i-th state in the history.
    Returns `Option α` to handle out-of-bounds safely.
  -/
  def get? (τ : Trace α) (i : Nat) : Option α := List.get? τ i

  /-- 
    The current (most recent) state of the system.
    Most invariants (e.g., Safety) are checked against this state 
    relative to the history.
  -/
  def last? (τ : Trace α) : Option α := List.getLast? τ

  /-- 
    Predicate: Trace is not empty. 
    Many theorems require at least an initial state to hold.
  -/
  def nonEmpty (τ : Trace α) : Prop := τ ≠ []

  /--
    Trace inclusion predicate.
    `subtrace τ1 τ2` means τ1 is a prefix of τ2.
    Essential for proving monotonicity of history.
  -/
  def isPrefix (τ1 τ2 : Trace α) : Prop := List.isPrefix τ1 τ2

end Trace

end FormalSDD