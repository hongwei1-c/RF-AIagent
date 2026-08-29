#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传输线 HFSS 控制器
"""

import os
import sys
import time
from config import HFSS_TLINE_TEMPLATE, TLINE_CSV_OUTPUT, TLINE_AI_WORKSPACE
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from hfss_automation import HFSSAutomation


class TLineController:
    """传输线 HFSS 控制器"""

    def __init__(self, work_dir: str = None,
                 template_project: str = None,
                 tline_type: str = "微带线",
                 target_freq: float = 5.0):

        if work_dir is None:
            work_dir = str(TLINE_AI_WORKSPACE)
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.template_project = template_project or str(HFSS_TLINE_TEMPLATE)
        self.tline_type = tline_type
        self.target_freq = target_freq

    def get_default_params(self) -> Dict[str, float]:
        """获取默认参数"""
        return {
            "W0": 30.0,
            "L0": 50.0,
            "w1": 2.5,
            "l1": 40.0,
            "H": 1.6
        }

    def run_simulation(self, params: Dict[str, float],
                       analysis_type: str = "all",
                       reuse_hfss=None) -> Dict[str, Any]:
        """运行仿真"""
        result = {
            'success': False,
            'csv_s_params': None,
            'csv_tdr': None,
            'error': None,
            'params': params.copy()
        }

        if not os.path.exists(self.template_project):
            result['error'] = f"项目文件不存在: {self.template_project}"
            return result

        output_dir = str(TLINE_CSV_OUTPUT)
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%H%M%S')
        csv_s = f"{output_dir}/s_params_{timestamp}.csv"
        csv_tdr = f"{output_dir}/tdr_{timestamp}.csv"

        print(f"  📂 项目: {Path(self.template_project).name}")
        print(f"  💾 输出: {output_dir}")

        try:
            if reuse_hfss:
                hfss = reuse_hfss
                need_close_hfss = False
            else:
                hfss = HFSSAutomation(visible=False)
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

            # 更新参数
            self._update_variables(oDesign, params)

            print(f"  🚀 运行仿真...")
            hfss.analyze_all()

            print(f"  ⏳ 等待仿真完成...")
            self._wait_for_analysis_complete(oDesign, timeout_seconds=120)

            # 导出报告
            oModule = oDesign.GetModule("ReportSetup")

            try:
                oModule.ExportToFile("S Parameter Plot", csv_s, False)
                result['csv_s_params'] = csv_s
                print(f"  ✅ S参数导出成功: {csv_s}")
            except:
                pass

            try:
                oModule.ExportToFile("TDR Plot", csv_tdr, False)
                result['csv_tdr'] = csv_tdr
                print(f"  ✅ TDR导出成功: {csv_tdr}")
            except:
                pass

            if result['csv_s_params'] or result['csv_tdr']:
                result['success'] = True

            hfss.save_project()
            hfss.close_project()
            if need_close_hfss:
                hfss.close_hfss()

        except Exception as e:
            result['error'] = str(e)
            print(f"  ❌ 异常: {e}")

        return result

    def _update_variables(self, oDesign, params: Dict[str, float]):
        """更新变量"""
        try:
            oDesign.ChangeProperty([
                "NAME:AllTabs",
                ["NAME:LocalVariableTab",
                 ["NAME:PropServers", "LocalVariables"],
                 ["NAME:ChangedProps"] + [
                     [f"NAME:{key}", "Value:=", f"{value}mm"]
                     for key, value in params.items() if value > 0
                 ]
                 ]
            ])
            print(f"     ✓ 参数已更新")
        except Exception as e:
            print(f"     ⚠️ 更新参数失败: {e}")

    def _wait_for_analysis_complete(self, oDesign, timeout_seconds=120):
        """等待仿真完成"""
        start = time.time()
        while time.time() - start < timeout_seconds:
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
