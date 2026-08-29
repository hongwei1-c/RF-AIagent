#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S参数分析模块
- CSV数值分析（精确计算）
- 多频点分析（新增）
- LLM智能诊断（可选，用于生成建议和报告）
"""

import os
import sys
import csv
import json
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
from scipy import interpolate
import warnings

warnings.filterwarnings('ignore')


@dataclass
class S11AnalysisResult:
    """S11分析结果"""
    s11_min_db: float
    frequency_at_min_ghz: float
    bandwidth_under_6db_ghz: float
    bandwidth_under_10db_ghz: float
    bandwidth_under_15db_ghz: float
    center_frequency_ghz: Optional[float] = None
    q_value: Optional[float] = None
    resonance_depth_db: Optional[float] = None
    is_pass: bool = False
    threshold_used_db: float = -10
    data_points: int = 0
    frequency_range: Dict = field(default_factory=dict)


@dataclass
class MultiBandAnalysisResult:
    """多频段分析结果"""
    bands_analysis: Dict[str, Dict] = field(default_factory=dict)
    is_pass: bool = False
    overall_score: float = 0.0


class CSVSParameterAnalyzer:
    """基于CSV数据的S参数分析器（纯数值计算）"""

    def __init__(self):
        self.s11_data = None
        self.frequencies = None

    def parse_csv(self, csv_path: str) -> Dict[str, Any]:
        """
        解析HFSS导出的CSV文件

        Args:
            csv_path: CSV文件路径

        Returns:
            包含频率和S参数数据的字典
        """
        try:
            frequencies = []
            s11_data = []
            s21_data = []
            s12_data = []
            s22_data = []

            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)
                header = [h.strip().strip('"').strip() for h in header]

                # 查找列索引
                freq_idx = 0
                s11_idx = None
                s21_idx = None
                s12_idx = None
                s22_idx = None

                for i, col in enumerate(header):
                    col_lower = col.lower()
                    if 'freq' in col_lower or col_lower == 'x':
                        freq_idx = i
                    elif 's(1,1)' in col_lower or 's11' in col_lower:
                        s11_idx = i
                    elif 's(2,1)' in col_lower or 's21' in col_lower:
                        s21_idx = i
                    elif 's(1,2)' in col_lower or 's12' in col_lower:
                        s12_idx = i
                    elif 's(2,2)' in col_lower or 's22' in col_lower:
                        s22_idx = i

                # 读取数据
                for row in reader:
                    if not row:
                        continue
                    try:
                        freq = float(row[freq_idx].strip())
                        frequencies.append(freq)

                        if s11_idx is not None and s11_idx < len(row):
                            s11_data.append(float(row[s11_idx].strip()))
                        if s21_idx is not None and s21_idx < len(row):
                            s21_data.append(float(row[s21_idx].strip()))
                        if s12_idx is not None and s12_idx < len(row):
                            s12_data.append(float(row[s12_idx].strip()))
                        if s22_idx is not None and s22_idx < len(row):
                            s22_data.append(float(row[s22_idx].strip()))
                    except (ValueError, IndexError):
                        continue

            result = {
                'frequencies': np.array(frequencies),
                's11': np.array(s11_data) if s11_data else None,
                's21': np.array(s21_data) if s21_data else None,
                's12': np.array(s12_data) if s12_data else None,
                's22': np.array(s22_data) if s22_data else None,
            }

            self.frequencies = result['frequencies']
            self.s11_data = result['s11']
            return result

        except Exception as e:
            print(f"解析CSV失败: {e}")
            return None

    def analyze_s11(self, frequencies: np.ndarray, s11_db: np.ndarray,
                    threshold_db: float = -10) -> S11AnalysisResult:
        """
        分析S11参数（纯数值计算）

        Args:
            frequencies: 频率数组 (GHz)
            s11_db: S11数据数组 (dB)
            threshold_db: 阈值 (dB)

        Returns:
            S11AnalysisResult对象
        """
        if s11_db is None or len(s11_db) == 0:
            return None

        frequencies = np.array(frequencies)
        s11_db = np.array(s11_db)

        # 移除无效值
        valid_mask = np.isfinite(s11_db)
        if not np.any(valid_mask):
            return None

        frequencies = frequencies[valid_mask]
        s11_db = s11_db[valid_mask]

        if len(frequencies) < 2:
            return None

        # 找最小值
        min_idx = np.argmin(s11_db)
        s11_min = float(s11_db[min_idx])
        freq_at_min = float(frequencies[min_idx])

        # 计算各阈值带宽
        bandwidth_6db = self._calculate_bandwidth(frequencies, s11_db, -6)
        bandwidth_10db = self._calculate_bandwidth(frequencies, s11_db, threshold_db)
        bandwidth_15db = self._calculate_bandwidth(frequencies, s11_db, -15)

        # 计算中心频率和Q值
        center_freq, q_value = self._calculate_center_and_q(
            frequencies, s11_db, s11_min, freq_at_min
        )

        # 计算谐振深度
        avg_s11 = np.mean(s11_db)
        resonance_depth = avg_s11 - s11_min if avg_s11 > s11_min else 0

        return S11AnalysisResult(
            s11_min_db=round(s11_min, 2),
            frequency_at_min_ghz=round(freq_at_min, 4),
            bandwidth_under_6db_ghz=round(bandwidth_6db, 4),
            bandwidth_under_10db_ghz=round(bandwidth_10db, 4),
            bandwidth_under_15db_ghz=round(bandwidth_15db, 4),
            center_frequency_ghz=round(center_freq, 4) if center_freq else None,
            q_value=round(q_value, 1) if q_value else None,
            resonance_depth_db=round(resonance_depth, 2),
            is_pass=s11_min <= threshold_db,
            threshold_used_db=threshold_db,
            data_points=len(frequencies),
            frequency_range={
                'start': round(float(frequencies[0]), 4),
                'end': round(float(frequencies[-1]), 4)
            }
        )

    def _calculate_bandwidth(self, frequencies: np.ndarray, s11_db: np.ndarray,
                             threshold: float) -> float:
        """计算指定阈值下的带宽"""
        below_threshold = s11_db <= threshold

        total_bandwidth = 0.0
        in_range = False
        start_freq = None

        for i, is_below in enumerate(below_threshold):
            if is_below and not in_range:
                in_range = True
                start_freq = frequencies[i]
            elif not is_below and in_range:
                in_range = False
                total_bandwidth += frequencies[i - 1] - start_freq

        if in_range:
            total_bandwidth += frequencies[-1] - start_freq

        return total_bandwidth

    def _calculate_center_and_q(self, frequencies: np.ndarray, s11_db: np.ndarray,
                                s11_min: float, freq_at_min: float) -> Tuple[Optional[float], Optional[float]]:
        """计算中心频率和Q值"""
        # 找到-3dB点（相对于最小值）
        s11_3db = s11_min + 3
        min_idx = np.argmin(s11_db)

        # 搜索范围
        search_range = min(20, len(frequencies) // 4)
        start_idx = max(0, min_idx - search_range)
        end_idx = min(len(frequencies), min_idx + search_range)

        freq_sub = frequencies[start_idx:end_idx]
        s11_sub = s11_db[start_idx:end_idx]

        # 找左侧-3dB点
        left_freq = None
        for i in range(len(freq_sub) - 1):
            if (s11_sub[i] <= s11_3db <= s11_sub[i + 1] or
                    s11_sub[i] >= s11_3db >= s11_sub[i + 1]):
                t = (s11_3db - s11_sub[i]) / (s11_sub[i + 1] - s11_sub[i] + 1e-9)
                left_freq = freq_sub[i] + t * (freq_sub[i + 1] - freq_sub[i])
                break

        # 找右侧-3dB点
        right_freq = None
        for i in range(len(freq_sub) - 1, 0, -1):
            if (s11_sub[i] <= s11_3db <= s11_sub[i - 1] or
                    s11_sub[i] >= s11_3db >= s11_sub[i - 1]):
                t = (s11_3db - s11_sub[i]) / (s11_sub[i - 1] - s11_sub[i] + 1e-9)
                right_freq = freq_sub[i] + t * (freq_sub[i - 1] - freq_sub[i])
                break

        if left_freq and right_freq and right_freq > left_freq:
            bandwidth_3db = right_freq - left_freq
            if bandwidth_3db > 0:
                center_freq = (left_freq + right_freq) / 2
                q_value = center_freq / bandwidth_3db
                return center_freq, q_value

        return None, None

    def analyze_csv_file(self, csv_path: str, threshold_db: float = -10) -> Dict[str, Any]:
        """分析CSV文件"""
        if not os.path.exists(csv_path):
            return {'error': f'文件不存在: {csv_path}', 'is_pass': False}

        csv_data = self.parse_csv(csv_path)
        if csv_data is None or csv_data['s11'] is None:
            return {'error': 'CSV解析失败或无S11数据', 'is_pass': False}

        result = self.analyze_s11(csv_data['frequencies'], csv_data['s11'], threshold_db)

        if result is None:
            return {'error': '分析失败', 'is_pass': False}

        return {
            's11_min_db': result.s11_min_db,
            'frequency_at_min_ghz': result.frequency_at_min_ghz,
            'bandwidth_under_10db_ghz': result.bandwidth_under_10db_ghz,
            'bandwidth_under_6db_ghz': result.bandwidth_under_6db_ghz,
            'bandwidth_under_15db_ghz': result.bandwidth_under_15db_ghz,
            'center_frequency_ghz': result.center_frequency_ghz,
            'q_value': result.q_value,
            'resonance_depth_db': result.resonance_depth_db,
            'is_pass': result.is_pass,
            'threshold_used_db': threshold_db,
            'data_points': result.data_points,
            'frequency_range': result.frequency_range,
            'method': 'csv_numerical_analysis',
            'confidence': 1.0
        }


def analyze_multi_band(frequencies: np.ndarray,
                       s11_db: np.ndarray,
                       target_freqs: Dict[str, float],
                       threshold_db: float = -10) -> MultiBandAnalysisResult:
    """
    分析多频段S参数

    Args:
        frequencies: 频率数组
        s11_db: S11数据
        target_freqs: 目标频点字典 {'2.45GHz': 2.45, '5GHz': 5.0}
        threshold_db: 阈值

    Returns:
        MultiBandAnalysisResult 对象
    """
    bands_analysis = {}
    all_pass = True
    overall_score = 0.0

    frequency_ghz = np.array(frequencies)
    s11_values = np.array(s11_db)

    for band_name, target_freq in target_freqs.items():
        # 提取该频点附近的S11值
        freq_tolerance = 0.1  # 100MHz容差
        band_mask = np.abs(frequency_ghz - target_freq) < freq_tolerance

        if not np.any(band_mask):
            bands_analysis[band_name] = {
                's11_at_target': None,
                'frequency_at_min_ghz': None,
                'is_pass': False,
                'error': '频点数据不足',
                'freq_error_mhz': None
            }
            all_pass = False
            continue

        band_freqs = frequency_ghz[band_mask]
        band_s11 = s11_values[band_mask]

        # 找到最小S11
        min_idx = np.argmin(band_s11)
        s11_min = float(band_s11[min_idx])
        freq_at_min = float(band_freqs[min_idx])

        # 计算频率偏差
        freq_error_mhz = (freq_at_min - target_freq) * 1000

        # 判断是否达标
        is_pass = s11_min <= threshold_db

        bands_analysis[band_name] = {
            's11_at_target': round(s11_min, 2),
            'frequency_at_min_ghz': round(freq_at_min, 4),
            'is_pass': is_pass,
            'freq_error_mhz': round(freq_error_mhz, 1)
        }

        if not is_pass:
            all_pass = False

        # 计算得分（S11越低越好，频率越准越好）
        s11_score = max(0, min(1, (s11_min - threshold_db) / (-20 - threshold_db))) if s11_min < 0 else 0
        freq_score = max(0, 1 - abs(freq_error_mhz) / 100)  # 100MHz内线性衰减
        band_score = 0.7 * s11_score + 0.3 * freq_score
        overall_score += band_score

    # 平均得分
    if target_freqs:
        overall_score /= len(target_freqs)

    return MultiBandAnalysisResult(
        bands_analysis=bands_analysis,
        is_pass=all_pass,
        overall_score=overall_score
    )


class LLMAdvisor:
    """LLM智能顾问（用于生成诊断和建议）"""

    def __init__(self, api_url: str = "http://localhost:1234/v1",
                 model_name: str = "qwen2.5-coder-7b-instruct",
                 enabled: bool = True):
        self.api_url = api_url
        self.model_name = model_name
        self.enabled = enabled
        self.available = self._check_availability() if enabled else False

    def _check_availability(self) -> bool:
        """检查LLM服务是否可用"""
        try:
            import requests
            resp = requests.get(f"{self.api_url}/models", timeout=5)
            return resp.status_code == 200
        except:
            return False

    def generate_diagnosis(self, analysis_result: Dict[str, Any]) -> str:
        """生成性能诊断"""
        if not self.available:
            return self._get_fallback_diagnosis(analysis_result)

        prompt = f"""
        请分析以下天线S参数结果，给出专业诊断：

        S11最小值: {analysis_result.get('s11_min_db')} dB
        -10dB带宽: {analysis_result.get('bandwidth_under_10db_ghz')} GHz
        中心频率: {analysis_result.get('center_frequency_ghz')} GHz
        Q值: {analysis_result.get('q_value')}
        谐振深度: {analysis_result.get('resonance_depth_db')} dB
        判定结果: {'合格' if analysis_result.get('is_pass') else '不合格'}
        阈值: {analysis_result.get('threshold_used_db')} dB

        请回答：
        1. 性能评估（优/良/差及理由）
        2. 如果性能不佳，可能的原因是什么
        3. 具体优化建议（2-3条）

        使用专业但易懂的语言：
        """

        try:
            import requests
            response = requests.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"LLM调用失败: {e}")

        return self._get_fallback_diagnosis(analysis_result)

    def _get_fallback_diagnosis(self, analysis_result: Dict[str, Any]) -> str:
        """降级诊断（不使用LLM）"""
        s11 = analysis_result.get('s11_min_db', 0)
        bw = analysis_result.get('bandwidth_under_10db_ghz', 0)
        is_pass = analysis_result.get('is_pass', False)

        if is_pass:
            if s11 < -20:
                perf = "优秀"
            elif s11 < -15:
                perf = "良好"
            else:
                perf = "合格"

            return f"""【性能评估】{perf}
