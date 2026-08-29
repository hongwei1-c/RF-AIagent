#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天线设计知识库 - 完整版
支持任意频率，动态计算介质板尺寸
支持双频天线
"""

import math
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass, field


@dataclass
class SubstrateMaterial:
    """介质板材料参数"""
    name: str
    epsilon_r: float
    loss_tangent: float
    thickness: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'epsilon_r': self.epsilon_r,
            'loss_tangent': self.loss_tangent,
            'thickness': self.thickness
        }


MATERIAL_LIBRARY = {
    'FR4': SubstrateMaterial('FR4', 4.4, 0.02, 1.6),
    'RO4350B': SubstrateMaterial('RO4350B', 3.48, 0.0037, 1.524),
    'RO4003C': SubstrateMaterial('RO4003C', 3.38, 0.0027, 0.813),
    'RT5880': SubstrateMaterial('RT5880', 2.2, 0.0009, 0.787),
}

# 单频经验参数表（作为物理计算的参考基准）
RELIABLE_PARAMS_TABLE = {
    ('FR4', 2.0): {'l': 45.0, 'w': 55.0, 'w0': 80.0, 'l0': 100.0, 'w1': 3.0, 'w2': 1.5, 'd2': 22.0, 'd1': 28.0},
    ('FR4', 2.4): {'l': 38.5, 'w': 45.0, 'w0': 70.0, 'l0': 85.0, 'w1': 3.0, 'w2': 1.25, 'd2': 19.0, 'd1': 28.0},
    ('FR4', 2.45): {'l': 37.7, 'w': 44.26, 'w0': 80.0, 'l0': 100.0, 'w1': 2.98, 'w2': 1.2, 'd2': 18.72, 'd1': 28.0},
    ('FR4', 5.0): {'l': 18.0, 'w': 21.5, 'w0': 36.0, 'l0': 43.0, 'w1': 3.0, 'w2': 0.6, 'd2': 8.5, 'd1': 14.0},
    ('FR4', 5.8): {'l': 15.5, 'w': 18.0, 'w0': 31.0, 'l0': 36.0, 'w1': 3.0, 'w2': 0.8, 'd2': 8.0, 'd1': 12.0},
    ('RO4350B', 2.45): {'l': 40.0, 'w': 48.0, 'w0': 80.0, 'l0': 100.0, 'w1': 3.3, 'w2': 1.3, 'd2': 20.0, 'd1': 28.0},
    ('RO4350B', 5.8): {'l': 16.5, 'w': 20.0, 'w0': 35.0, 'l0': 40.0, 'w1': 3.3, 'w2': 0.9, 'd2': 8.5, 'd1': 15.0},
}

# 双频经验参数表
# (材料, 低频, 高频): {L0, W0, l1, l2, H}
DUAL_FREQ_RELIABLE_PARAMS_TABLE = {
    ('FR4', 1.8, 2.45): {
        'L0': 38.0,  # 贴片长度 - 控制低频 (~1.8GHz)
        'W0': 48.0,  # 贴片宽度 - 控制高频 (~2.45GHz)
        'l1': 8.0,  # 馈电X偏移
        'l2': 12.0,  # 馈电Y偏移
        'H': 1.6,  # 介质厚度
    },
    ('FR4', 2.45, 5.0): {
        'L0': 27.9,  # 贴片长度 - 控制低频 (~2.45GHz)
        'W0': 40.0,  # 贴片宽度 - 控制高频 (~5GHz)
        'l1': 6.6,  # 馈电X偏移
        'l2': 10.0,  # 馈电Y偏移
        'H': 1.6,
    },
    ('FR4', 2.4, 5.2): {
        'L0': 28.5,
        'W0': 38.5,
        'l1': 6.8,
        'l2': 9.8,
        'H': 1.6,
    },
    ('FR4', 2.45, 5.8): {
        'L0': 27.5,
        'W0': 36.0,
        'l1': 6.5,
        'l2': 9.5,
        'H': 1.6,
    },
    ('FR4', 1.9, 2.45): {
        'L0': 36.0,
        'W0': 46.0,
        'l1': 7.5,
        'l2': 11.5,
        'H': 1.6,
    },
    ('RO4350B', 2.45, 5.0): {
        'L0': 30.0,
        'W0': 42.0,
        'l1': 7.0,
        'l2': 10.5,
        'H': 1.524,
    },
}


class AntennaKnowledgeBase:
    """天线设计知识库 - 单频"""

    C = 299792458000  # 光速 (mm/s)

    # 介质板尺寸比例因子（相对于贴片尺寸的倍数）
    SUBSTRATE_MARGIN_RATIO = 2.0

    ABSOLUTE_BOUNDS = {
        'l': (3.0, 150.0),
        'w': (5.0, 150.0),
        'w0': (10.0, 300.0),
        'l0': (15.0, 300.0),
        'w1': (0.3, 10.0),
        'w2': (0.1, 8.0),
        'd1': (5.0, 100.0),
        'd2': (2.0, 80.0),
    }

    def __init__(self, material: SubstrateMaterial = None, target_freq_ghz: float = 2.45):
        self.material = material or MATERIAL_LIBRARY['FR4']
        self.material_name = self.material.name
        self.target_freq = max(0.5, min(10.0, target_freq_ghz))

        self._use_table = (self.material_name, self.target_freq) in RELIABLE_PARAMS_TABLE
        if self._use_table:
            print(f"  📚 使用经验参数表: {self.material_name} @ {self.target_freq}GHz")
        else:
            print(f"  🔬 使用物理公式计算: {self.material_name} @ {self.target_freq}GHz")

        self._update_derived_params()

    def _update_derived_params(self):
        w_guess = self._estimate_width_safe()
        self.epsilon_eff = self._calc_effective_epsilon_safe(
            self.material.epsilon_r, self.material.thickness, w_guess
        )
        freq_hz = self.target_freq * 1e9
        self.lambda_0 = self.C / freq_hz
        if self.epsilon_eff > 1.0:
            self.lambda_g = self.lambda_0 / math.sqrt(self.epsilon_eff)
        else:
            self.lambda_g = self.lambda_0 / math.sqrt(self.material.epsilon_r)

    def _clamp(self, value: float, key: str) -> float:
        if key in self.ABSOLUTE_BOUNDS:
            low, high = self.ABSOLUTE_BOUNDS[key]
            return max(low, min(high, value))
        return max(0.1, value)

    def _calc_effective_epsilon_safe(self, er: float, h: float, w: float) -> float:
        if w <= 0 or h <= 0:
            return er
        try:
            ratio = w / h
            term = (1 + 12 / ratio) ** -0.5
            result = (er + 1) / 2 + (er - 1) / 2 * term
            return max(1.0, min(er, result))
        except:
            return er

    def _estimate_width_safe(self) -> float:
        try:
            freq_hz = self.target_freq * 1e9
            w = self.C / (2 * freq_hz) * math.sqrt(2 / (self.material.epsilon_r + 1))
            return self._clamp(w, 'w')
        except:
            return 44.0

    def _calc_substrate_dimensions(self, l: float, w: float, d1: float, d2: float) -> Tuple[float, float]:
        w0 = max(15.0, w * self.SUBSTRATE_MARGIN_RATIO)
        l0 = max(20.0, (l + d1 + d2) * 1.5)
        w0 = round(w0 * 2) / 2
        l0 = round(l0 * 2) / 2
        return self._clamp(w0, 'w0'), self._clamp(l0, 'l0')

    def get_initial_guess(self) -> Dict[str, float]:
        """获取初始设计参数（支持任意频率）"""
        key = (self.material_name, self.target_freq)

        # 1. 精确匹配经验表
        if key in RELIABLE_PARAMS_TABLE:
            return self._validate_params(RELIABLE_PARAMS_TABLE[key].copy())

        # 2. 同材料最接近频率缩放
        closest_key = self._find_closest_freq()
        if closest_key:
            base = RELIABLE_PARAMS_TABLE[closest_key].copy()
            scale = closest_key[1] / self.target_freq

            base['l'] = round(base['l'] * scale, 2)
            base['w'] = round(base['w'] * scale, 2)
            base['d2'] = round(base['d2'] * scale, 2)
            base['d1'] = max(10.0, round(base['d1'] * scale, 2))

            w0, l0 = self._calc_substrate_dimensions(base['l'], base['w'], base['d1'], base['d2'])
            base['w0'] = w0
            base['l0'] = l0

            print(f"  📐 从 {closest_key[1]}GHz 按比例缩放 (scale={scale:.3f})")
            return self._validate_params(base)

        # 3. 物理公式计算
        l = self._calc_patch_length_safe()
        w = self._calc_patch_width_safe()
        w1 = self._calc_feed_width_50ohm_safe()
        w2, d2 = self._calc_transformer_safe()
        d1 = max(10.0, self.lambda_g * 0.3)
        w0, l0 = self._calc_substrate_dimensions(l, w, d1, d2)

        return self._validate_params({
            'l': l, 'w': w, 'w0': w0, 'l0': l0,
            'w1': w1, 'w2': w2, 'd2': d2, 'd1': d1,
        })

    def _find_closest_freq(self) -> Optional[Tuple]:
        """找到最接近目标频率的经验参数"""
        best_key = None
        best_diff = float('inf')
        for k in RELIABLE_PARAMS_TABLE:
            if k[0] == self.material_name:
                diff = abs(k[1] - self.target_freq)
                if diff < best_diff:
                    best_diff = diff
                    best_key = k
        return best_key

    def _validate_params(self, params: Dict) -> Dict:
        validated = {}
        for key, value in params.items():
            validated[key] = self._clamp(value, key)
        return validated

    def _calc_patch_width_safe(self) -> float:
        try:
            freq_hz = self.target_freq * 1e9
            w = self.C / (2 * freq_hz) * math.sqrt(2 / (self.material.epsilon_r + 1))
            return self._clamp(w, 'w')
        except:
            return 44.0

    def _calc_patch_length_safe(self) -> float:
        try:
            h = self.material.thickness
            er = self.material.epsilon_r
            w = self._calc_patch_width_safe()
            epsilon_eff = self._calc_effective_epsilon_safe(er, h, w)
            delta_L = 0.412 * h * ((epsilon_eff + 0.3) * (w / h + 0.264)) / \
                      ((epsilon_eff - 0.258) * (w / h + 0.8) + 1e-9)
            freq_hz = self.target_freq * 1e9
            L = self.C / (2 * freq_hz * math.sqrt(max(1.0, epsilon_eff))) - 2 * delta_L
            return self._clamp(L, 'l')
        except:
            return 37.0

    def _calc_feed_width_50ohm_safe(self) -> float:
        try:
            er = self.material.epsilon_r
            h = self.material.thickness
            A = 50 / 60 * math.sqrt((er + 1) / 2) + (er - 1) / (er + 1) * (0.23 + 0.11 / er)
            if A > 1.52:
                w_h = 8 * math.exp(A) / (math.exp(2 * A) - 2 + 1e-9)
            else:
                B = 377 * math.pi / (2 * 50 * math.sqrt(er))
                w_h = 2 / math.pi * (B - 1 - math.log(2 * B - 1 + 1e-9) +
                                     (er - 1) / (2 * er) * (math.log(B - 1 + 1e-9) + 0.39 - 0.61 / er))
            return self._clamp(w_h * h, 'w1')
        except:
            return 3.0

    def _calc_transformer_safe(self) -> Tuple[float, float]:
        try:
            Z_in = 200
            Z_0 = 50
            Z_t = math.sqrt(Z_in * Z_0)
            er = self.material.epsilon_r
            h = self.material.thickness

            if Z_t <= (44 - 2 * er):
                w_h = 8 * math.exp((Z_t * math.sqrt(er + 1.41)) / 87) / \
                      (math.exp((Z_t * math.sqrt(er + 1.41)) / 42) - 2 + 1e-9)
            else:
                w_h = 2 / math.pi * ((377 * math.pi) / (2 * Z_t * math.sqrt(er)) - 1 -
                                     math.log((377 * math.pi) / (Z_t * math.sqrt(er)) - 1 + 1e-9))

            w2 = self._clamp(w_h * h, 'w2')
            d2 = self._clamp(self.lambda_g / 4, 'd2')
            return w2, d2
        except:
            return 1.2, 18.0

    def get_parameter_bounds(self) -> Dict[str, Tuple[float, float]]:
        guess = self.get_initial_guess()
        bounds = {}
        ratios = {'l': 0.25, 'w': 0.30, 'w0': 0.20, 'l0': 0.20,
                  'w1': 0.30, 'w2': 0.50, 'd2': 0.25}
        for key, ratio in ratios.items():
            center = guess.get(key, 10.0)
            if center <= 0:
                center = 10.0
            half_range = center * ratio
            low = max(center - half_range, self.ABSOLUTE_BOUNDS[key][0])
            high = min(center + half_range, self.ABSOLUTE_BOUNDS[key][1])
            bounds[key] = (round(low, 2), round(high, 2))
        return bounds

    def get_tuning_guidance(self) -> str:
        guess = self.get_initial_guess()
        return f"""
