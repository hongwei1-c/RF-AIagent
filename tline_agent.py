#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传输线优化 AI Agent
"""

import json
import math
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from tline_controller import TLineController
from tline_analyzer import TLineAnalyzer, TLineAnalysisResult
from ai_brain import AIBrain, DecisionMode


class TLineAgent:
    """传输线优化 AI Agent"""

    def __init__(self,
                 tline_type: str = "微带线",
                 target_freq: float = 5.0,
                 target_s11: float = -15,
                 target_impedance: float = 50.0,
                 max_iterations: int = 15,
                 decision_mode: DecisionMode = DecisionMode.LLM_ONLY,
                 llm_url: str = "http://localhost:1234/v1",
                 model_name: str = "deepseek-v4-pro",
                 llm_service: str = "llm_studio",
                 api_key: str = None,
                 work_dir: str = None,
                 template_project: str = None):

        if work_dir is None:
            work_dir = f"T:/TLine_Agent_{tline_type}_{target_freq}GHz"
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.target_freq = target_freq
        self.target_s11 = target_s11
        self.target_impedance = target_impedance
        self.max_iterations = max_iterations
        self.model_name = model_name
        self.llm_service = llm_service
        self.api_key = api_key

        self.controller = TLineController(
            work_dir=str(self.work_dir / "tline_runs"),
            template_project=template_project,
            tline_type=tline_type,
            target_freq=target_freq
        )

        self.analyzer = TLineAnalyzer(target_impedance=target_impedance)

        from antenna_knowledge_base import AntennaKnowledgeBase
        self.kb = AntennaKnowledgeBase(target_freq_ghz=target_freq)

        self.brain = AIBrain(
            knowledge_base=self.kb,
            mode=decision_mode,
            api_url=llm_url,
            model_name=model_name,
            target_s11=target_s11,
            llm_service=llm_service,
            api_key=api_key,
        )

        self.current_params = self.controller.get_default_params()
        self.iteration = 0
        self.history = []
        self.best_result = None
        self.best_params = None
        self.best_score = 0
        self._stop_flag = False

        print("=" * 60)
        print("🔌 WHYAVE-AI PCB传输线优化系统")
        print(f"   传输线类型: {tline_type}")
        print(f"   目标频率: {target_freq} GHz")
        print(f"   目标S11: < {target_s11} dB")
        print(f"   目标阻抗: {target_impedance} Ω")
        print("=" * 60)

    def optimize(self) -> Dict[str, Any]:
        """执行优化"""
        for self.iteration in range(1, self.max_iterations + 1):
            if self._stop_flag:
                break

            print(f"\n{'─' * 40}")
            print(f"📍 迭代 {self.iteration}/{self.max_iterations}")

            sim_result = self.controller.run_simulation(self.current_params)

            if not sim_result['success']:
                print(f"  ❌ 仿真失败: {sim_result.get('error')}")
                continue

            analysis = self.analyzer.analyze(
                s_params_csv=sim_result.get('csv_s_params'),
                tdr_csv=sim_result.get('csv_tdr'),
                threshold_db=self.target_s11
            )

            s11 = analysis.s11_min_db or 0
            imp = analysis.characteristic_impedance or 0
            is_pass = analysis.is_pass

            score = 0
            if s11:
                score += 0.6 * max(0, min(1, (s11 - self.target_s11) / (-20 - self.target_s11)))
            if imp:
                imp_score = 1 - abs(imp - self.target_impedance) / self.target_impedance
                score += 0.4 * max(0, min(1, imp_score))

            print(f"  📊 S11: {s11:.2f} dB, 阻抗: {imp:.2f} Ω")
            print(f"  📊 得分: {score:.3f}, {'✅ 合格' if is_pass else '❌ 未达标'}")

            if score > self.best_score:
                self.best_score = score
                self.best_result = analysis
                self.best_params = self.current_params.copy()
                print(f"  🏆 新最佳! 得分={score:.3f}")

            if is_pass:
                print(f"\n🎉 传输线优化成功！S11={s11:.2f}dB, 阻抗={imp:.1f}Ω")
                break

            # AI决策
            decision_input = {
                's11_min_db': s11,
                'frequency_at_min_ghz': analysis.s11_freq_ghz or self.target_freq,
                'bandwidth_under_10db_ghz': analysis.bandwidth_10db_ghz or 0,
                'is_pass': is_pass
            }

            decision = self.brain.decide(self.current_params, decision_input, self.iteration)
            print(f"  🧠 [{decision.model_name}] {decision.strategy}")

            self.current_params = decision.new_params.copy()

        return self._finalize()

    def stop(self):
        self._stop_flag = True

    def _finalize(self) -> Dict[str, Any]:
        print(f"\n{'=' * 60}")
        print(f"📝 传输线优化完成 [{self.model_name}]")

        if self.best_result:
            print(f"\n🏆 最佳结果:")
            print(f"   S11: {self.best_result.s11_min_db} dB")
            print(f"   阻抗: {self.best_result.characteristic_impedance:.1f} Ω")

        final = {
            'success': self.best_result is not None,
            'best_score': self.best_score,
            'best_params': self.best_params,
            'best_s11': self.best_result.s11_min_db if self.best_result else None,
            'best_impedance': self.best_result.characteristic_impedance if self.best_result else None,
            'iterations': self.iteration,
        }

        path = self.work_dir / f"final_tline_result.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(final, f, indent=2)

        print(f"\n📁 结果: {path}")
        return final