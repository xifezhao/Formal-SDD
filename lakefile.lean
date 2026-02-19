/-
  lakefile.lean

  The Trusted Kernel Configuration for Formal-SDD.
  
  This file defines the build system and environment for the Lean 4 
  Verification Oracle (V). It ensures that the LMGPA engine has 
  access to the necessary semantic libraries (Trace, LTL, Concurrency)
  during the synthesis loop.
-/

import Lake
open Lake DSL

package «formal-sdd-lib» where
  -- Settings applied to both the library and executables
  leanOptions := #[
    ⟨`pp.unicode.fun, true⟩, -- Use unicode arrows
    ⟨`autoImplicit, false⟩  -- Force explicit variable declaration for rigor
  ]

/--
  The core Formal-SDD library containing semantic domains.
  These modules are the "Truth Source" that the LLM cannot modify.
-/
@[default_target]
lean_lib «FormalSDD» where
  srcDir := "."
  roots := #[`FormalSDD.Trace, `FormalSDD.LTL, `FormalSDD.Concurrency]

/--
  The Main module acts as a scratchpad for the LMGPA Orchestrator.
  The verifier dynamically injects candidate code (p) and proofs (pi) 
  into this module and attempts to build it.
-/
lean_lib «Main» where
  srcDir := "FormalSDD"
  roots := #[`Main]

/--
  External dependencies. 
  'std' provides essential data structures and tactics.
-/
require std from git "https://github.com/leanprover/std4" @ "main"

/--
  Target for the Extraction Compiler (Section 4.3).
  Enables the generation of shared libraries (.so / .dylib) 
  for Python FFI integration.
-/
target ffi_export pkg : FilePath := do
  let oFile := pkg.buildDir / "native" / "formal_sdd_ffi.o"
  let srcJob ← lean_lib.build «Main»
  -- This custom target helps the compiler.py script locate 
  -- the object files for final linking.
  return srcJob