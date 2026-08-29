# -*- coding: utf-8 -*-
"""
HFSS自动化模块 - 精简版
只导出CSV文件，使用简单路径
"""

import win32com.client
import os
import time
import gc
from typing import Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HFSSAutomation:
    """HFSS自动化类"""

    def __init__(self, visible: bool = True):
        self.oAnsoftApp = None
        self.oDesktop = None
        self.oProject = None
        self.oDesign = None
        self.visible = visible

    def start(self) -> bool:
        """启动HFSS"""
        try:
            logger.info("正在启动HFSS...")
            self.oAnsoftApp = win32com.client.Dispatch("Ansoft.ElectronicsDesktop")
            self.oDesktop = self.oAnsoftApp.GetAppDesktop()
            if self.visible:
                self.oDesktop.RestoreWindow()
            return True
        except Exception as e:
            logger.error(f"启动HFSS失败: {e}")
            return False

    def open_project(self, project_path: str) -> bool:
        """打开HFSS项目"""
        try:
            if not os.path.exists(project_path):
                logger.error(f"项目文件不存在: {project_path}")
                return False
            logger.info(f"正在打开项目: {os.path.basename(project_path)}")
            self.oDesktop.OpenProject(project_path)
            self.oProject = self.oDesktop.GetActiveProject()
            self.oDesign = self.oProject.GetActiveDesign()
            return True
        except Exception as e:
            logger.error(f"打开项目失败: {e}")
            return False

    def analyze_all(self) -> bool:
        """分析所有设计"""
        try:
            logger.info("正在分析项目...")
            self.oDesign.AnalyzeAll()
            return True
        except Exception as e:
            logger.error(f"分析项目失败: {e}")
            return False

    def export_s_parameters_csv(self, output_path: str) -> Tuple[bool, str]:
        """
        只导出S参数CSV文件

        Args:
            output_path: 完整的CSV输出路径（例如 T:/data/s11.csv）

        Returns:
            (success, csv_path)
        """
        try:
            oModule = self.oDesign.GetModule("ReportSetup")

            # 确保路径使用正斜杠
            csv_path = output_path.replace("\\", "/")

            # 确保目录存在
            csv_dir = os.path.dirname(csv_path)
            os.makedirs(csv_dir, exist_ok=True)

            logger.info(f"导出CSV到: {csv_path}")

            report_name = "S Parameter Plot 1"

            # 尝试直接导出
            try:
                oModule.ExportToFile(report_name, csv_path, False)
                logger.info("导出成功")
            except:
                # 报告不存在，创建它
                logger.info("创建新报告...")
                try:
                    oModule.CreateReport(
                        report_name,
                        "Modal Solution Data",
                        "Rectangular Plot",
                        "Setup1 : Sweep",
                        ["Domain:=", "Sweep"],
                        ["Freq:=", ["All"]],
                        [
                            "X Component:=", "Freq",
                            "Y Component:=", ["dB(S(1,1))"]
                        ]
                    )
                    # 等待报告创建完成（最多5秒，轮询方式）
                    exported = False
                    for _ in range(10):
                        time.sleep(0.5)
                        try:
                            oModule.ExportToFile(report_name, csv_path, False)
                            exported = True
                            break
                        except:
                            continue

                    if not exported:
                        # 最后一次尝试
                        oModule.ExportToFile(report_name, csv_path, False)

                    logger.info("创建并导出成功")
                except Exception as e:
                    logger.error(f"创建报告失败: {e}")
                    return False, ""

            # 验证文件
            if os.path.exists(csv_path):
                logger.info(f"CSV验证成功: {csv_path}")
                return True, csv_path
            else:
                logger.warning("CSV文件未生成")
                return False, ""

        except Exception as e:
            logger.error(f"导出失败: {e}")
            return False, ""

    def save_project(self) -> bool:
        try:
            self.oProject.Save()
            return True
        except:
            return False

    def close_project(self) -> bool:
        try:
            if self.oProject:
                project_name = self.oProject.GetName()
                self.oDesktop.CloseProject(project_name)
                time.sleep(0.5)  # 减少等待时间
                return True
            return False
        except:
            return False

    def close_hfss(self) -> bool:
        logger.info("关闭HFSS...")
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
        time.sleep(1)  # 减少等待时间
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_hfss()