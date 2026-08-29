#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 决策模块
支持单频和双频天线优化
支持多种 LLM 服务：LLM Studio、DeepSeek API、Ollama
参数优先级正确体现
"""

import json
import math
import random
import re
import requests
import os
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum


class DecisionMode(Enum):
    """决策模式"""
    RULE_ONLY = "rule_only"
    LLM_ONLY = "llm_only"
    RULE_FIRST_LLM_FALLBACK = "rule_first"
    LLM_FIRST_RULE_FALLBACK = "llm_first"
    HYBRID = "hybrid"


class LLMServiceType(Enum):
    """LLM 服务类型"""
    LLM_STUDIO = "llm_studio"  # 本地 LLM Studio
    DEEPSEEK_API = "deepseek_api"  # DeepSeek API (需要密钥)
    OLLAMA = "ollama"  # Ollama 本地服务


@dataclass
class OptimizationDecision:
    """优化决策结果"""
    analysis: str
    strategy: str
    new_params: Dict[str, float]
    expected_effect: str
    confidence: float
    should_stop: bool
    decision_source: str
    model_name: str = ""


class AIBrain:
    """AI 决策大脑 - 支持多种 LLM 服务"""

    TUNABLE_PARAMS = ['l', 'w', 'w0', 'l0', 'w1', 'd1', 'w2', 'd2']

    FALLBACK_PARAMS = {
        'low': {'l': 90, 'w': 100, 'w0': 180.0, 'l0': 200.0, 'w1': 3.0, 'd1': 28.0, 'w2': 1.2, 'd2': 18.0, 'h': 1.6},
        'mid': {'l': 18.0, 'w': 21.5, 'w0': 36.0, 'l0': 43.0, 'w1': 3.0, 'd1': 14.0, 'w2': 0.6, 'd2': 8.5, 'h': 1.6},
        'high': {'l': 10.0, 'w': 12.0, 'w0': 25.0, 'l0': 30.0, 'w1': 2.5, 'd1': 10.0, 'w2': 0.4, 'd2': 5.0, 'h': 1.6},
    }

    EXPANDED_BOUNDS = {
        'l': (3.0, 150.0), 'w': (5.0, 150.0),
        'w0': (15.0, 300.0), 'l0': (20.0, 300.0),
        'w1': (0.3, 10.0), 'd1': (5.0, 100.0),
        'w2': (0.1, 8.0), 'd2': (2.0, 80.0),
    }

    # DeepSeek 模型映射
    DEEPSEEK_MODEL_MAP = {
        "deepseek-v4-pro": "deepseek-v4-pro",
        "deepseek-chat": "deepseek-v4-pro",
        "deepseek-reasoner": "deepseek-v4-pro",
    }

    def __init__(self,
                 knowledge_base,
                 mode: DecisionMode = DecisionMode.RULE_FIRST_LLM_FALLBACK,
                 api_url: str = "http://localhost:1234/v1",
                 model_name: str = "qwen2.5-coder-7b-instruct",
                 target_s11: float = -15,
                 llm_timeout: int = 60,
                 llm_service: str = "llm_studio",
                 api_key: str = None):

        self.kb = knowledge_base
        self.mode = mode
        self.api_url = api_url
        self.model_name = model_name
        self.target_s11 = target_s11
        self.llm_timeout = llm_timeout
        self.llm_service = llm_service
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")

        # 判断是否为双频知识库
        self.is_dual = hasattr(knowledge_base, 'target_freq_low')

        if self.is_dual:
            self.target_freq_low = knowledge_base.target_freq_low
            self.target_freq_high = knowledge_base.target_freq_high
            self.target_freq = self.target_freq_low
        else:
            self.target_freq = knowledge_base.target_freq if hasattr(knowledge_base, 'target_freq') else 2.45

        self.bounds = self.EXPANDED_BOUNDS.copy()

        if hasattr(knowledge_base, 'get_parameter_bounds'):
            try:
                kb_bounds = knowledge_base.get_parameter_bounds()
                for key in self.TUNABLE_PARAMS:
                    if key in kb_bounds:
                        self.bounds[key] = (
                            min(self.bounds[key][0], kb_bounds[key][0]),
                            max(self.bounds[key][1], kb_bounds[key][1])
                        )
            except:
                pass

        # 检测 LLM 可用性
        self.llm_available = self._check_llm()
        self.history: List[Dict] = []

        if not self.is_dual:
            if self.target_freq < 3.0:
                self.default_params = self.FALLBACK_PARAMS['low'].copy()
            elif self.target_freq < 6.0:
                self.default_params = self.FALLBACK_PARAMS['mid'].copy()
            else:
                self.default_params = self.FALLBACK_PARAMS['high'].copy()
        else:
            # 双频默认参数
            self.default_params = {
                'L0': 27.9, 'W0': 40.0, 'Ls': 80.0, 'Ws': 100.0,
                'l1': 6.6, 'l2': 10.0, 'H': 1.6
            }

        self.stats = {
            'rule_decisions': 0,
            'llm_decisions': 0,
            'hybrid_decisions': 0,
            'llm_failures': 0,
        }

        # 打印服务信息
        service_names = {
            "llm_studio": "LLM Studio (本地)",
            "deepseek_api": "DeepSeek API (云端)",
            "ollama": "Ollama (本地)"
        }
        mode_str = mode.value
        print(f"  🧠 AI Brain: 模式={mode_str}, 服务={service_names.get(llm_service, llm_service)}")
        print(f"  🧠 API地址: {api_url}")
        print(f"  🧠 模型: {model_name}")
        print(f"  🧠 状态: {'✅ 已连接' if self.llm_available else '❌ 未连接'}")

        if self.is_dual:
            print(f"  📡 双频模式: {self.target_freq_low}GHz / {self.target_freq_high}GHz")

    def _check_llm(self) -> bool:
        """检测 LLM 服务是否可用"""
        try:
            if self.llm_service == "deepseek_api":
                # DeepSeek API 需要带密钥检测
                if not self.api_key:
                    print("  ⚠️ DeepSeek API Key 未设置")
                    return False
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                resp = requests.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self._get_model_name(),
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1
                    },
                    timeout=5
                )
                return resp.status_code == 200

            elif self.llm_service == "ollama":
                # Ollama 检测
                resp = requests.get(f"{self.api_url}/api/tags", timeout=5)
                return resp.status_code == 200

            else:  # llm_studio 默认
                resp = requests.get(f"{self.api_url}/models", timeout=5)
                return resp.status_code == 200

        except Exception as e:
            print(f"  ⚠️ LLM 检测失败: {e}")
            return False

    def _get_llm_headers(self) -> dict:
        """获取 LLM 请求头"""
        headers = {"Content-Type": "application/json"}

        if self.llm_service == "deepseek_api" and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _get_model_name(self) -> str:
        """获取实际模型名称"""
        if self.llm_service == "deepseek_api":
            return self.DEEPSEEK_MODEL_MAP.get(self.model_name, "deepseek-v4-pro")
        return self.model_name

    def _call_llm(self, prompt: str, system_prompt: str = "",
                  temperature: float = 0.3, max_tokens: int = 300) -> Optional[str]:
        """统一的 LLM 调用接口"""
        try:
            headers = self._get_llm_headers()
            model = self._get_model_name()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # 构建请求体
            request_body = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            # DeepSeek 云端模式：添加思考模式
            if self.llm_service == "deepseek_api":
                request_body["thinking"] = {"type": "enabled"}
                request_body["reasoning_effort"] = "high"

            # 根据服务类型选择 API 端点
            if self.llm_service == "ollama":
                # Ollama 使用不同的 API 格式
                response = requests.post(
                    f"{self.api_url}/api/chat",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": messages,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens
                        },
                        "stream": False
                    },
                    timeout=self.llm_timeout
                )
                if response.status_code == 200:
                    return response.json()['message']['content']
            else:
                # LLM Studio 和 DeepSeek 使用 OpenAI 兼容格式
                response = requests.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=request_body,
                    timeout=self.llm_timeout
                )
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                else:
                    print(f"  ⚠️ LLM 请求失败: HTTP {response.status_code}")
                    if self.llm_service == "deepseek_api" and response.status_code == 401:
                        print(f"  ⚠️ API Key 无效或已过期")
                    return None

        except requests.exceptions.Timeout:
            print(f"  ⚠️ LLM 请求超时 ({self.llm_timeout}s)")
            return None
        except Exception as e:
            print(f"  ⚠️ LLM 请求异常: {e}")
            return None

    def refresh_llm_status(self):
        """重新检测 LLM 服务可用性"""
        self.llm_available = self._check_llm()
        status = "✅" if self.llm_available else "❌"
        print(f"  🔄 LLM 状态刷新: {status}")
        return self.llm_available

    def _get_default_for_key(self, key: str, current_params: Dict = None) -> float:
        if current_params and key in current_params and current_params.get(key, 0) > 0:
            return current_params[key]
        if key in self.default_params:
            return self.default_params[key]
        return 1.0

    def _is_stuck(self) -> bool:
        if len(self.history) < 3:
            return False
        last_three = self.history[-3:]
        s11_values = [h.get('s11', h.get('low_s11', 0)) for h in last_three]
        return all(s > self.target_s11 for s in s11_values) and max(s11_values) - min(s11_values) < 2

    def decide(self,
               current_params: Dict[str, float],
               analysis_result: Dict[str, Any],
               iteration: int) -> OptimizationDecision:

        # 判断是否为双频
        if self.is_dual:
            return self._decide_dual(current_params, analysis_result, iteration)
        else:
            return self._decide_single(current_params, analysis_result, iteration)

    def _decide_single(self, current_params: Dict, analysis_result: Dict, iteration: int) -> OptimizationDecision:
        """单频决策"""
        s11 = analysis_result.get('s11_min_db', 0)
        freq = analysis_result.get('frequency_at_min_ghz', 0)
        bw = analysis_result.get('bandwidth_under_10db_ghz', 0)

        if freq > 0:
            self.history.append({
                'iteration': iteration,
                'params': current_params.copy(),
                's11': s11, 'freq': freq, 'bw': bw
            })

        freq_ok = abs(freq - self.target_freq) < 0.01 if freq else False
        s11_ok = s11 <= self.target_s11

        if freq_ok and s11_ok:
            return OptimizationDecision(
                analysis=f"S11={s11:.2f}dB @ {freq:.4f}GHz",
                strategy="目标达成",
                new_params=current_params,
                expected_effect="无需调整",
                confidence=1.0,
                should_stop=True,
                decision_source="system",
                model_name=self.model_name,
            )

        if self.mode == DecisionMode.RULE_ONLY:
            decision = self._rule_decision_single(current_params, analysis_result)
            decision.model_name = self.model_name
            return decision

        if self.llm_available:
            return self._llm_decision_single(current_params, analysis_result, iteration)
        else:
            decision = self._rule_decision_single(current_params, analysis_result)
            decision.model_name = self.model_name
            return decision

    def _rule_decision_single(self, current_params: Dict, result: Dict) -> OptimizationDecision:
        """单频规则决策"""
        self.stats['rule_decisions'] += 1
        s11 = result.get('s11_min_db', 0)
        freq = result.get('frequency_at_min_ghz', 0)

        new_params = {k: v for k, v in current_params.items()}
        strategy_parts = []

        current_l = current_params.get('l', self.default_params['l'])
        current_w = current_params.get('w', self.default_params['w'])
        current_d1 = current_params.get('d1', self.default_params['d1'])
        current_d2 = current_params.get('d2', self.default_params['d2'])
        current_w1 = current_params.get('w1', self.default_params['w1'])
        current_w2 = current_params.get('w2', self.default_params['w2'])

        stuck = self._is_stuck()

        if freq > 0 and abs(freq - self.target_freq) > 0.01:
            ratio = 1 + (freq / self.target_freq - 1) * 0.5
            ratio = max(0.7, min(1.3, ratio))
            new_params['l'] = current_l * ratio
            new_params['w'] = current_w * ratio
            new_params['d1'] = current_d1 * ratio
            new_params['d2'] = current_d2 * ratio
            new_params['w2'] = current_w2 * ratio
            new_params['w0'] = max(20.0, new_params['w'] * 2.0)
            new_params['l0'] = max(30.0, (new_params['l'] + new_params['d1'] + new_params['d2']) * 1.5)
            strategy_parts.append(f"频率调整 {abs(1 - ratio) * 100:.0f}%")

        elif s11 > self.target_s11:
            if s11 > -10:
                new_params['d2'] = current_d2 * random.choice([0.7, 0.8, 0.85, 1.15, 1.2, 1.3])
                new_params['w1'] = current_w1 * random.choice([0.7, 0.8, 0.85, 1.15, 1.2, 1.3])
                new_params['w2'] = current_w2 * random.choice([0.7, 0.8, 0.85, 1.15, 1.2, 1.3])
                strategy_parts.append("S11差-大幅调整匹配")
            elif s11 > -13:
                new_params['d2'] = current_d2 * random.choice([0.9, 0.92, 0.95, 1.05, 1.08, 1.1])
                new_params['w1'] = current_w1 * random.choice([0.95, 0.98, 1.02, 1.05])
                strategy_parts.append("S11中等-微调匹配")
            else:
                new_params['d2'] = current_d2 * random.choice([0.97, 0.98, 0.99, 1.01, 1.02, 1.03])
                strategy_parts.append("S11接近目标-精细调整")

        if stuck:
            new_params['d2'] = current_d2 * random.choice([0.75, 1.25])
            new_params['w1'] = current_w1 * random.choice([0.75, 1.25])
            new_params['w2'] = current_w2 * random.choice([0.75, 1.25])
            strategy_parts.append("卡住-强制调整")

        new_params = self._protect_params(new_params, current_params)

        return OptimizationDecision(
            analysis=f"S11={s11:.2f}dB @ {freq:.4f}GHz",
            strategy="[规则] " + ("; ".join(strategy_parts) if strategy_parts else "保持"),
            new_params=new_params,
            expected_effect="改善性能",
            confidence=0.85,
            should_stop=False,
            decision_source="rule",
            model_name=self.model_name,
        )

    def _llm_decision_single(self, current_params: Dict, result: Dict, iteration: int) -> OptimizationDecision:
        """单频 LLM 决策"""
        self.stats['llm_decisions'] += 1
        s11 = result.get('s11_min_db', 0)
        freq = result.get('frequency_at_min_ghz', 0)

        prompt = f"""天线优化第{iteration}轮: S11={s11:.1f}dB @ {freq:.3f}GHz (目标{self.target_freq}GHz, S11<{self.target_s11}dB)