【天线设计知识库】
目标: {self.target_freq} GHz | 材料: {self.material_name} (εr={self.material.epsilon_r}, h={self.material.thickness}mm)

【推荐初始参数】
  贴片: l={guess['l']:.2f}, w={guess['w']:.2f} mm
  介质板: w0={guess['w0']:.2f}, l0={guess['l0']:.2f} mm
  馈线: w1={guess['w1']:.2f}, d1={guess['d1']:.2f} mm
  变换器: w2={guess['w2']:.2f}, d2={guess['d2']:.2f} mm

【调参规律】
  频率偏移 → 调整 l 和 w
  匹配不佳 → 调整 d2 和 w1
  带宽不足 → 增加 w
"""

    def suggest_l_adjustment(self, current_freq_ghz: float) -> float:
        if current_freq_ghz <= 0:
            return 0.0
        freq_error = current_freq_ghz - self.target_freq
        if abs(freq_error) < 0.01:
            return 0.0
        l_current = self.get_initial_guess()['l']
        return l_current * freq_error * 0.3


class DualBandAntennaKnowledgeBase:
    """双频天线知识库"""

    C = 299792458  # mm/s

    def __init__(self, material: SubstrateMaterial = None,
                 target_freqs: List[float] = None):
        self.material = material or MATERIAL_LIBRARY['FR4']
        self.material_name = self.material.name
        self.target_freq_low = target_freqs[0] if target_freqs else 2.45
        self.target_freq_high = target_freqs[1] if target_freqs else 5.0

        # 计算介质参数
        self._calc_substrate_params()

        print(f"  📚 双频知识库: {self.material_name} @ {self.target_freq_low}/{self.target_freq_high}GHz")

    def _calc_substrate_params(self):
        """计算介质基板相关参数"""
        freq_hz_low = self.target_freq_low * 1e9
        freq_hz_high = self.target_freq_high * 1e9

        # 有效介电常数估算 (微带线)
        w_guess = 40.0  # mm
        self.epsilon_eff = self._calc_effective_epsilon(
            self.material.epsilon_r,
            self.material.thickness,
            w_guess
        )

        # 波长
        self.lambda_g_low = self.C / (freq_hz_low * math.sqrt(self.epsilon_eff))
        self.lambda_g_high = self.C / (freq_hz_high * math.sqrt(self.epsilon_eff))

    def _calc_effective_epsilon(self, er: float, h: float, w: float) -> float:
        """计算有效介电常数"""
        if w <= 0 or h <= 0:
            return er
        try:
            ratio = w / h
            if ratio < 1:
                return (er + 1) / 2 + (er - 1) / 2 * (
                        1 / math.sqrt(1 + 12 * h / w) + 0.04 * (1 - w / h) ** 2
                )
            else:
                return (er + 1) / 2 + (er - 1) / 2 / math.sqrt(1 + 12 * h / w)
        except:
            return er

    def get_initial_guess(self) -> Dict[str, float]:
        """获取双频天线初始参数"""
        key = (self.material_name, self.target_freq_low, self.target_freq_high)
        if key in DUAL_FREQ_RELIABLE_PARAMS_TABLE:
            base = DUAL_FREQ_RELIABLE_PARAMS_TABLE[key].copy()
            # 补充 Ls, Ws
            if 'Ls' not in base:
                base['Ls'] = base.get('L0', 27.9) * 2.8
            if 'Ws' not in base:
                base['Ws'] = base.get('W0', 40.0) * 2.8
            return base
        closest = self._find_closest()
        if closest:
            base = DUAL_FREQ_RELIABLE_PARAMS_TABLE[closest].copy()
            scale_low = closest[1] / self.target_freq_low
            scale_high = closest[2] / self.target_freq_high
            base['L0'] = round(base['L0'] * scale_low, 2)
            base['W0'] = round(base['W0'] * scale_high, 2)
            base['l1'] = round(base['l1'] * ((scale_low + scale_high) / 2), 2)
            base['l2'] = round(base['l2'] * ((scale_low + scale_high) / 2), 2)
            # 补充 Ls, Ws
            avg_scale = (scale_low + scale_high) / 2
            base['Ls'] = round(base.get('Ls', base['L0'] * 2.8) * avg_scale, 1)
            base['Ws'] = round(base.get('Ws', base['W0'] * 2.8) * avg_scale, 1)
            return base
        # 物理公式计算
        return self._physical_initial_guess()

    def _physical_initial_guess(self) -> Dict[str, float]:
        L0 = self.C / (2 * self.target_freq_low * 1e9 * math.sqrt(self.epsilon_eff))
        W0_from_high = self.C / (2 * self.target_freq_high * 1e9 * math.sqrt(self.epsilon_eff))
        W0 = max(L0 * 1.2, W0_from_high * 1.1)
        l1 = L0 * 0.3
        l2 = W0 * 0.25
        Ls = L0 * 2.8  # 新增
        Ws = W0 * 2.8  # 新增
        # 边界裁剪
        L0 = max(15.0, min(80.0, L0))
        W0 = max(20.0, min(100.0, W0))
        l1 = max(3.0, min(25.0, l1))
        l2 = max(4.0, min(30.0, l2))
        Ls = max(40.0, min(200.0, Ls))
        Ws = max(50.0, min(250.0, Ws))
        return {
            'L0': round(L0, 2), 'W0': round(W0, 2),
            'l1': round(l1, 2), 'l2': round(l2, 2),
            'Ls': round(Ls, 1), 'Ws': round(Ws, 1),
            'H': self.material.thickness,
        }

    def _find_closest(self):
        """找到最接近的已知设计"""
        best_key = None
        best_diff = float('inf')
        for key in DUAL_FREQ_RELIABLE_PARAMS_TABLE:
            if key[0] == self.material_name:
                diff = abs(key[1] - self.target_freq_low) + abs(key[2] - self.target_freq_high)
                if diff < best_diff:
                    best_diff = diff
                    best_key = key
        return best_key

    def get_tuning_guidance(self, low_analysis: Dict = None, high_analysis: Dict = None) -> str:
        """生成调参指导"""
        guidance = f"""