- S11最小值{s11}dB，匹配良好
- -10dB带宽{bw}GHz

【建议】设计满足要求，可考虑进一步优化增益和方向性。"""
        else:
            reasons = []
            if s11 > -10:
                reasons.append("阻抗匹配不足")
            if bw < 0.05:
                reasons.append("带宽较窄")

            return f"""【性能评估】不合格
- S11最小值{s11}dB，未达到{analysis_result.get('threshold_used_db', 10)}dB要求
- 问题诊断：{', '.join(reasons) if reasons else '综合性能不足'}

【优化建议】
1. 调整馈电点位置，优化输入阻抗
2. 增加匹配网络或调整贴片尺寸
3. 考虑使用多层结构增加带宽"""

    def generate_multi_band_diagnosis(self, analysis_result: Dict[str, Any]) -> str:
        """生成多频段诊断"""
        if not self.available:
            bands = analysis_result.get('bands', {})
            diagnosis = "【多频点分析】\n"
            for band_name, info in bands.items():
                status = "✅ 达标" if info.get('is_pass') else "❌ 未达标"
                s11 = info.get('s11_at_target', 'N/A')
                freq_err = info.get('freq_error_mhz', 'N/A')
                diagnosis += f"- {band_name}: S11={s11}dB, 频偏={freq_err}MHz {status}\n"
            return diagnosis

        bands_info = json.dumps(analysis_result.get('bands', {}), indent=2)
        prompt = f"""分析以下多频天线性能：

