#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天线优化 AI Agent
支持单频天线和双频天线优化
与 tline_agent.py 平级，共享 ai_brain、hfss_controller 等模块
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from ai_brain import AIBrain, DecisionMode
from hfss_controller import HFSSController
from s_param_analyzer import SParamAnalyzer
from antenna_knowledge_base import (
    AntennaKnowledgeBase,
    DualBandAntennaKnowledgeBase,
    MATERIAL_LIBRARY,
    SubstrateMaterial
)


class AntennaAgent:
    """
    单频天线优化 Agent

    使用方式:
        agent = AntennaAgent(
            material_name="FR4",
            target_freq=2.45,
            target_s11=-15,
            max_iterations=15,
            decision_mode=DecisionMode.LLM_ONLY,
            template_project="T:/AnsysPrj/AI-Patch.aedt",
            device_type="微带贴片天线"
        )
        result = agent.optimize()
    """

    def __init__(self,
                 material_name: str = "FR4",
                 target_freq: float = 2.45,
                 target_s11: float = -15,
                 max_iterations: int = 15,
                 decision_mode: DecisionMode = DecisionMode.LLM_ONLY,
                 llm_url: str = "http://localhost:1234/v1",
                 model_name: str = "qwen2.5-coder-7b-instruct",
                 llm_service: str = "llm_studio",
                 api_key: str = None,
                 work_dir: str = None,
                 template_project: str = None,
                 device_type: str = "微带贴片天线",
                 freq_tolerance: float = 0.01):
        """
        初始化单频天线优化 Agent

        Args:
            material_name: 介质材料名称 (FR4, RO4350B, RO4003C, RT5880)
            target_freq: 目标频率 (GHz)
            target_s11: 目标 S11 阈值 (dB)
            max_iterations: 最大迭代次数
            decision_mode: 决策模式 (DecisionMode)
            llm_url: LLM API 地址
            model_name: 模型名称
            llm_service: LLM 服务类型 (llm_studio, deepseek_api, ollama)
            api_key: API 密钥 (DeepSeek 需要)
            work_dir: 工作目录
            template_project: HFSS 模板项目路径
            device_type: 器件类型
            freq_tolerance: 频率容差 (GHz)
        """
        # 设置工作目录
        if work_dir is None:
            work_dir = f"T:/HFSS_Agent_{material_name}_{target_freq}GHz"
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # 保存配置
        self.material = MATERIAL_LIBRARY.get(material_name, MATERIAL_LIBRARY["FR4"])
        self.material_name = material_name
        self.target_freq = target_freq
        self.target_s11 = target_s11
        self.max_iterations = max_iterations
        self.model_name = model_name
        self.llm_service = llm_service
        self.api_key = api_key
        self.device_type = device_type
        self.freq_tolerance = freq_tolerance

        # 初始化知识库
        self.kb = AntennaKnowledgeBase(self.material, target_freq)
        initial_params = self.kb.get_initial_guess()

        # 初始化 HFSS 控制器
        self.controller = HFSSController(
            work_dir=str(self.work_dir),
            template_project=template_project,
            target_freq=target_freq,
            device_type=device_type
        )

        # 初始化分析器
        self.analyzer = SParamAnalyzer(
            lm_studio_url=llm_url.replace("/v1", ""),
            enable_llm=True
        )

        # 初始化 AI 大脑
        self.brain = AIBrain(
            knowledge_base=self.kb,
            mode=decision_mode,
            api_url=llm_url,
            model_name=model_name,
            target_s11=target_s11,
            llm_service=llm_service,
            api_key=api_key,
        )

        # 状态变量
        self.current_params = initial_params
        self.iteration = 0
        self.history = []
        self.best_result = None
        self.best_params = None
        self.best_score = -float('inf')
        self._stop_flag = False

        # 回调函数 (供 GUI 使用)
        self.on_iteration = None
        self.on_best = None
        self.on_decision = None

        print("=" * 60)
        print(f"📡 天线优化 Agent (单频)")
        print(f"   器件类型: {device_type}")
        print(f"   材料: {material_name}")
        print(f"   目标: {target_freq} GHz, S11 < {target_s11} dB")
        print(f"   LLM: {llm_service} / {model_name}")
        print("=" * 60)

    def stop(self):
        """停止优化"""
        self._stop_flag = True

    def optimize(self) -> Dict[str, Any]:
        """执行优化循环"""
        for self.iteration in range(1, self.max_iterations + 1):
            if self._stop_flag:
                break

            print(f"\n{'─' * 40}")
            print(f"📍 迭代 {self.iteration}/{self.max_iterations}")

            # 1. 运行仿真
            sim_result = self.controller.run_simulation(self.current_params)

            if not sim_result['success']:
                print(f"  ❌ 仿真失败: {sim_result.get('error')}")
                continue

            # 2. 分析结果
            analysis = self.analyzer.analyze(
                sim_result['csv_path'],
                use_ai=True,
                threshold_db=self.target_s11
            )

            s11 = analysis.get('s11_min_db', 0)
            freq = analysis.get('frequency_at_min_ghz', 0)
            is_pass = analysis.get('is_pass', False)

            # 3. 计算得分
            score = self._calculate_score(s11, freq)

            print(f"  📊 S11: {s11:.2f} dB @ {freq:.4f} GHz")
            print(f"  📊 得分: {score:.3f}, {'✅ 合格' if is_pass else '❌ 未达标'}")

            # 4. 更新最佳
            if score > self.best_score:
                self.best_score = score
                self.best_result = analysis
                self.best_params = self.current_params.copy()
                print(f"  🏆 新最佳! 得分={score:.3f}")
                if self.on_best:
                    self.on_best(self.iteration, self.best_params, self.best_result)

            # 5. 回调
            if self.on_iteration:
                self.on_iteration(self.iteration, self.current_params, analysis)

            # 6. 检查是否达标
            freq_ok = abs(freq - self.target_freq) <= self.freq_tolerance
            s11_ok = s11 <= self.target_s11

            if freq_ok and s11_ok:
                print(f"\n🎉 天线优化成功！S11={s11:.2f}dB @ {freq:.4f}GHz")
                break

            # 7. AI 决策
            decision = self.brain.decide(self.current_params, analysis, self.iteration)

            if self.on_decision:
                self.on_decision(decision)

            print(f"  🧠 [{decision.model_name}] {decision.strategy}")
            self.current_params = decision.new_params.copy()

            if decision.should_stop:
                break

        return self._finalize()

    def _calculate_score(self, s11: float, freq: float) -> float:
        """计算综合得分"""
        score = 0.0
        if s11:
            score += 0.7 * max(0, min(1, (s11 - self.target_s11) / (-20 - self.target_s11)))
        if freq:
            freq_score = 1 - min(1, abs(freq - self.target_freq) / 0.5)
            score += 0.3 * max(0, freq_score)
        return score

    def _finalize(self) -> Dict[str, Any]:
        """生成最终结果"""
        print(f"\n{'=' * 60}")
        print(f"📝 天线优化完成 [{self.model_name}]")

        if self.best_result:
            print(f"\n🏆 最佳结果:")
            print(f"   S11: {self.best_result.get('s11_min_db')} dB")
            print(f"   频率: {self.best_result.get('frequency_at_min_ghz')} GHz")

        final = {
            'success': self.best_result is not None,
            'best_score': self.best_score,
            'best_params': self.best_params,
            'best_result': self.best_result,
            'iterations': self.iteration,
            'stats': self.brain.get_stats() if hasattr(self.brain, 'get_stats') else {}
        }

        # 保存结果
        path = self.work_dir / "final_result.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(final, f, indent=2, default=str)

        print(f"\n📁 结果已保存: {path}")
        return final