【双频天线调参指南】- {self.material_name}

物理规律:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  L0 (贴片长度) → 控制低频谐振频率
  W0 (贴片宽度) → 控制高频谐振频率
  l1 (馈电X偏移) → 影响匹配和双频平衡
  l2 (馈电Y偏移) → 影响输入阻抗

频率调整:
  - 低频偏低: ↑ L0 (增加长度)
  - 低频偏高: ↓ L0 (减小长度)
  - 高频偏低: ↑ W0 (增加宽度)  
  - 高频偏高: ↓ W0 (减小宽度)

匹配调整:
  - 双频不平衡: 调整 l1 (靠近中心 → 双频更平衡)
  - S11较差: 调整 l2 (改变输入阻抗)
  - 带宽不足: 增加 W0/L0 比例

经验公式:
  L0 ≈ 300/(2*f_low*√ε_eff) mm
  W0 ≈ 1.2~1.5 * L0
  l1 ≈ 0.3*L0, l2 ≈ 0.25*W0

当前推荐初始值:
  L0 = {self.get_initial_guess().get('L0', 30):.2f} mm
  W0 = {self.get_initial_guess().get('W0', 40):.2f} mm
  l1 = {self.get_initial_guess().get('l1', 8):.2f} mm
  l2 = {self.get_initial_guess().get('l2', 10):.2f} mm