{bands_info}

请提供：
1. 各频点性能评估
2. 优化优先级建议
3. 参数调整方向"""

        try:
            import requests
            response = requests.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
        except:
            pass

        return self._get_fallback_diagnosis(analysis_result)

    def generate_dual_band_report(self, result: Dict[str, Any]) -> str:
        """生成双频分析报告"""
        bands = result.get('bands', {})

        report = "📡 双频天线性能分析\n"
        report += "=" * 40 + "\n"

        for band_name, info in bands.items():
            s11 = info.get('s11_at_target', 'N/A')
            freq_err = info.get('freq_error_mhz', 'N/A')
            is_pass = info.get('is_pass', False)

            status = "✅ 达标" if is_pass else "❌ 未达标"
            report += f"\n{band_name}:\n"
            report += f"  S11: {s11} dB  {status}\n"
            report += f"  频偏: {freq_err} MHz\n"

        report += "\n" + "=" * 40 + "\n"
        report += f"综合判定: {'✅ 全部合格' if result.get('is_pass') else '❌ 部分频点未达标'}\n"
        report += f"综合得分: {result.get('overall_score', 0):.2f}\n"

        return report

    def generate_report(self, all_results: List[Dict[str, Any]],
                        stats: Dict[str, Any]) -> str:
        """生成综合报告"""
        if not self.available:
            return self._get_fallback_report(all_results, stats)

        prompt = f"""
        基于以下天线仿真结果，生成一份专业的技术报告：

        总设计数: {stats.get('total', 0)}
        合格数: {stats.get('passed', 0)}
        通过率: {stats.get('pass_rate', 0):.1f}%

        S11统计:
        - 最佳: {stats.get('s11_best', 'N/A')} dB
        - 最差: {stats.get('s11_worst', 'N/A')} dB
        - 平均: {stats.get('s11_avg', 'N/A')} dB

        请生成包含以下内容的报告：
        1. 执行摘要
        2. 统计概览
        3. 典型合格案例分析
        4. 典型不合格案例分析
        5. 总体建议

        使用Markdown格式：
        """

        try:
            import requests
            response = requests.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 800
                },
                timeout=40
            )
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
        except:
            pass

        return self._get_fallback_report(all_results, stats)

    def _get_fallback_report(self, all_results: List[Dict[str, Any]],
                             stats: Dict[str, Any]) -> str:
        """降级报告"""
        report = f"""# 天线仿真分析报告