class DualBandAntennaAgent:
    """
    双频天线优化 Agent

    使用方式:
        agent = DualBandAntennaAgent(
            material_name="FR4",
            target_freqs=[2.45, 5.0],
            target_s11=-15,
            max_iterations=30,
            decision_mode=DecisionMode.HYBRID,
            template_project="T:/AnsysPrj/dual_frequence_ai.aedt",
            device_type="双频微带天线"
        )
        result = agent.optimize()
    """

    def __init__(self,
                 material_name: str = "FR4",
                 target_freqs: List[float] = None,
                 target_s11: float = -15,
                 max_iterations: int = 30,
                 decision_mode: DecisionMode = DecisionMode.LLM_ONLY,
                 llm_url: str = "http://localhost:1234/v1",
                 model_name: str = "qwen2.5-coder-7b-instruct",
                 llm_service: str = "llm_studio",
                 api_key: str = None,
                 work_dir: str = None,
                 template_project: str = None,
                 device_type: str = "双频微带天线",
                 freq_tolerance: float = 0.01):
        """
        初始化双频天线优化 Agent

        Args:
            material_name: 介质材料名称
            target_freqs: [低频, 高频] 列表 (GHz)
            target_s11: 目标 S11 阈值 (dB)
            max_iterations: 最大迭代次数
            decision_mode: 决策模式
            llm_url: LLM API 地址
            model_name: 模型名称
            llm_service: LLM 服务类型
            api_key: API 密钥
            work_dir: 工作目录
            template_project: HFSS 模板项目路径
            device_type: 器件类型
            freq_tolerance: 频率容差 (GHz)
        """
        if target_freqs is None:
            target_freqs = [2.45, 5.0]

        self.target_freq_low = target_freqs[0]
        self.target_freq_high = target_freqs[1]

        if work_dir is None:
            work_dir = f"T:/HFSS_Agent_{material_name}_{self.target_freq_low}_{self.target_freq_high}GHz"
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # 保存配置
        self.material = MATERIAL_LIBRARY.get(material_name, MATERIAL_LIBRARY["FR4"])
        self.material_name = material_name
        self.target_freqs = target_freqs
        self.target_s11 = target_s11
        self.max_iterations = max_iterations
        self.model_name = model_name
        self.llm_service = llm_service
        self.api_key = api_key
        self.device_type = device_type
        self.freq_tolerance = freq_tolerance

        # 初始化双频知识库
        self.kb = DualBandAntennaKnowledgeBase(self.material, target_freqs)
        initial_params = self.kb.get_initial_guess()

        # 初始化 HFSS 控制器
        self.controller = HFSSController(
            work_dir=str(self.work_dir),
            template_project=template_project,
            target_freq=target_freqs[0],
            device_type=device_type
        )

        # 初始化分析器
        self.analyzer = SParamAnalyzer(
            lm_studio_url=llm_url.replace("/v1", ""),
            enable_llm=True
        )

        # 初始化 AI 大脑 (标记为双频)
        self.brain = AIBrain(
            knowledge_base=self.kb,
            mode=decision_mode,
            api_url=llm_url,
            model_name=model_name,
            target_s11=target_s11,
            llm_service=llm_service,
            api_key=api_key,
        )
        self.brain.is_dual = True

        # 状态变量
        self.current_params = initial_params
        self.iteration = 0
        self.history = []
        self.best_result = None
        self.best_params = None
        self.best_score = -float('inf')
        self._stop_flag = False

        # 回调函数
        self.on_iteration = None
        self.on_best = None
        self.on_decision = None

        print("=" * 60)
        print(f"📡 天线优化 Agent (双频)")
        print(f"   器件类型: {device_type}")
        print(f"   材料: {material_name}")
        print(f"   目标: {target_freqs[0]}GHz / {target_freqs[1]}GHz")
        print(f"   S11 < {target_s11} dB")
        print(f"   LLM: {llm_service} / {model_name}")
        print("=" * 60)

    def stop(self):
        """停止优化"""
        self._stop_flag = True

    def optimize(self) -> Dict[str, Any]:
        """执行双频优化循环"""
        for self.iteration in range(1, self.max_iterations + 1):
            if self._stop_flag:
                break

            print(f"\n{'─' * 40}")
            print(f"📍 迭代 {self.iteration}/{self.max_iterations}")

            # 1. 运行仿真 (传递双频频点)
            sim_result = self.controller.run_simulation(
                self.current_params,
                target_freqs=self.target_freqs
            )

            if not sim_result['success']:
                print(f"  ❌ 仿真失败: {sim_result.get('error')}")
                continue

            # 2. 多频分析
            target_freqs_dict = {
                f"{self.target_freq_low}GHz": self.target_freq_low,
                f"{self.target_freq_high}GHz": self.target_freq_high
            }

            analysis = self.analyzer.analyze_multi_freq(
                sim_result['csv_path'],
                target_freqs_dict,
                threshold_db=self.target_s11,
                use_ai=True
            )

            # 3. 提取结果
            low_band = analysis['bands'].get(f"{self.target_freq_low}GHz", {})
            high_band = analysis['bands'].get(f"{self.target_freq_high}GHz", {})

            low_s11 = low_band.get('s11_at_target', 0)
            high_s11 = high_band.get('s11_at_target', 0)
            low_freq = low_band.get('frequency_at_min_ghz', 0)
            high_freq = high_band.get('frequency_at_min_ghz', 0)
            is_pass = analysis.get('is_pass', False)
            score = analysis.get('overall_score', 0)

            # 计算频率误差 (MHz)
            low_freq_error = (low_freq - self.target_freq_low) * 1000 if low_freq else 0
            high_freq_error = (high_freq - self.target_freq_high) * 1000 if high_freq else 0

            # 补充分析结果
            analysis['low_s11'] = low_s11
            analysis['high_s11'] = high_s11
            analysis['low_freq_error'] = low_freq_error
            analysis['high_freq_error'] = high_freq_error
            analysis['low_actual_freq'] = low_freq
            analysis['high_actual_freq'] = high_freq

            print(f"  📊 低频: S11={low_s11:.2f}dB @ {low_freq:.4f}GHz")
            print(f"  📊 高频: S11={high_s11:.2f}dB @ {high_freq:.4f}GHz")
            print(f"  📊 得分: {score:.3f}, {'✅ 合格' if is_pass else '❌ 未达标'}")

            # 4. 更新最佳
            if score > self.best_score:
                self.best_score = score
                self.best_result = analysis
                self.best_params = self.current_params.copy()
                print(f"  🏆 新最佳! 得分={score:.3f}")
                if self.on_best:
                    self.on_best(self.iteration, self.best_params, self.best_result)

            # 5. 回调
            if self.on_iteration:
                self.on_iteration(self.iteration, self.current_params, analysis)

            # 6. 检查是否达标
            low_freq_ok = abs(low_freq_error) <= 20  # 20MHz
            high_freq_ok = abs(high_freq_error) <= 20
            low_s11_ok = low_s11 <= self.target_s11
            high_s11_ok = high_s11 <= self.target_s11

            if low_freq_ok and high_freq_ok and low_s11_ok and high_s11_ok:
                print(f"\n🎉 双频天线优化成功！")
                print(f"   低频: S11={low_s11:.2f}dB @ {low_freq:.4f}GHz")
                print(f"   高频: S11={high_s11:.2f}dB @ {high_freq:.4f}GHz")
                break

            # 7. AI 决策
            decision = self.brain.decide(self.current_params, analysis, self.iteration)

            if self.on_decision:
                self.on_decision(decision)

            print(f"  🧠 [{decision.model_name}] {decision.strategy}")
            self.current_params = decision.new_params.copy()

            if decision.should_stop:
                break

        return self._finalize()

    def _finalize(self) -> Dict[str, Any]:
        """生成最终结果"""
        print(f"\n{'=' * 60}")
        print(f"📝 双频天线优化完成 [{self.model_name}]")

        if self.best_result:
            print(f"\n🏆 最佳结果:")
            print(f"   低频 S11: {self.best_result.get('low_s11')} dB")
            print(f"   高频 S11: {self.best_result.get('high_s11')} dB")

        final = {
            'success': self.best_result is not None,
            'best_score': self.best_score,
            'best_params': self.best_params,
            'best_result': self.best_result,
            'iterations': self.iteration,
            'stats': self.brain.get_stats() if hasattr(self.brain, 'get_stats') else {}
        }

        # 保存结果
        path = self.work_dir / "final_result.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(final, f, indent=2, default=str)

        print(f"\n📁 结果已保存: {path}")
        return final