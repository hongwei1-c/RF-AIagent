#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传输线分析模块
"""

import os
import csv
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TLineAnalysisResult:
    """传输线分析结果"""
    s11_min_db: float = None
    s11_freq_ghz: float = None
    s21_min_db: float = None
    bandwidth_10db_ghz: float = None
    characteristic_impedance: float = None
    tdr_impedance_avg: float = None
    is_pass: bool = False
    threshold_db: float = -10


class TLineAnalyzer:
    """传输线分析器"""

    def __init__(self, target_impedance: float = 50.0):
        self.target_impedance = target_impedance

    def parse_s_params_csv(self, csv_path: str) -> Dict[str, Any]:
        """解析S参数CSV"""
        if not os.path.exists(csv_path):
            return None

        try:
            frequencies = []
            s11_db = []
            s21_db = []

            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)

                freq_idx = 0
                s11_idx = None
                s21_idx = None

                for i, col in enumerate(header):
                    col_lower = col.lower()
                    if 'freq' in col_lower:
                        freq_idx = i
                    elif 's(1,1)' in col_lower or 's11' in col_lower:
                        s11_idx = i
                    elif 's(2,1)' in col_lower or 's21' in col_lower:
                        s21_idx = i

                for row in reader:
                    if not row:
                        continue
                    try:
                        frequencies.append(float(row[freq_idx].strip()))
                        if s11_idx is not None:
                            s11_db.append(float(row[s11_idx].strip()))
                        if s21_idx is not None:
                            s21_db.append(float(row[s21_idx].strip()))
                    except:
                        continue

            return {
                'frequencies': np.array(frequencies),
                's11_db': np.array(s11_db) if s11_db else None,
                's21_db': np.array(s21_db) if s21_db else None
            }
        except Exception as e:
            print(f"解析S参数失败: {e}")
            return None

    def parse_tdr_csv(self, csv_path: str) -> Dict[str, Any]:
        """解析TDR CSV"""
        if not os.path.exists(csv_path):
            return None

        try:
            times = []
            impedances = []

            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)

                time_idx = 0
                imp_idx = None

                for i, col in enumerate(header):
                    col_lower = col.lower()
                    if 'time' in col_lower:
                        time_idx = i
                    elif 'tdrzt' in col_lower or 'impedance' in col_lower:
                        imp_idx = i

                for row in reader:
                    if not row:
                        continue
                    try:
                        times.append(float(row[time_idx].strip()))
                        if imp_idx is not None:
                            impedances.append(float(row[imp_idx].strip()))
                    except:
                        continue

            return {
                'times': np.array(times),
                'impedances': np.array(impedances) if impedances else None
            }
        except Exception as e:
            print(f"解析TDR失败: {e}")
            return None

    def analyze(self, s_params_csv: str = None, tdr_csv: str = None,
                threshold_db: float = -10) -> TLineAnalysisResult:
        """综合分析"""
        result = TLineAnalysisResult(threshold_db=threshold_db)

        if s_params_csv and os.path.exists(s_params_csv):
            data = self.parse_s_params_csv(s_params_csv)
            if data and data['s11_db'] is not None:
                s11 = data['s11_db']
                freqs = data['frequencies']

                min_idx = np.argmin(s11)
                result.s11_min_db = float(s11[min_idx])
                result.s11_freq_ghz = float(freqs[min_idx])

                if data['s21_db'] is not None:
                    result.s21_min_db = float(np.min(data['s21_db']))

                # 计算-10dB带宽
                below = s11 <= threshold_db
                total_bw = 0.0
                in_range = False
                start = None
                for i, b in enumerate(below):
                    if b and not in_range:
                        in_range = True
                        start = freqs[i]
                    elif not b and in_range:
                        in_range = False
                        total_bw += freqs[i - 1] - start
                if in_range:
                    total_bw += freqs[-1] - start
                result.bandwidth_10db_ghz = total_bw
                result.is_pass = result.s11_min_db <= threshold_db

        if tdr_csv and os.path.exists(tdr_csv):
            data = self.parse_tdr_csv(tdr_csv)
            if data and data['impedances'] is not None:
                imps = data['impedances']
                valid = imps[np.isfinite(imps)]
                if len(valid) > 10:
                    start = int(len(valid) * 0.1)
                    end = int(len(valid) * 0.9)
                    core = valid[start:end]
                    result.tdr_impedance_avg = float(np.mean(core))
                    result.characteristic_impedance = result.tdr_impedance_avg

        return result