#!/usr/bin/env python3
"""
分析实验结果并生成收敛图表

根据论文 Section 5 的描述，生成以下可视化：
1. 细化步数的收敛曲线
2. 验证尝试次数的比较
3. 总体成功率
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

def load_results():
    """加载所有实验结果"""
    results_dir = Path("experiments/results")
    results = []
    
    for json_file in results_dir.glob("*.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            results.append(json.load(f))
    
    return results

def plot_convergence_trace(result):
    """
    绘制单个实验的细化收敛曲线
    对应论文中的 Figure 5: Convergence Trace
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 提取细化轨迹数据
    steps = []
    timestamps = []
    actions = []
    
    for step in result['refinement_trace']:
        steps.append(step['step_number'])
        timestamps.append(step['timestamp'])
        actions.append(step['action'])
    
    # 图1: 累积时间消耗
    ax1.plot(steps, timestamps, marker='o', linewidth=2, markersize=8, color='#2E86AB')
    ax1.fill_between(steps, 0, timestamps, alpha=0.3, color='#2E86AB')
    ax1.set_xlabel('细化步数', fontsize=12)
    ax1.set_ylabel('累积时间 (秒)', fontsize=12)
    ax1.set_title(f'LMGPA 收敛曲线 - {result["benchmark_id"]}', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # 标注关键事件
    for i, (step, ts, action) in enumerate(zip(steps, timestamps, actions)):
        if action == "formalize":
            ax1.annotate('形式化', xy=(step, ts), xytext=(step+0.3, ts+0.2),
                        arrowprops=dict(arrowstyle='->', color='green', lw=1.5),
                        fontsize=9, color='green')
        elif result['refinement_trace'][i].get('verification_result'):
            if '✓' in str(result['refinement_trace'][i]['verification_result']):
                ax1.annotate('验证通过', xy=(step, ts), xytext=(step+0.3, ts+0.3),
                            arrowprops=dict(arrowstyle='->', color='darkgreen', lw=1.5),
                            fontsize=9, color='darkgreen', weight='bold')
    
    # 图2: 验证尝试分布
    verify_steps = [s for s, a in zip(steps, actions) if 'verify' in a]
    verify_times = [t for s, t, a in zip(steps, timestamps, actions) if 'verify' in a]
    
    if verify_times:
        # 计算每次验证的增量时间
        verify_durations = [verify_times[0]] + [verify_times[i] - verify_times[i-1] 
                                                 for i in range(1, len(verify_times))]
        
        colors = ['#FF6B6B' if i < len(verify_steps)-1 else '#4ECDC4' for i in range(len(verify_steps))]
        bars = ax2.bar(range(1, len(verify_steps)+1), verify_durations, color=colors, edgecolor='black', linewidth=1.5)
        
        ax2.set_xlabel('验证尝试次数', fontsize=12)
        ax2.set_ylabel('验证耗时 (秒)', fontsize=12)
        ax2.set_title('验证Oracle调用分析', fontsize=14, fontweight='bold')
        ax2.grid(True, axis='y', alpha=0.3)
        
        # 添加图例
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#FF6B6B', edgecolor='black', label='失败尝试'),
            Patch(facecolor='#4ECDC4', edgecolor='black', label='成功验证')
        ]
        ax2.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    
    # 保存图表
    output_dir = Path("experiments/analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"convergence_{result['benchmark_id']}_{timestamp}.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"📊 收敛图表已保存: {output_file}")
    
    plt.show()

def generate_summary_report(results):
    """生成实验总结报告"""
    print("\n" + "="*80)
    print("实验结果总结报告")
    print("="*80)
    
    total_experiments = len(results)
    successful = sum(1 for r in results if r['success'])
    
    print(f"\n总实验次数: {total_experiments}")
    print(f"成功次数: {successful}")
    print(f"成功率: {successful/total_experiments*100:.1f}%")
    
    print("\n细化步数统计:")
    refinement_steps = [r['num_refinement_steps'] for r in results]
    print(f"  平均: {np.mean(refinement_steps):.2f} 步")
    print(f"  中位数: {np.median(refinement_steps):.0f} 步")
    print(f"  范围: {min(refinement_steps)} - {max(refinement_steps)} 步")
    
    print("\n验证尝试次数统计:")
    verification_attempts = [r['verification_attempts'] for r in results]
    print(f"  平均: {np.mean(verification_attempts):.2f} 次")
    print(f"  总计: {sum(verification_attempts)} 次")
    
    print("\n总耗时统计:")
    total_times = [r['total_time'] for r in results]
    print(f"  平均: {np.mean(total_times):.2f} 秒")
    print(f"  总计: {sum(total_times):.2f} 秒")
    
    print("\n各基准测试详细结果:")
    print("-"*80)
    print(f"{'基准ID':<25} {'方法':<15} {'成功':<8} {'步数':<8} {'时间(s)':<10}")
    print("-"*80)
    
    for r in results:
        success_mark = "✓" if r['success'] else "✗"
        print(f"{r['benchmark_id']:<25} {r['method']:<15} {success_mark:<8} "
              f"{r['num_refinement_steps']:<8} {r['total_time']:<10.2f}")
    
    print("="*80)

def main():
    """主函数"""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  Formal-SDD 实验结果分析                                      ║
    ║  生成论文中的图表和统计数据                                    ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 加载结果
    results = load_results()
    
    if not results:
        print("⚠️  未找到实验结果文件，请先运行实验。")
        return
    
    print(f"✓ 加载了 {len(results)} 个实验结果\n")
    
    # 生成总结报告
    generate_summary_report(results)
    
    # 为每个结果生成收敛图
    print("\n生成收敛曲线图表...")
    for result in results:
        plot_convergence_trace(result)

if __name__ == "__main__":
    main()
