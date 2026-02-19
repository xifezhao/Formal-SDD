# Formal-SDD: Specification-Driven Development for Certified Synthesis

This repository contains the official implementation and experimental data for the paper **"Formal-SDD: Bridging Behavioral and Logical Specifications in Neuro-Symbolic Program Synthesis"**.

## 1. Introduction

**Formal-SDD** is a neuro-symbolic framework designed to bridge the semantic gap in AI-assisted code generation, effectively solving the reliability crisis of probabilistic "Vibe Coding" in high-assurance software.

* 
**Core Philosophy**: We model the software synthesis process not as a simple generative task, but as a stochastic transition system tightly constrained by a formal verification oracle.


* 
**The LMGPA Engine**: Utilizes Large Language Models (LLMs) as a Samplable Stochastic Kernel () to propose refinement steps, guided by the Lean 4 theorem prover.


* 
**Dual-Specification Architecture**: Automatically bridges developer-intuitive behavioral intent, expressed as Trace Specifications (), into machine-checkable Logical Specifications () via an embedding function ().



---

## 2. Repository Structure

```text
formal-sdd-experiment/
├── src/                    # Core source code for the LMGPA Engine
│   ├── lmgpa/              # Orchestrator, Agent logic, and Semantic Embedding
│   ├── verification/       # Lean 4 Verification Oracle interfaces & Feedback Parser
│   └── extraction/         # Correct-by-Extraction FFI compiler
├── lean_lib/               # Formally defined Lean 4 libraries (Trace, LTL, Concurrency)
├── data/concurbench_20/    # The 20 high-concurrency benchmarks used for evaluation
├── baselines/              # Baseline implementations (Zero-shot, TDD)
├── experiments/            # Experiment driver scripts, logs, and analysis tools
└── tests/                  # Unit tests and Property-Based Testing suites

```

---

## 3. Installation Guide

### Prerequisites

1. **Python 3.9+**
2. **Lean 4 & Elan**: Follow the [official Lean 4 installation guide](https://www.google.com/search?q=https://leanprover.github.io/lean4/doc/setup.html).
3. 
**Clang/GCC**: Required for compiling the native shared libraries during the extraction phase.



### Installation Steps

```bash
# Clone the repository
git clone https://github.com/your-username/formal-sdd-experiment.git
cd formal-sdd-experiment

# Install Python dependencies
pip install -r requirements.txt

# Initialize the Lean 4 project
cd lean_lib
lake exe cache get
lake build
cd ..

```

### API Key Configuration

Create a `.env` file in the root directory and configure your LLM API keys. The framework supports Gemini, Claude, and OpenAI models:

```text
GOOGLE_API_KEY=your_gemini_key_here
ANTHROPIC_API_KEY=your_claude_key_here
OPENAI_API_KEY=your_openai_key_here

# Set the default model for the LMGPA engine
DEFAULT_MODEL=gemini-2.5-flash

```

---

## 4. Reproducing Results (RQ1 & RQ2)

### 4.1 Running the Main Experiments

Use the following scripts to run specific benchmarks (e.g., `01_speculative_stream`) and compare our method against the baselines:

```bash
# Run Formal-SDD (Our Method)
python experiments/run_all.py --benchmark 01_speculative_stream --method formal-sdd

# Run Baseline 1 (Zero-shot / "Vibe Coding")
python experiments/run_all.py --benchmark 01_speculative_stream --method baseline-1

# Run Baseline 2 (Test-Driven Development)
python experiments/run_all.py --benchmark 01_speculative_stream --method baseline-2

```

### 4.2 Evaluating Correctness & Concurrency Safety

To detect subtle race conditions and validate functional correctness, run the property-based testing (PBT) and stress testing suite:

```bash
python experiments/evaluate_correctness.py --benchmark 01_speculative_stream --method baseline-1
python experiments/evaluate_correctness.py --benchmark 01_speculative_stream --method formal-sdd

```

---

## 5. Data Analysis & Visualization

### Generating the Convergence Plot (Figure 5)

Analyze the monotonic descent of the Semantic Potential () over refinement iterations:

```bash
python experiments/analysis/plot_convergence.py --benchmark 01_speculative_stream

```

*Generated plots will be saved in the `assets/figures/` directory.*

### Generating the Metrics Table (Table 1)

Aggregate the pass rates, safety violations, and estimated token costs across all benchmarks:

```bash
python experiments/analysis/calc_metrics.py

```

---

## 6. Core Theoretical Reference: The LMGPA Engine

The orchestrator (`src/lmgpa/orchestrator.py`) implements the neuro-symbolic refinement loop as a discrete-time stochastic state machine. The transition dynamics are governed by the Verification Oracle ():

1. 
**Map**: The system maps the high-level Trace Spec () to a low-level proof obligation: .


2. 
**Check**: The Lean 4 oracle evaluates the candidate program and proof: .


3. **Transition**:
* 
**Success ()**: If , the artifact is mathematically verified and extracted via FFI.


* 
**Tool Error ()**: If  (e.g., timeout, syntax error), a deterministic backoff or syntax repair strategy is triggered without consuming stochastic budget.


* 
**Logical Error ()**: If  (e.g., counter-example, unsolved goal), the agent executes a Stochastic Refinement Step, sampling a new candidate from the LLM conditioned on the structured feedback: .





---

## 7. Citation

If you find this code or our theoretical framework useful in your research, please cite our paper:

```bibtex
@inproceedings{formal_sdd_2026,
  title={Formal-SDD: Bridging Behavioral and Logical Specifications in Neuro-Symbolic Program Synthesis},
  author={Anonymous},
  booktitle={Proceedings of the ACM/SIGPLAN Conference},
  year={2026}
}

```

## 8. License

This project is licensed under the **Apache License 2.0**. See the `LICENSE` file for details.