"""
        return guidance

    def get_parameter_bounds(self) -> Dict[str, Tuple[float, float]]:
        """获取参数边界"""
        guess = self.get_initial_guess()
        return {
            'L0': (max(15.0, guess['L0'] * 0.7), min(80.0, guess['L0'] * 1.3)),
            'W0': (max(20.0, guess['W0'] * 0.7), min(100.0, guess['W0'] * 1.3)),
            'l1': (max(2.0, guess['l1'] * 0.5), min(25.0, guess['l1'] * 1.5)),
            'l2': (max(3.0, guess['l2'] * 0.5), min(30.0, guess['l2'] * 1.5)),
            'H': (self.material.thickness, self.material.thickness),  # 固定
            'Ls': (max(40.0, guess.get('Ls', 40) * 0.7), min(150.0, guess.get('Ls', 40) * 1.3)),
            'Ws': (max(50.0, guess.get('Ws', 50) * 0.7), min(200.0, guess.get('Ws', 80) * 1.3)),
        }


def create_knowledge_base(material_name: str = 'FR4',
                          target_freq_ghz: float = 2.45) -> AntennaKnowledgeBase:
    material = MATERIAL_LIBRARY.get(material_name, MATERIAL_LIBRARY['FR4'])
    return AntennaKnowledgeBase(material, target_freq_ghz)


def create_dual_band_knowledge_base(material_name: str = 'FR4',
                                    target_freqs: List[float] = None) -> DualBandAntennaKnowledgeBase:
    material = MATERIAL_LIBRARY.get(material_name, MATERIAL_LIBRARY['FR4'])
    return DualBandAntennaKnowledgeBase(material, target_freqs)