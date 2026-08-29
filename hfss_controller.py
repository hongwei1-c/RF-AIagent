#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HFSS 控制器 - 多器件支持版
支持：单频天线、双频天线、滤波器、功分器
自动根据器件类型适配参数映射
"""

import os
import sys
import time
from config import HFSS_TEMPLATE_PROJECT, HFSS_CSV_OUTPUT, HFSS_RUNS
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from hfss_automation import HFSSAutomation


class HFSSController:
    """HFSS 仿真控制器 - 多器件支持版"""

    # ===== 不同器件的变量映射表 =====
    DEVICE_VAR_MAP = {
        "微带贴片天线": [
            ('l', 'l'),
            ('w', 'w'),
            ('w0', 'w0'),
            ('l0', 'l0'),
            ('w1', 'w1'),
            ('w2', 'w2'),
            ('d2', 'd2'),
            ('d1', 'd1'),
        ],
        "缝隙天线": [
            ('slot_l', 'slot_l'),
            ('slot_w', 'slot_w'),
            ('patch_l', 'patch_l'),
            ('patch_w', 'patch_w'),
            ('w0', 'w0'),
            ('l0', 'l0'),
            ('feed_w', 'feed_w'),
            ('feed_offset', 'feed_offset'),
        ],
        "PIFA天线": [
            ('patch_l', 'patch_l'),
            ('patch_w', 'patch_w'),
            ('patch_h', 'patch_h'),
            ('short_w', 'short_w'),
            ('feed_x', 'feed_x'),
            ('ground_l', 'ground_l'),
            ('ground_w', 'ground_w'),
        ],
        "双频微带天线": [
            ('L0', 'L0'),
            ('W0', 'W0'),
            ('l1', 'L1'),
            ('l2', 'L2'),
            ('Ls', 'Ls'),
            ('Ws', 'Ws'),
            ('H', 'H'),
        ],
        "双频缝隙天线": [
            ('slot1_l', 'slot1_l'),
            ('slot1_w', 'slot1_w'),
            ('slot2_l', 'slot2_l'),
            ('slot2_w', 'slot2_w'),
            ('spacing', 'spacing'),
            ('w0', 'w0'),
            ('l0', 'l0'),
        ],
        "微带带通滤波器": [
            ('cl1', 'cl1'),
            ('cw1', 'cw1'),
            ('cl2', 'cl2'),
            ('cw2', 'cw2'),
            ('cl3', 'cl3'),
            ('cw3', 'cw3'),
            ('gap1', 'gap1'),
            ('gap2', 'gap2'),
            ('feed_w', 'feed_w'),
        ],
        "微带低通滤波器": [
            ('high_z_l', 'high_z_l'),
            ('high_z_w', 'high_z_w'),
            ('low_z_l', 'low_z_l'),
            ('low_z_w', 'low_z_w'),
            ('stages', 'stages'),
            ('feed_w', 'feed_w'),
        ],
        "微带高通滤波器": [
            ('cap_l', 'cap_l'),
            ('cap_w', 'cap_w'),
            ('ind_l', 'ind_l'),
            ('ind_w', 'ind_w'),
            ('stages', 'stages'),
            ('feed_w', 'feed_w'),
        ],
        "Wilkinson功分器": [
            ('branch_l', 'branch_l'),
            ('branch_w', 'branch_w'),
            ('feed_w', 'feed_w'),
            ('resistor', 'resistor'),
            ('angle', 'angle'),
            ('w0', 'w0'),
            ('l0', 'l0'),
        ],
        "T型功分器": [
            ('branch_l', 'branch_l'),
            ('branch_w', 'branch_w'),
            ('feed_w', 'feed_w'),
            ('w0', 'w0'),
            ('l0', 'l0'),
        ],
    }

    # ===== 不同器件的默认参数 =====
    DEVICE_DEFAULT_PARAMS = {
        "微带贴片天线": {
            'l': 37.7, 'w': 44.26, 'w0': 80.0, 'l0': 100.0,
            'w1': 2.98, 'w2': 1.2, 'd2': 18.72, 'd1': 28.0,
        },
        "缝隙天线": {
            'slot_l': 30.0, 'slot_w': 2.0, 'patch_l': 40.0, 'patch_w': 50.0,
            'w0': 80.0, 'l0': 100.0, 'feed_w': 3.0, 'feed_offset': 10.0,
        },
        "PIFA天线": {
            'patch_l': 20.0, 'patch_w': 20.0, 'patch_h': 8.0,
            'short_w': 5.0, 'feed_x': 5.0, 'ground_l': 80.0, 'ground_w': 80.0,
        },
        "双频微带天线": {
            'L0': 27.9,
            'W0': 40.0,
            'Ls': 80,
            'Ws': 100,
            'l1': 6.6,
            'l2': 10.0,
            'H': 1.6,
        },
        "双频缝隙天线": {
            'slot1_l': 30.0, 'slot1_w': 2.0, 'slot2_l': 15.0, 'slot2_w': 1.5,
            'spacing': 10.0, 'w0': 80.0, 'l0': 100.0,
        },
        "微带带通滤波器": {
            'cl1': 15.0, 'cw1': 2.0, 'cl2': 15.0, 'cw2': 2.0,
            'cl3': 15.0, 'cw3': 2.0, 'gap1': 0.5, 'gap2': 0.5,
            'feed_w': 3.0,
        },
        "微带低通滤波器": {
            'high_z_l': 10.0, 'high_z_w': 0.5, 'low_z_l': 10.0, 'low_z_w': 5.0,
            'stages': 5, 'feed_w': 3.0,
        },
        "微带高通滤波器": {
            'cap_l': 10.0, 'cap_w': 5.0, 'ind_l': 10.0, 'ind_w': 0.5,
            'stages': 3, 'feed_w': 3.0,
        },
        "Wilkinson功分器": {
            'branch_l': 18.0, 'branch_w': 1.5, 'feed_w': 3.0,
            'resistor': 100.0, 'angle': 90.0, 'w0': 60.0, 'l0': 60.0,
        },
        "T型功分器": {
            'branch_l': 18.0, 'branch_w': 1.5, 'feed_w': 3.0,
            'w0': 60.0, 'l0': 60.0,
        },
    }

    def __init__(self, work_dir: str = None,
                 template_project: str = None,
                 target_freq: float = 2.45,
                 device_type: str = "微带贴片天线"):
        if work_dir is None:
            work_dir = str(HFSS_RUNS)
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.template_project = template_project or str(HFSS_TEMPLATE_PROJECT)
        self.target_freq = target_freq
        self.device_type = device_type

    def _get_var_mapping(self):
        return self.DEVICE_VAR_MAP.get(self.device_type,
                                       self.DEVICE_VAR_MAP["微带贴片天线"])

    def get_default_params(self) -> Dict[str, float]:
        return self.DEVICE_DEFAULT_PARAMS.get(
            self.device_type,
            self.DEVICE_DEFAULT_PARAMS["微带贴片天线"]
        ).copy()

    def run_simulation(self, params: Dict[str, float], reuse_hfss=None, target_freqs: List[float] = None) -> Dict[
        str, Any]:
        """运行 HFSS 仿真，支持双频频点"""
        return self._run_with_existing_aedt(params, reuse_hfss, target_freqs)

    def _run_with_existing_aedt(self, params: Dict[str, float], reuse_hfss=None, target_freqs: List[float] = None) -> \
    Dict[str, Any]:
        result = {
            'success': False,
            'csv_path': None,
            'error': None,
            'params': params.copy()
        }

        if not os.path.exists(self.template_project):
            result['error'] = f"项目文件不存在: {self.template_project}"
            print(f"  ❌ {result['error']}")
            return result

        output_dir = str(HFSS_CSV_OUTPUT)
        os.makedirs(output_dir, exist_ok=True)
        csv_path = f"{output_dir}/s11_{datetime.now().strftime('%H%M%S')}.csv"

        print(f"  📂 项目: {Path(self.template_project).name}")
        print(f"  💾 输出: {csv_path}")

        param_str = ", ".join(f"{k}={v:.2f}" for k, v in params.items()
                              if k not in ['w0', 'l0', 'd1'])
        if 'w0' in params:
            param_str += f", w0={params['w0']:.1f}"
        if 'l0' in params:
            param_str += f", l0={params['l0']:.1f}"
        print(f"     参数: {param_str}")

        try:
            if reuse_hfss:
                hfss = reuse_hfss
                need_close_hfss = False
            else:
                hfss = HFSSAutomation(visible=True)
                if not hfss.start():
                    result['error'] = "启动 HFSS 失败"
                    return result
                need_close_hfss = True

            if not hfss.open_project(self.template_project):
                result['error'] = "打开项目失败"
                if need_close_hfss:
                    hfss.close_hfss()
                return result

            oDesign = hfss.oProject.GetActiveDesign()

            var_mapping = self._get_var_mapping()
            for param_key, var_name in var_mapping:
                if param_key in params:
                    value = params[param_key]
                    if isinstance(value, (int, float)) and value > 0 and value < 500:
                        try:
                            oDesign.ChangeProperty(
                                ["NAME:AllTabs",
                                 ["NAME:LocalVariableTab",
                                  ["NAME:PropServers", "LocalVariables"],
                                  ["NAME:ChangedProps",
                                   [f"NAME:{var_name}", "Value:=", f"{value}mm"]
                                   ]
                                  ]])
                            print(f"     ✓ {var_name} = {value} mm")
                        except Exception as e:
                            print(f"     ✗ 修改 {var_name} 失败: {e}")
                    else:
                        print(f"     ⚠️ 跳过无效值 {var_name} = {value}")

            # 传递双频频点
            self._update_solution_setup(oDesign, target_freqs)

            print(f"  🚀 运行仿真...")
            hfss.analyze_all()

            print(f"  ⏳ 等待仿真完成...")
            if not self._wait_for_analysis_complete(oDesign, timeout_seconds=120):
                print(f"  ⚠️ 仿真超时（120秒），继续尝试导出")
            else:
                print(f"  ✅ 仿真完成")

            success, exported_csv = hfss.export_s_parameters_csv(csv_path)

            if success and os.path.exists(exported_csv):
                result['csv_path'] = exported_csv
                result['success'] = True
                print(f"  ✅ 成功: {exported_csv}")
            else:
                result['error'] = "CSV导出失败"
                print(f"  ❌ {result['error']}")

            hfss.save_project()
            hfss.close_project()
            if need_close_hfss:
                hfss.close_hfss()

        except Exception as e:
            result['error'] = str(e)
            print(f"  ❌ 异常: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _wait_for_analysis_complete(self, oDesign, timeout_seconds=120):
        start = time.time()

        output_dir = str(HFSS_CSV_OUTPUT)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        initial_files = set(os.listdir(output_dir)) if os.path.exists(output_dir) else set()

        while time.time() - start < timeout_seconds:
            if os.path.exists(output_dir):
                current_files = set(os.listdir(output_dir))
                new_files = current_files - initial_files
                if any(f.endswith('.csv') for f in new_files):
                    time.sleep(2)
                    return True

            try:
                analysis = oDesign.GetModule("AnalysisSetup")
                if hasattr(analysis, 'IsSolving'):
                    if not analysis.IsSolving():
                        time.sleep(1)
                        return True
            except:
                pass

            time.sleep(1)

        return False

    def _update_solution_setup(self, oDesign, target_freqs: List[float] = None):
        """动态修改求解设置：扫频范围和求解频率（支持双频）"""
        try:
            oModule = oDesign.GetModule("AnalysisSetup")

            # 根据单频或双频设置扫频范围
            if target_freqs and len(target_freqs) >= 2:
                # 双频模式：扫频范围覆盖两个频点
                freq_low = min(target_freqs)
                freq_high = max(target_freqs)
                freq_start = max(0.5, freq_low - 1.0)
                freq_end = min(20.0, freq_high + 1.5)
                # 求解频率使用低频
                freq_solution = freq_low
                print(f"     📡 双频扫频范围: {freq_start:.2f} - {freq_end:.2f} GHz")
                print(f"     📡 双频目标: {freq_low}GHz / {freq_high}GHz")
            else:
                # 单频模式
                freq = self.target_freq
                if freq <= 2.0:
                    freq_start = max(0.1, freq - 1.0)
                    freq_end = freq + 1.5
                elif freq <= 4.0:
                    freq_start = max(0.5, freq - 2.0)
                    freq_end = freq + 2.0
                else:
                    freq_start = max(1.0, freq - 2.5)
                    freq_end = freq + 2.5
                freq_solution = freq
                print(f"     📡 单频扫频范围: {freq_start:.2f} - {freq_end:.2f} GHz")

            freq_start = max(0.1, freq_start)
            freq_end = min(20.0, freq_end)

            # 修改扫频
            sweep_ok = False
            try:
                sweeps = list(oModule.GetSweeps("Setup1"))
                if sweeps:
                    sweep_name = sweeps[0]
                    oModule.EditSweep("Setup1", sweep_name, [
                        "NAME:" + sweep_name,
                        "IsEnabled:=", True,
                        "RangeStart:=", f"{freq_start}GHz",
                        "RangeEnd:=", f"{freq_end}GHz",
                        "RangeStep:=", "0.01GHz",
                    ])
                    sweep_ok = True
                    print(f"     ✓ 更新扫频范围")
            except:
                pass

            if not sweep_ok:
                try:
                    try:
                        sweeps = list(oModule.GetSweeps("Setup1"))
                        for s in sweeps:
                            try:
                                oModule.DeleteSweep("Setup1", s)
                            except:
                                pass
                    except:
                        pass

                    oModule.InsertFrequencySweep("Setup1", [
                        "NAME:Sweep",
                        "IsEnabled:=", True,
                        "RangeType:=", "LinearStep",
                        "RangeStart:=", f"{freq_start}GHz",
                        "RangeEnd:=", f"{freq_end}GHz",
                        "RangeStep:=", "0.01GHz",
                        "Type:=", "Interpolating",
                        "SaveFields:=", False,
                        "SaveRadFields:=", False,
                        "InterpTolerance:=", 0.5,
                        "InterpMaxSolns:=", 250,
                        "InterpMinSolns:=", 0,
                        "InterpMinSubranges:=", 1,
                        "InterpUseS:=", True,
                        "InterpUsePortImped:=", False,
                        "InterpUsePropConst:=", True,
                        "UseDerivativeConvergence:=", False,
                        "InterpDerivTolerance:=", 0.2,
                        "UseFullBasis:=", True,
                        "EnforcePassivity:=", True,
                        "PassivityErrorTolerance:=", 0.0001
                    ])
                    sweep_ok = True
                    print(f"     ✓ 重建扫频范围")
                except Exception as e:
                    print(f"     ⚠️ 重建扫频失败: {e}")

            if not sweep_ok:
                print(f"     ⚠️ 无法修改扫频范围，使用模板默认值")

            # 修改求解频率
            try:
                oModule.EditSetup("Setup1", [
                    "NAME:Setup1",
                    "Frequency:=", f"{freq_solution}GHz",
                    "MaxDeltaS:=", 0.02,
                    "MaximumPasses:=", 15,
                ])
                print(f"     ✓ 更新求解频率: {freq_solution} GHz")
            except:
                try:
                    oDesign.ChangeProperty([
                        "NAME:AllTabs",
                        ["NAME:HfssTab",
                         ["NAME:PropServers", "AnalysisSetup:Setup1"],
                         ["NAME:ChangedProps",
                          ["NAME:Solution Freq", "Value:=", f"{freq_solution}GHz"]
                          ]]
                    ])
                    print(f"     ✓ 更新求解频率: {freq_solution} GHz (备用方法)")
                except Exception as e:
                    print(f"     ⚠️ 修改求解频率失败: {e}")

        except Exception as e:
            print(f"     ⚠️ 更新求解设置失败: {e}")