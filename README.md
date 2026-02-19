

# Formal-SDD: Specification-Driven Development for Certified Synthesis

本仓库包含论文 **"Formal-SDD: Bridging Behavioral and Logical Specifications in Neuro-Symbolic Program Synthesis"** 的官方实验代码实现。

## 1. 项目简介

**Formal-SDD** 是一个神经符号（Neuro-Symbolic）框架，旨在解决大语言模型（LLM）在编写高可靠软件时的不确定性问题。

* **核心理念**：将代码生成视为一个受验证器约束的随机状态机。
* **LMGPA 引擎**：使用 LLM 作为可采样随机核 ()，在 Lean 4 定理证明器的引导下进行自动细化（Refinement）。
* **双重规格说明**：连接了开发者直觉的“迹规格 (Trace Spec)”与严谨的“逻辑规格 (Logical Spec)”。

---

## 2. 目录结构

```text
formal-sdd-experiment/
├── src/                    # 核心源代码 (LMGPA Engine)
│   ├── lmgpa/              # 编排器、Agent 逻辑与语义映射
│   ├── verification/       # Lean 4 验证 Oracle 接口
│   └── extraction/         # 正确提取 (FFI) 编译器
├── lean_lib/               # 形式化定义的 Lean 库 (Trace, LTL, Concurrency)
├── data/concurbench_20/    # 论文评估使用的 20 个高并发基准测试
├── baselines/              # 基线实现 (Zero-shot, TDD)
├── experiments/            # 实验驱动脚本、日志与分析工具
└── tests/                  # 项目单元测试

```

---

## 3. 安装指南

### 前置依赖

1. **Python 3.9+**
2. **Lean 4 & Elan**: [安装指南]()
3. **Clang/GCC**: 用于提取过程中的 FFI 编译。

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/your-repo/formal-sdd-experiment.git
cd formal-sdd-experiment

# 安装 Python 依赖
pip install -r requirements.txt

# 初始化 Lean 项目
cd lean_lib
lake exe cache get
lake build
cd ..

```

### 配置 API Key

在根目录下创建 `.env` 文件并填入您的模型密钥：

```text
ANTHROPIC_API_KEY=your_key_here
# 或者
OPENAI_API_KEY=your_key_here

```

---

## 4. 实验复现 (Reproducing Results)

### 4.1 运行主实验 (RQ1 & RQ2)

使用以下脚本运行特定的 Benchmark（例如 `01_speculative_stream`）：

```bash
# 运行 Formal-SDD (我们的方法)
python experiments/run_all.py --benchmark 01_speculative_stream --method formal-sdd

# 运行基线 (Zero-shot)
python experiments/run_all.py --benchmark 01_speculative_stream --method baseline-1

# 运行基线 (TDD)
python experiments/run_all.py --benchmark 01_speculative_stream --method baseline-2

```

### 4.2 验证正确性与并发性

对生成的结果进行基于属性的测试 (PBT) 和压力测试，以检测竞态条件：

```bash
python experiments/evaluate_correctness.py --benchmark 01_speculative_stream --method baseline-1
python experiments/evaluate_correctness.py --benchmark 01_speculative_stream --method formal-sdd

```

---

## 5. 可视化分析

### 生成收敛图 (Figure 5)

分析语义势能 () 随迭代次数的下降趋势：

```bash
python experiments/analysis/plot_convergence.py --benchmark 01_speculative_stream

```

生成的文件将保存在 `assets/figures/` 目录下。

### 生成指标对比表 (Table 1)

汇总所有 Benchmark 的通过率、违规数和成本：

```bash
python experiments/analysis/calc_metrics.py

```

---

## 6. 核心理论参考 (The LMGPA Engine)

在 `src/lmgpa/orchestrator.py` 中实现的状态机遵循以下转移逻辑：

---

## 7. 许可证

本项目采用 **Apache License 2.0**。详情请参阅 [LICENSE]() 文件。