## 执行摘要
本次共处理 {stats.get('total', 0)} 个天线设计，合格 {stats.get('passed', 0)} 个，通过率 {stats.get('pass_rate', 0):.1f}%。

## 统计概览
| 指标 | 数值 |
|------|------|
| 总设计数 | {stats.get('total', 0)} |
| 合格数 | {stats.get('passed', 0)} |
| 不合格数 | {stats.get('total', 0) - stats.get('passed', 0)} |
| 最佳S11 | {stats.get('s11_best', 'N/A')} dB |
| 平均S11 | {stats.get('s11_avg', 'N/A')} dB |

## 详细结果
"""
        for r in all_results[:10]:
            report += f"\n### {r.get('project_name', 'Unknown')}\n"
            report += f"- S11: {r.get('s11_min_db', 'N/A')} dB\n"
            report += f"- 判定: {'✅ 合格' if r.get('is_pass') else '❌ 不合格'}\n"

        return report


class SParamAnalyzer:
    """S参数分析器（整合CSV分析、多频分析和LLM诊断）"""

    def __init__(self, lm_studio_url: str = "http://localhost:1234",
                 model_name: str = None,
                 enable_llm: bool = True):
        """
        初始化分析器

        Args:
            lm_studio_url: LLM服务地址
            model_name: 模型名称
            enable_llm: 是否启用LLM智能诊断
        """
        self.csv_analyzer = CSVSParameterAnalyzer()
        self.enable_llm = enable_llm

        if enable_llm:
            self.llm_advisor = LLMAdvisor(
                api_url=f"{lm_studio_url}/v1" if not lm_studio_url.endswith('/v1') else lm_studio_url,
                model_name=model_name or "qwen2.5-7b-instruct",
                enabled=True
            )
        else:
            self.llm_advisor = None

        print(f"✅ S参数分析器初始化完成 (LLM诊断: {'启用' if enable_llm else '禁用'})")

    def analyze(self, file_path: str, use_ai: bool = True,
                threshold_db: float = -10) -> Dict[str, Any]:
        """
        分析S参数文件（支持CSV格式）

        Args:
            file_path: CSV文件路径
            use_ai: 是否使用LLM生成诊断
            threshold_db: S11阈值

        Returns:
            分析结果字典
        """
        # 1. CSV数值分析（精确计算）
        if file_path.lower().endswith('.csv'):
            result = self.csv_analyzer.analyze_csv_file(file_path, threshold_db)
            result['file_path'] = file_path
            result['file_name'] = os.path.basename(file_path)

            # 2. LLM智能诊断（可选）
            if use_ai and self.enable_llm and self.llm_advisor and result.get('is_pass') is not None:
                diagnosis = self.llm_advisor.generate_diagnosis(result)
                result['llm_diagnosis'] = diagnosis
                result['method'] = 'csv_with_llm_diagnosis'
            else:
                result['method'] = 'csv_numerical_analysis'

            return result
        else:
            return {
                'error': f'不支持的文件格式: {file_path}，请使用CSV格式',
                'is_pass': False,
                'method': 'error'
            }

    def analyze_multi_freq(self, file_path: str,
                           target_freqs: Dict[str, float],
                           threshold_db: float = -10,
                           use_ai: bool = True) -> Dict[str, Any]:
        """
        多频点分析

        Args:
            file_path: CSV文件路径
            target_freqs: 目标频点字典
            threshold_db: S11阈值
            use_ai: 是否使用AI诊断

        Returns:
            包含多频点分析结果的字典
        """
        if not file_path.lower().endswith('.csv'):
            return {'error': '不支持的格式', 'is_pass': False}

        csv_data = self.csv_analyzer.parse_csv(file_path)
        if csv_data is None or csv_data['s11'] is None:
            return {'error': 'CSV解析失败', 'is_pass': False}

        # 全频段分析
        full_analysis = self.csv_analyzer.analyze_s11(
            csv_data['frequencies'], csv_data['s11'], threshold_db
        )

        # 多频点分析
        multi_analysis = analyze_multi_band(
            csv_data['frequencies'],
            csv_data['s11'],
            target_freqs,
            threshold_db
        )

        result = {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'full_band': {
                's11_min_db': full_analysis.s11_min_db if full_analysis else None,
                'frequency_at_min_ghz': full_analysis.frequency_at_min_ghz if full_analysis else None,
                'bandwidth_under_10db_ghz': full_analysis.bandwidth_under_10db_ghz if full_analysis else None,
            },
            'bands': multi_analysis.bands_analysis,
            'is_pass': multi_analysis.is_pass,
            'overall_score': multi_analysis.overall_score,
            'method': 'multi_freq_analysis',
        }

        # LLM诊断
        if use_ai and self.enable_llm and self.llm_advisor:
            diagnosis = self.llm_advisor.generate_multi_band_diagnosis(result)
            result['llm_diagnosis'] = diagnosis
            result['method'] = 'multi_freq_with_llm'

        return result

    def batch_analyze(self, file_paths: list, use_ai: bool = True,
                      threshold_db: float = -10) -> list:
        """批量分析文件"""
        results = []
        for file_path in file_paths:
            result = self.analyze(file_path, use_ai, threshold_db)
            result['file'] = str(file_path)
            results.append(result)
        return results

    def generate_summary_report(self, results: List[Dict[str, Any]],
                                output_path: str = None) -> str:
        """生成汇总报告"""
        total = len(results)
        passed = sum(1 for r in results if r.get('is_pass', False))
        s11_values = [r['s11_min_db'] for r in results if r.get('s11_min_db') is not None]

        stats = {
            'total': total,
            'passed': passed,
            'failed': total - passed,
            'pass_rate': passed / total * 100 if total > 0 else 0,
            's11_best': min(s11_values) if s11_values else None,
            's11_worst': max(s11_values) if s11_values else None,
            's11_avg': sum(s11_values) / len(s11_values) if s11_values else None
        }

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': str(Path(output_path).stat().st_ctime),
                    'statistics': stats,
                    'results': results
                }, f, ensure_ascii=False, indent=2, default=str)

            html_path = output_path.replace('.json', '.html') if output_path else None
            if html_path:
                self._generate_html_report(results, stats, html_path)

        report = ""
        if self.enable_llm and self.llm_advisor:
            report = self.llm_advisor.generate_report(results, stats)

        return report

    def _generate_html_report(self, results: List[Dict], stats: Dict, output_path: str):
        """生成HTML报告"""
        import datetime
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>天线仿真分析报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #0a0a1a; color: #c0d0e0; }}
        h1 {{ color: #00ccff; border-bottom: 3px solid #2196F3; }}
        h2 {{ color: #00ccff; margin-top: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: linear-gradient(135deg, #003366 0%, #0066cc 100%); 
                      color: white; padding: 20px; border-radius: 10px; text-align: center; }}
        .stat-value {{ font-size: 32px; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #1a3a5c; }}
        th {{ background: #2196F3; color: white; }}
        .pass {{ color: #00ff88; font-weight: bold; }}
        .fail {{ color: #ff3366; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>📡 天线仿真分析报告</h1>

    <div class="stats">
        <div class="stat-card"><div class="stat-value">{stats['total']}</div><div>总设计数</div></div>
        <div class="stat-card"><div class="stat-value">{stats['passed']}</div><div>合格设计</div></div>
        <div class="stat-card"><div class="stat-value">{stats['failed']}</div><div>不合格设计</div></div>
        <div class="stat-card"><div class="stat-value">{stats['pass_rate']:.1f}%</div><div>通过率</div></div>
    </div>

    <h2>详细结果</h2>
    <table>
        <thead>
            <tr><th>设计名称</th><th>S11最小值(dB)</th><th>-10dB带宽(GHz)</th><th>中心频率(GHz)</th><th>Q值</th><th>判定</th></tr>
        </thead>
        <tbody>
"""
        for r in results:
            s11 = r.get('s11_min_db', 'N/A')
            bw = r.get('bandwidth_under_10db_ghz', 'N/A')
            center = r.get('center_frequency_ghz', 'N/A')
            q = r.get('q_value', 'N/A')
            is_pass = r.get('is_pass', False)
            pass_class = "pass" if is_pass else "fail"
            pass_text = "✅ 合格" if is_pass else "❌ 不合格"

            html += f"""
            <tr>
                <td>{r.get('file_name', 'N/A')}</td>
                <td>{s11}</td>
                <td>{bw}</td>
                <td>{center}</td>
                <td>{q}</td>
                <td class="{pass_class}">{pass_text}</td>
            </tr>"""

        html += f"""
        </tbody>
    </table>
    <p style="text-align: center; margin-top: 20px;">报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</body>
</html>"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)


# 测试代码
if __name__ == "__main__":
    import numpy as np

    test_csv = "test_s11.csv"
    freqs = np.linspace(1.0, 6.0, 501)
    # 模拟双频响应
    s11 = -5 - 15 * np.exp(-((freqs - 2.45) / 0.05) ** 2) - 12 * np.exp(-((freqs - 5.0) / 0.08) ** 2)

    with open(test_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Freq', 'S(1,1)'])
        for freq, s in zip(freqs, s11):
            writer.writerow([f"{freq:.6f}", f"{s:.6f}"])

    # 测试多频分析
    analyzer = SParamAnalyzer(enable_llm=False)
    target_freqs = {"2.45GHz": 2.45, "5GHz": 5.0}
    result = analyzer.analyze_multi_freq(test_csv, target_freqs, threshold_db=-10)

    print("\n📊 多频分析结果:")
    for band_name, info in result['bands'].items():
        print(
            f"  {band_name}: S11={info['s11_at_target']}dB, 频偏={info['freq_error_mhz']}MHz, {'✅' if info['is_pass'] else '❌'}")
    print(f"  总分: {result['overall_score']:.2f}")

    os.remove(test_csv)