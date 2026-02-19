"""
experiments/run_all.py

Main Experiment Driver for Formal-SDD.

This script executes the evaluation pipeline described in Section 5 of the paper.
It supports running the proposed LMGPA method against the comparative baselines
on the ConcurBench-20 suite.

Usage:
    python experiments/run_all.py --benchmark 01_speculative_stream --method formal-sdd
    python experiments/run_all.py --benchmark 01_speculative_stream --method baseline-1

Arguments:
    --benchmark: ID of the benchmark problem (directory name in data/concurbench_20).
    --method: The synthesis approach to use ('formal-sdd', 'baseline-1', 'baseline-2').
    --model: The LLM backend (default: claude-3-5-sonnet).
    --max_steps: Maximum refinement iterations (default: 15).
"""

import argparse
import logging
import json
import time
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import LMGPA Components
from src.lmgpa.orchestrator import Orchestrator, LMGPAConfig
from src.lmgpa.agents.formalizer import FormalizerAgent
from src.lmgpa.agents.synthesizer import SynthesizerAgent
from src.lmgpa.agents.base import AgentConfig
from src.lmgpa.embedding.mapper import EmbeddingMapper
from src.verification.lean_runner import LeanVerifier
from src.extraction.compiler import NativeCompiler

# Import Baselines
from baselines.baseline_1_zeroshot import ZeroShotRunner
from baselines.baseline_2_tdd import TDDRunner

# Configuration Constants
DATA_DIR = Path("data/concurbench_20")
LOG_DIR = Path("experiments/logs")
RESULTS_DIR = Path("experiments/results")

def setup_logger(benchmark_id: str, method: str) -> logging.Logger:
    """Configures logging to both console and a timestamped file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{method}_{benchmark_id}_{timestamp}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file)
        ]
    )
    return logging.getLogger("ExperimentDriver")

def load_benchmark_intent(benchmark_id: str) -> str:
    """Reads the natural language prompt (I) from the data directory."""
    prompt_path = DATA_DIR / benchmark_id / "prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Benchmark prompt not found: {prompt_path}")
    
    with open(prompt_path, "r") as f:
        return f.read().strip()

def run_formal_sdd(args, logger):
    """Executes the LMGPA Engine (Ours)."""
    logger.info("--- Initializing Formal-SDD (LMGPA) Engine ---")
    
    # 1. Configure Components
    agent_config = AgentConfig(
        model_name=args.model,
        temperature=0.7
    )
    
    lmgpa_config = LMGPAConfig(
        max_refinement_steps=args.max_steps,
        model_name=args.model
    )

    # 2. Instantiate Agents & Tools
    formalizer = FormalizerAgent(agent_config)
    synthesizer = SynthesizerAgent(agent_config)
    mapper = EmbeddingMapper()
    verifier = LeanVerifier(project_root="lean_lib") # The trusted kernel
    
    # 3. Create Orchestrator
    orchestrator = Orchestrator(
        config=lmgpa_config,
        formalizer=formalizer,
        synthesizer=synthesizer,
        mapper=mapper,
        verifier=verifier
    )

    # 4. Load Data
    intent = load_benchmark_intent(args.benchmark)
    
    # 5. Run Execution Loop
    start_time = time.time()
    artifact = orchestrator.solve(intent)
    duration = time.time() - start_time

    # 6. Save Results & Metrics
    result_dir = RESULTS_DIR / args.benchmark / "formal_sdd"
    result_dir.mkdir(parents=True, exist_ok=True)
    
    # Save Metrics JSON (for plotting Figure 5)
    metrics_file = result_dir / "convergence_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(orchestrator.metrics.__dict__, f, indent=2)
    
    if artifact:
        logger.info(f"SUCCESS: Synthesis complete in {duration:.2f}s.")
        
        # Save Generated Source
        with open(result_dir / "solution.py", "w") as f:
            f.write(artifact.program_code)
        
        with open(result_dir / "proof.lean", "w") as f:
            f.write(artifact.proof_script)
            
        # Optional: Trigger Compilation (Extraction)
        logger.info("Triggering Native Compilation...")
        compiler = NativeCompiler(project_root="lean_lib", output_dir=str(result_dir))
        compiler.compile("Main") # Assumes artifact was injected into Main
        
    else:
        logger.error(f"FAILURE: Failed to converge within {args.max_steps} steps.")

def run_baseline_1(args, logger):
    """Executes Baseline 1: Zero-shot Direct Synthesis."""
    logger.info("--- Running Baseline 1: Zero-Shot ---")
    
    runner = ZeroShotRunner(output_dir=str(RESULTS_DIR))
    prompt_path = DATA_DIR / args.benchmark / "prompt.txt"
    
    start_time = time.time()
    runner.run_benchmark(args.benchmark, prompt_path)
    duration = time.time() - start_time
    
    logger.info(f"Baseline 1 finished in {duration:.2f}s")

def run_baseline_2(args, logger):
    """Executes Baseline 2: TDD (LLM + Unit Tests)."""
    logger.info("--- Running Baseline 2: TDD Loop ---")
    
    runner = TDDRunner(max_iterations=args.max_steps, output_dir=str(RESULTS_DIR))
    prompt_path = DATA_DIR / args.benchmark / "prompt.txt"
    # Note: TDD requires a test file to exist
    test_path = DATA_DIR / args.benchmark / "tests.py"
    
    if not test_path.exists():
        logger.error(f"Baseline 2 requires 'tests.py' in {DATA_DIR}/{args.benchmark}")
        return

    start_time = time.time()
    runner.run_benchmark(args.benchmark, prompt_path, test_path)
    duration = time.time() - start_time
    
    logger.info(f"Baseline 2 finished in {duration:.2f}s")

def main():
    parser = argparse.ArgumentParser(description="Formal-SDD Experiment Driver")
    
    parser.add_argument("--benchmark", type=str, required=True, 
                        help="Benchmark ID (e.g., 01_speculative_stream)")
    parser.add_argument("--method", type=str, required=True, 
                        choices=["formal-sdd", "baseline-1", "baseline-2"],
                        help="Synthesis method to evaluate")
    parser.add_argument("--model", type=str, default="claude-3-5-sonnet-20240620",
                        help="LLM Model ID")
    parser.add_argument("--max_steps", type=int, default=15,
                        help="Maximum refinement/TDD iterations")
    
    args = parser.parse_args()

    # 1. Setup Environment
    logger = setup_logger(args.benchmark, args.method)
    
    # 2. Dispatch
    try:
        if args.method == "formal-sdd":
            run_formal_sdd(args, logger)
        elif args.method == "baseline-1":
            run_baseline_1(args, logger)
        elif args.method == "baseline-2":
            run_baseline_2(args, logger)
            
    except KeyboardInterrupt:
        logger.warning("Experiment interrupted by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception during experiment: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()