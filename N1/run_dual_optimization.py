#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双频微带天线优化 - 运行脚本
目标: 1.65GHz + 6.5GHz, S11 < -15dB
混合决策, 最大6次迭代
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# 确保路径正确
sys.path.insert(0, str(Path(__file__).parent))

# ===== 关键修改：从 antenna_agent 导入，不再是 agent_main =====
from antenna_agent import DualBandAntennaAgent
from ai_brain import DecisionMode

# ===== 配置参数 =====
PROJECT_PATH = r"T:\AnsysPrj\HFSS-AI\dual_frequence_ai.aedt"
MATERIAL = "FR4"
TARGET_FREQ_LOW = 1.65      # GHz
TARGET_FREQ_HIGH = 6.5      # GHz
TARGET_S11 = -15             # dB
MAX_ITERATIONS = 6
DECISION_MODE = DecisionMode.HYBRID
LLM_URL = "http://localhost:1234/v1"
MODEL_NAME = "qwen2.5-coder-7b-instruct"
WORK_DIR = r"T:\HFSS_Agent_FR4_1.65_6.5GHz"

print("=" * 70)
print("🚀 双频微带天线优化启动")
print(f"   目标频率: {TARGET_FREQ_LOW} GHz / {TARGET_FREQ_HIGH} GHz")
print(f"   目标 S11: < {TARGET_S11} dB")
print(f"   决策模式: {DECISION_MODE.value}")
print(f"   最大迭代: {MAX_ITERATIONS}")
print(f"   HFSS项目: {PROJECT_PATH}")
print(f"   工作目录: {WORK_DIR}")
print("=" * 70)

# 检查项目文件是否存在
if not os.path.exists(PROJECT_PATH):
    print(f"❌ 项目文件不存在: {PROJECT_PATH}")
    sys.exit(1)

print(f"✅ 项目文件确认存在: {PROJECT_PATH}")

# 创建优化Agent
agent = DualBandAntennaAgent(
    material_name=MATERIAL,
    target_freqs=[TARGET_FREQ_LOW, TARGET_FREQ_HIGH],
    target_s11=TARGET_S11,
    max_iterations=MAX_ITERATIONS,
    decision_mode=DECISION_MODE,
    llm_url=LLM_URL,
    model_name=MODEL_NAME,
    work_dir=WORK_DIR,
    template_project=PROJECT_PATH,
    device_type="双频微带天线",
    freq_tolerance=0.01,  # ±10 MHz 频率精度
)

# 回调函数 - 记录迭代结果
def on_iteration(iteration, params, result):
    print(f"\n{'─' * 40}")
    print(f"[回调] 迭代 {iteration} 完成")

    bands = result.get('bands', {})
    low_band = bands.get(f"{TARGET_FREQ_LOW}GHz", {})
    high_band = bands.get(f"{TARGET_FREQ_HIGH}GHz", {})

    low_s11 = result.get('low_s11', 0)
    high_s11 = result.get('high_s11', 0)
    low_freq = low_band.get('frequency_at_min_ghz', 0)
    high_freq = high_band.get('frequency_at_min_ghz', 0)
    is_pass = result.get('is_pass', False)
    score = result.get('overall_score', 0)

    print(f"   低频: S11={low_s11:.2f}dB @ {low_freq:.4f}GHz (目标{low_s11<=TARGET_S11})")
    print(f"   高频: S11={high_s11:.2f}dB @ {high_freq:.4f}GHz (目标{high_s11<=TARGET_S11})")
    print(f"   得分: {score:.3f} | {'✅ 合格' if is_pass else '❌ 未达标'}")
    print(f"   L0={params.get('L0', 0):.2f}, W0={params.get('W0', 0):.2f}")
    print(f"   l1={params.get('l1', 0):.2f}, l2={params.get('l2', 0):.2f}")
    print(f"   Ls={params.get('Ls', 0):.1f}, Ws={params.get('Ws', 0):.1f}")

def on_best(iteration, params, result):
    print(f"  🏆 新最佳结果! (迭代 {iteration})")

def on_decision(decision):
    print(f"  🧠 [{decision.model_name}] {decision.strategy}")

agent.on_iteration = on_iteration
agent.on_best = on_best
agent.on_decision = on_decision

# 运行优化
print("\n" + "=" * 70)
print("开始优化循环...")
print("=" * 70)

final_result = agent.optimize()

# 输出最终结果
print("\n" + "=" * 70)
print("📊 优化完成 - 最终结果")
print("=" * 70)

if final_result.get('success'):
    best_params = final_result.get('best_params', {})
    best_result = final_result.get('best_result', {})

    bands = best_result.get('bands', {})
    low_band = bands.get(f"{TARGET_FREQ_LOW}GHz", {})
    high_band = bands.get(f"{TARGET_FREQ_HIGH}GHz", {})

    low_s11_final = best_result.get('low_s11', 0)
    high_s11_final = best_result.get('high_s11', 0)
    low_freq_final = low_band.get('frequency_at_min_ghz', 0)
    high_freq_final = high_band.get('frequency_at_min_ghz', 0)

    print(f"\n🏆 最佳结果 (迭代 {final_result.get('best_iteration', '?')}):")
    print(f"   低频 (目标 {TARGET_FREQ_LOW} GHz):")
    print(f"     S11 = {low_s11_final:.2f} dB {'✅' if low_s11_final <= TARGET_S11 else '❌'}")
    print(f"     频率 = {low_freq_final:.4f} GHz (偏差: {abs(low_freq_final - TARGET_FREQ_LOW)*1000:.1f} MHz)")
    print(f"   高频 (目标 {TARGET_FREQ_HIGH} GHz):")
    print(f"     S11 = {high_s11_final:.2f} dB {'✅' if high_s11_final <= TARGET_S11 else '❌'}")
    print(f"     频率 = {high_freq_final:.4f} GHz (偏差: {abs(high_freq_final - TARGET_FREQ_HIGH)*1000:.1f} MHz)")

    print(f"\n📐 最优参数:")
    for k, v in best_params.items():
        if k in ['Ls', 'Ws']:
            print(f"   {k} = {v:.1f} mm")
        elif k == 'H':
            print(f"   {k} = {v:.1f} mm")
        else:
            print(f"   {k} = {v:.2f} mm")

    print(f"\n📊 是否达标: {'✅ 是' if best_result.get('is_pass') else '❌ 否'}")
    print(f"📊 综合得分: {best_result.get('overall_score', 0):.3f}")
    print(f"📊 总迭代次数: {final_result.get('iterations', 0)}")
else:
    print("\n❌ 优化未产生有效结果")

print("\n完成！")