参数: l={current_params.get('l', 0):.2f}, w={current_params.get('w', 0):.2f}, d1={current_params.get('d1', 0):.1f}, d2={current_params.get('d2', 0):.2f}, w1={current_params.get('w1', 0):.2f}, w2={current_params.get('w2', 0):.2f}
规则: l,w控制频率(↓尺寸=↑频率), d2,w1控制S11
只输出JSON: {{"l":值,"w":值,"d1":值,"d2":值,"w1":值,"w2":值}}"""

        content = self._call_llm(
            prompt=prompt,
            system_prompt="你是天线设计专家。只输出JSON参数，不要markdown代码块。",
            temperature=0.3,
            max_tokens=300
        )

        if content:
            new_params = self._extract_params_robust(content, current_params)
            if new_params and self._has_param_change(current_params, new_params):
                return OptimizationDecision(
                    analysis="LLM优化",
                    strategy="[LLM] 参数调整",
                    new_params=new_params,
                    expected_effect="改善",
                    confidence=0.7,
                    should_stop=False,
                    decision_source="llm",
                    model_name=self.model_name,
                )

        # 降级到规则决策
        self.stats['llm_failures'] += 1
        decision = self._rule_decision_single(current_params, result)
        decision.model_name = f"{self.model_name}(降级)"
        return decision

    def _decide_dual(self, current_params: Dict, analysis_result: Dict, iteration: int) -> OptimizationDecision:
        """双频决策 - 体现参数优先级"""
        low_s11 = analysis_result.get('low_s11', 0)
        high_s11 = analysis_result.get('high_s11', 0)

        bands = analysis_result.get('bands', {})
        low_band = bands.get(f"{self.target_freq_low}GHz", {})
        high_band = bands.get(f"{self.target_freq_high}GHz", {})
        low_actual_freq = low_band.get('frequency_at_min_ghz', 0)
        high_actual_freq = high_band.get('frequency_at_min_ghz', 0)

        low_freq_error = (low_actual_freq - self.target_freq_low) * 1000 if low_actual_freq else 0
        high_freq_error = (high_actual_freq - self.target_freq_high) * 1000 if high_actual_freq else 0

        is_pass = analysis_result.get('is_pass', False)

        if low_actual_freq > 0:
            self.history.append({
                'iteration': iteration,
                'params': current_params.copy(),
                'low_s11': low_s11, 'high_s11': high_s11,
                'low_freq': low_actual_freq, 'high_freq': high_actual_freq,
            })

        low_freq_ok = abs(low_freq_error) < 20  # 20MHz精度
        high_freq_ok = abs(high_freq_error) < 20
        low_s11_ok = low_s11 <= self.target_s11
        high_s11_ok = high_s11 <= self.target_s11

        if low_freq_ok and high_freq_ok and low_s11_ok and high_s11_ok:
            return OptimizationDecision(
                analysis=f"低频S11={low_s11:.2f}dB @ {low_actual_freq:.4f}GHz, 高频S11={high_s11:.2f}dB @ {high_actual_freq:.4f}GHz",
                strategy="双频目标达成",
                new_params=current_params,
                expected_effect="无需调整",
                confidence=1.0,
                should_stop=True,
                decision_source="system",
                model_name=self.model_name,
            )

        if self.mode == DecisionMode.RULE_ONLY:
            decision = self._rule_decision_dual(current_params, analysis_result)
            decision.model_name = self.model_name
            return decision

        # 尝试刷新 LLM 状态
        if not self.llm_available:
            self.refresh_llm_status()

        if self.llm_available:
            return self._llm_decision_dual(current_params, analysis_result, iteration)
        else:
            decision = self._rule_decision_dual(current_params, analysis_result)
            decision.model_name = self.model_name
            return decision

    def _rule_decision_dual(self, current_params: Dict, result: Dict) -> OptimizationDecision:
        """双频规则决策 - 参数优先级"""
        self.stats['rule_decisions'] += 1

        low_s11 = result.get('low_s11', 0)
        high_s11 = result.get('high_s11', 0)
        low_freq_error = result.get('low_freq_error', 0)
        high_freq_error = result.get('high_freq_error', 0)

        new_params = current_params.copy()
        strategy_parts = []

        current_L0 = current_params.get('L0', 27.9)
        current_W0 = current_params.get('W0', 40.0)
        current_Ls = current_params.get('Ls', 80.0)
        current_Ws = current_params.get('Ws', 100.0)
        current_l1 = current_params.get('l1', 6.6)
        current_l2 = current_params.get('l2', 10.0)

        # L0 调整低频频率
        if abs(low_freq_error) > 30:
            ratio = 1 - low_freq_error / 800
            ratio = max(0.92, min(1.08, ratio))
            new_L0 = current_L0 * ratio
            new_params['L0'] = round(new_L0, 2)
            strategy_parts.append(f"L0调低频({low_freq_error:+.0f}MHz)")
        else:
            new_params['L0'] = current_L0

        # W0 调整高频频率
        if abs(high_freq_error) > 30:
            ratio = 1 - high_freq_error / 800
            ratio = max(0.92, min(1.08, ratio))
            new_W0 = current_W0 * ratio
            new_params['W0'] = round(new_W0, 2)
            strategy_parts.append(f"W0调高频({high_freq_error:+.0f}MHz)")
        else:
            new_params['W0'] = current_W0

        # Ls 辅助调频
        if abs(low_freq_error) > 15 or abs(high_freq_error) > 15:
            avg_error = (low_freq_error + high_freq_error) / 2
            ratio = 1 - avg_error / 1200
            ratio = max(0.96, min(1.04, ratio))
            if abs(ratio - 1.0) > 0.005:
                new_Ls = current_Ls * ratio
                new_params['Ls'] = round(max(40.0, min(200.0, new_Ls)), 1)
                strategy_parts.append(f"Ls辅助调频({ratio:.3f})")

        # Ws 辅助调频
        if abs(high_freq_error) > 15 or abs(low_freq_error) > 15:
            ratio = 1 - high_freq_error / 1200
            ratio = max(0.96, min(1.04, ratio))
            if abs(ratio - 1.0) > 0.005:
                new_Ws = current_Ws * ratio
                new_params['Ws'] = round(max(50.0, min(250.0, new_Ws)), 1)
                strategy_parts.append(f"Ws辅助调频({ratio:.3f})")

        # l1 控制低频 S11（乘法步长：S11越差，增幅越大）
        if low_s11 > self.target_s11:
            if low_s11 > -10:
                step_ratio = 1.5  # S11极差，激进增大50%
                strategy_parts.append(f"l1激进增大({current_l1:.2f}→")
            elif low_s11 > -13:
                step_ratio = 1.25  # S11较差，增大25%
                strategy_parts.append(f"l1大幅增大({current_l1:.2f}→")
            elif low_s11 > self.target_s11 + 1:
                step_ratio = 1.10
                strategy_parts.append(f"l1中等增大({current_l1:.2f}→")
            else:
                step_ratio = 1.05
                strategy_parts.append(f"l1微调增大({current_l1:.2f}→")

            new_l1 = current_l1 * step_ratio
            new_l1 = max(2.0, min(25.0, new_l1))
            new_params['l1'] = round(new_l1, 2)
            strategy_parts[-1] = f"{strategy_parts[-1]}{new_l1:.2f}mm)"

        # l2 控制高频 S11
        print(f"  🔧 [规则] l2={current_l2:.2f}mm, 高频S11={high_s11:.2f}dB, 目标={self.target_s11}dB")

        if high_s11 > self.target_s11:
            if current_l2 < 8.0:
                if high_s11 > -10:
                    step_ratio = 1.30
                elif high_s11 > -13:
                    step_ratio = 1.20
                else:
                    step_ratio = 1.15
                new_l2 = current_l2 * step_ratio
                new_l2 = min(30.0, new_l2)
                strategy_parts.append(f"l2过小强制增大 {current_l2:.2f}→{new_l2:.2f}mm")
            elif current_l2 < 12.0:
                step_ratio = 1.10
                new_l2 = current_l2 * step_ratio
                new_l2 = min(30.0, new_l2)
                strategy_parts.append(f"l2向最佳范围增大 {current_l2:.2f}→{new_l2:.2f}mm")
            elif current_l2 <= 18.0:
                import random
                step_ratio = random.choice([1.02, 1.03, 1.04, 1.05, 0.98])
                new_l2 = current_l2 * step_ratio
                new_l2 = max(8.0, min(30.0, new_l2))
                if step_ratio > 1.0:
                    strategy_parts.append(f"l2微调增大 {current_l2:.2f}→{new_l2:.2f}mm")
                else:
                    strategy_parts.append(f"l2微调减小 {current_l2:.2f}→{new_l2:.2f}mm")
            else:
                step_ratio = 0.92
                new_l2 = current_l2 * step_ratio
                new_l2 = max(8.0, new_l2)
                strategy_parts.append(f"l2偏大减小 {current_l2:.2f}→{new_l2:.2f}mm")
            new_params['l2'] = round(new_l2, 2)
        else:
            if current_l2 < 8.0:
                new_l2 = min(30.0, current_l2 * 1.10)
                new_params['l2'] = round(new_l2, 2)
                strategy_parts.append(f"l2虽达标但过小，优化 {current_l2:.2f}→{new_l2:.2f}mm")
            elif current_l2 > 20.0:
                new_l2 = max(8.0, current_l2 * 0.95)
                new_params['l2'] = round(new_l2, 2)
                strategy_parts.append(f"l2虽达标但过大，优化 {current_l2:.2f}→{new_l2:.2f}mm")

        # 卡住检测
        if self._is_stuck():
            import random
            new_params['l2'] = min(30.0, new_params.get('l2', current_l2) * random.uniform(1.1, 1.3))
            strategy_parts.append("卡住-l2强制增大")
            print(f"  ⚠️ 卡住检测，强制调整 l2 → {new_params['l2']:.2f}mm")

        # 边界保护
        bounds = {
            'L0': (15.0, 80.0),
            'W0': (20.0, 100.0),
            'Ls': (40.0, 200.0),
            'Ws': (50.0, 250.0),
            'l1': (2.0, 25.0),
            'l2': (4.0, 30.0),
        }

        for key, (low, high) in bounds.items():
            if key in new_params:
                new_params[key] = max(low, min(high, new_params[key]))

        if new_params.get('Ls', 0) < new_params.get('L0', 0) + 20:
            new_params['Ls'] = new_params['L0'] + 20
            strategy_parts.append("Ls自动扩展")
        if new_params.get('Ws', 0) < new_params.get('W0', 0) + 20:
            new_params['Ws'] = new_params['W0'] + 20
            strategy_parts.append("Ws自动扩展")

        new_params['H'] = current_params.get('H', 1.6)

        print(f"  🔧 [规则结果] l1={new_params.get('l1'):.2f}, l2={new_params.get('l2'):.2f}")

        low_freq_str = f"{result.get('low_actual_freq', 0):.4f}" if result.get('low_actual_freq') else "N/A"
        high_freq_str = f"{result.get('high_actual_freq', 0):.4f}" if result.get('high_actual_freq') else "N/A"

        return OptimizationDecision(
            analysis=f"低频S11={low_s11:.1f}dB @ {low_freq_str}GHz, 高频S11={high_s11:.1f}dB @ {high_freq_str}GHz",
            strategy="[规则] " + ("; ".join(strategy_parts) if strategy_parts else "保持参数"),
            new_params=new_params,
            expected_effect="改善双频性能",
            confidence=0.85,
            should_stop=False,
            decision_source="rule",
            model_name=self.model_name,
        )

    def _llm_decision_dual(self, current_params: Dict, result: Dict, iteration: int) -> OptimizationDecision:
        """双频 LLM 决策"""
        self.stats['llm_decisions'] += 1

        low_s11 = result.get('low_s11', 0)
        high_s11 = result.get('high_s11', 0)

        bands = result.get('bands', {})
        low_band = bands.get(f"{self.target_freq_low}GHz", {})
        high_band = bands.get(f"{self.target_freq_high}GHz", {})
        low_actual_freq = low_band.get('frequency_at_min_ghz', 0)
        high_actual_freq = high_band.get('frequency_at_min_ghz', 0)

        low_freq_error = (low_actual_freq - self.target_freq_low) * 1000 if low_actual_freq else 0
        high_freq_error = (high_actual_freq - self.target_freq_high) * 1000 if high_actual_freq else 0

        prompt = f"""你是双频微带天线设计专家。

