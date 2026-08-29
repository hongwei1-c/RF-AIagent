#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传输线脚本执行器 - 使用 COM 接口
"""

import os
import sys
import time
import gc
import tempfile
import win32com.client
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class TLineScriptRunner:
    """HFSS 脚本执行器 - 使用 COM 接口"""

    def __init__(self, hfss_exe: str = None):
        # hfss_exe 保留但不使用，改用 COM 接口
        self.hfss_exe = hfss_exe
        self.oAnsoftApp = None
        self.oDesktop = None
        self._started = False

    def _ensure_started(self) -> bool:
        """确保 HFSS 已启动"""
        if self._started and self.oDesktop is not None:
            return True

        try:
            print("  🚀 启动 HFSS (COM 接口)...")
            self.oAnsoftApp = win32com.client.Dispatch("Ansoft.ElectronicsDesktop")
            self.oDesktop = self.oAnsoftApp.GetAppDesktop()
            self.oDesktop.RestoreWindow()
            self._started = True
            print("  ✅ HFSS 启动成功")
            return True
        except Exception as e:
            print(f"  ❌ 启动 HFSS 失败: {e}")
            return False

    def run_script(self, script_path: str, wait: bool = True) -> Dict[str, Any]:
        """执行脚本"""
        result = {
            'success': False,
            'output': '',
            'error': '',
            'script': script_path
        }

        if not os.path.exists(script_path):
            result['error'] = f"脚本文件不存在: {script_path}"
            return result

        if not self._ensure_started():
            result['error'] = "启动 HFSS 失败"
            return result

        try:
            print(f"  📜 运行脚本: {os.path.basename(script_path)}")

            # 使用 RunScript 执行
            self.oDesktop.RunScript(script_path)
            result['success'] = True
            print("  ✅ 脚本执行完成")

            # 等待仿真完成
            if wait:
                print("  ⏳ 等待仿真完成...")
                self._wait_for_completion()

        except Exception as e:
            result['error'] = str(e)
            print(f"  ❌ 执行失败: {e}")

        return result

    def _wait_for_completion(self, timeout_seconds: int = 300):
        """等待仿真完成"""
        start = time.time()
        while time.time() - start < timeout_seconds:
            try:
                oProject = self.oDesktop.GetActiveProject()
                if oProject:
                    oDesign = oProject.GetActiveDesign()
                    analysis = oDesign.GetModule("AnalysisSetup")
                    if hasattr(analysis, 'IsSolving'):
                        if not analysis.IsSolving():
                            time.sleep(1)
                            print("  ✅ 仿真完成")
                            return True
            except:
                pass
            time.sleep(1)
        print("  ⚠️ 等待超时")
        return False

    def close_hfss(self):
        """关闭 HFSS"""
        try:
            if self.oDesktop:
                self.oDesktop.CloseDesktop()
        except:
            pass
        try:
            if self.oAnsoftApp:
                self.oAnsoftApp.QuitApplication()
        except:
            pass
        gc.collect()
        self._started = False

    # tline_runner.py - run_with_params 方法

    def run_with_params(self, params: Dict[str, float],
                        target_freq: float = 5.0) -> Dict[str, Any]:
        """使用参数生成并执行"""
        from tline_builder import TLineScriptBuilder

        builder = TLineScriptBuilder(
            project_name=f"TLine_{datetime.now().strftime('%H%M%S')}",
            target_freq=target_freq
        )
        builder.set_common_params(**params)
        # 设置线参数 (如果 params 中有 w1, l1)
        w = params.get('w1', 2.85)
        l = params.get('l1', 100.0)
        builder.set_line(w=w, l=l)

        temp_dir = tempfile.gettempdir()
        script_path = Path(temp_dir) / f"tline_{datetime.now().strftime('%H%M%S')}.py"
        builder.save_script(str(script_path))

        result = self.run_script(str(script_path))

        try:
            os.remove(script_path)
        except:
            pass

        return result

    def __enter__(self):
        self._ensure_started()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_hfss()


# ===== 测试代码 =====
if __name__ == "__main__":
    print("=" * 60)
    print("测试 TLineScriptRunner (COM 接口)")
    print("=" * 60)

    runner = TLineScriptRunner()
    result = runner.run_script("test_script.py")
    print(f"结果: {result}")
    runner.close_hfss()