【参数优先级（非常重要！）】
1. L0: 控制【低频】频率，优先级最高，调整幅度 5-8%
2. W0: 控制【高频】频率，优先级最高，调整幅度 5-8%
3. Ls: 控制介质板长度，影响两个频率，优先级中等，调整幅度 2-4%
4. Ws: 控制介质板宽度，影响两个频率，优先级中等，调整幅度 2-4%
5. l1: 控制低频 S11 匹配深度（范围3-25mm），S11差时允许±30%调整
6. l2: 控制高频 S11 匹配深度（范围4-30mm），S11差时允许±30%调整

【物理规律 - 核心】
- 频率偏高 → 增大尺寸 ↓频率
- L0 ↑ → 低频频率 ↓, W0 ↑ → 高频频率 ↓
- l1 增大 → 低频 S11 变好（更负），S11差时需大幅增大 l1
- l2 太小(<6mm)或太大(>20mm)都会导致高频S11差，最佳范围 8-15mm
- Ls/Ws 必须大于 L0/W0，保持 Ls ≥ L0+20, Ws ≥ W0+20

【当前性能】
低频: S11={low_s11:.2f}dB @ {low_actual_freq:.4f}GHz (目标{self.target_freq_low}GHz, 频偏{low_freq_error:+.0f}MHz)
高频: S11={high_s11:.2f}dB @ {high_actual_freq:.4f}GHz (目标{self.target_freq_high}GHz, 频偏{high_freq_error:+.0f}MHz)

【当前参数】
L0={current_params.get('L0', 0):.2f} mm  (主控低频)
W0={current_params.get('W0', 0):.2f} mm  (主控高频)
Ls={current_params.get('Ls', 0):.1f} mm   (介质板长度)
Ws={current_params.get('Ws', 0):.1f} mm   (介质板宽度)
l1={current_params.get('l1', 0):.2f} mm   (低频匹配)
l2={current_params.get('l2', 0):.2f} mm   (高频匹配)

【输出要求】
只输出JSON，不要markdown，不要其他文字：
{{"L0": xx.xx, "W0": xx.xx, "Ls": xx.x, "Ws": xx.x, "l1": xx.xx, "l2": xx.xx}}"""

        content = self._call_llm(
            prompt=prompt,
            system_prompt="你是天线设计专家。优先调整L0和W0调整频率，最后调整l1/l2改善匹配。只输出JSON。",
            temperature=0.4,
            max_tokens=350
        )

        if content:
            content = content.replace('```json', '').replace('```', '').strip()
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                try:
                    new_params = json.loads(json_match.group())
                    validated_params = {}

                    if 'L0' in new_params:
                        val = float(new_params['L0'])
                        ratio = val / current_params.get('L0', val)
                        if 0.92 <= ratio <= 1.08:
                            validated_params['L0'] = max(15.0, min(80.0, val))

                    if 'W0' in new_params:
                        val = float(new_params['W0'])
                        ratio = val / current_params.get('W0', val)
                        if 0.92 <= ratio <= 1.08:
                            validated_params['W0'] = max(20.0, min(100.0, val))

                    if 'Ls' in new_params:
                        val = float(new_params['Ls'])
                        ratio = val / current_params.get('Ls', val)
                        if 0.96 <= ratio <= 1.04:
                            validated_params['Ls'] = max(40.0, min(200.0, val))

                    if 'Ws' in new_params:
                        val = float(new_params['Ws'])
                        ratio = val / current_params.get('Ws', val)
                        if 0.96 <= ratio <= 1.04:
                            validated_params['Ws'] = max(50.0, min(250.0, val))

                    # l1/l2: 根据 S11 表现动态调整允许范围
                    # S11 差时允许更大步长（±30%），好时限制小步长（±5%）
                    l1_range = (0.70, 1.30) if low_s11 > -10 else \
                               (0.80, 1.20) if low_s11 > self.target_s11 else \
                               (0.95, 1.05)

                    if 'l1' in new_params:
                        val = float(new_params['l1'])
                        ratio = val / current_params.get('l1', val)
                        if l1_range[0] <= ratio <= l1_range[1]:
                            validated_params['l1'] = max(2.0, min(25.0, val))

                    l2_range = (0.70, 1.30) if high_s11 > -10 else \
                               (0.80, 1.20) if high_s11 > self.target_s11 else \
                               (0.95, 1.05)

                    if 'l2' in new_params:
                        val = float(new_params['l2'])
                        ratio = val / current_params.get('l2', val)
                        if l2_range[0] <= ratio <= l2_range[1]:
                            validated_params['l2'] = max(3.0, min(30.0, val))

                    for key in ['L0', 'W0', 'Ls', 'Ws', 'l1', 'l2']:
                        if key not in validated_params:
                            validated_params[key] = current_params.get(key)

                    if validated_params.get('Ls', 0) < validated_params.get('L0', 0) + 20:
                        validated_params['Ls'] = validated_params['L0'] + 20

                    if validated_params.get('Ws', 0) < validated_params.get('W0', 0) + 20:
                        validated_params['Ws'] = validated_params['W0'] + 20

                    validated_params['H'] = current_params.get('H', 1.6)

                    strategy = f"LLM调整: L0={validated_params['L0']:.2f}, W0={validated_params['W0']:.2f}, Ls={validated_params['Ls']:.1f}, Ws={validated_params['Ws']:.1f}, l1={validated_params['l1']:.2f}, l2={validated_params['l2']:.2f}"

                    return OptimizationDecision(
                        analysis=f"低频S11={low_s11:.1f}dB, 高频S11={high_s11:.1f}dB",
                        strategy="[LLM] " + strategy,
                        new_params=validated_params,
                        expected_effect="改善双频性能",
                        confidence=0.7,
                        should_stop=False,
                        decision_source="llm",
                        model_name=self.model_name,
                    )
                except Exception as e:
                    print(f"  ⚠️ 解析 LLM 响应失败: {e}")

        print(f"  ⚠️ LLM 决策失败，降级到规则决策")
        self.stats['llm_failures'] += 1
        decision = self._rule_decision_dual(current_params, result)
        decision.model_name = f"{self.model_name}(降级)"
        return decision

    def _extract_params_robust(self, content: str, current_params: Dict) -> Dict:
        """鲁棒提取JSON参数"""
        cleaned = content.strip()
        cleaned = cleaned.replace('```json', '').replace('```', '')
        cleaned = re.sub(r'//.*?\n', '\n', cleaned)

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                if 'new_params' in data:
                    data = data['new_params']
                return self._validate_params(data, current_params)
        except:
            pass

        json_match = re.search(r'\{[^{}]*"l"\s*:\s*[\d.]+[^{}]*\}', cleaned, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if 'new_params' in data:
                    data = data['new_params']
                return self._validate_params(data, current_params)
            except:
                pass

        patterns = {
            'l': r'"l"\s*:\s*([\d.]+)', 'w': r'"w"\s*:\s*([\d.]+)',
            'd1': r'"d1"\s*:\s*([\d.]+)', 'd2': r'"d2"\s*:\s*([\d.]+)',
            'w1': r'"w1"\s*:\s*([\d.]+)', 'w2': r'"w2"\s*:\s*([\d.]+)',
        }

        extracted = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, cleaned)
            if match:
                val = float(match.group(1))
                if 0.1 < val < 500:
                    extracted[key] = val

        if 'l' in extracted and 'w' in extracted:
            return self._validate_params(extracted, current_params)

        return {}

    def _validate_params(self, params: Dict, current_params: Dict) -> Dict:
        """验证参数范围"""
        validated = {}
        for key in self.TUNABLE_PARAMS:
            if key in params and params[key] > 0:
                current_val = current_params.get(key, self.default_params.get(key, 1))
                if current_val > 0 and key in ['l', 'w']:
                    validated[key] = round(max(current_val * 0.7, min(current_val * 1.3, params[key])), 2)
                elif current_val > 0:
                    validated[key] = round(max(current_val * 0.5, min(current_val * 2.0, params[key])), 2)
                else:
                    validated[key] = round(params[key], 2)
            else:
                validated[key] = current_params.get(key, self.default_params.get(key, 0))

        l_val = validated.get('l', current_params.get('l', 37))
        w_val = validated.get('w', current_params.get('w', 44))
        d1_val = validated.get('d1', current_params.get('d1', 22))
        d2_val = validated.get('d2', current_params.get('d2', 18))

        validated['w0'] = round(max(20.0, w_val * 2.0), 1)
        validated['l0'] = round(max(30.0, (l_val + d1_val + d2_val) * 1.5), 1)

        return validated

    def _has_param_change(self, old_params: Dict, new_params: Dict) -> bool:
        """检查参数是否有变化"""
        for key in ['l', 'w', 'd1', 'd2', 'w1', 'w2']:
            if abs(old_params.get(key, 0) - new_params.get(key, 0)) > 0.01:
                return True
        return False

    def _protect_params(self, new_params: Dict, current_params: Dict) -> Dict:
        """保护参数边界"""
        protected = {}
        for key in ['l', 'w', 'w0', 'l0', 'w1', 'd1', 'w2', 'd2']:
            value = new_params.get(key, 0)
            if value <= 0:
                value = current_params.get(key, self.default_params.get(key, 1))
            if key in self.bounds:
                value = max(self.bounds[key][0], min(self.bounds[key][1], value))
            protected[key] = round(value, 2 if key in ['l', 'w', 'w1', 'w2', 'd2'] else 1)
        return protected

    def _parse_json(self, content: str) -> Dict:
        """解析JSON"""
        try:
            return json.loads(content)
        except:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return {}

    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = self.stats.copy()
        stats['model_name'] = self.model_name
        stats['llm_service'] = self.llm_service
        if self.is_dual:
            stats['is_dual'] = True
            stats['target_freq_low'] = self.target_freq_low
            stats['target_freq_high'] = self.target_freq_high
        return stats