#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WHYAVE-AI - AI-Agent驱动射频设计系统 主程序
集成HFSS自动化、CSV数值分析、LLM智能诊断、AI Agent自动优化
支持单频和多频优化
"""

import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import traceback


# 设置异常钩子
def excepthook(exc_type, exc_value, exc_traceback):
    """全局异常处理"""
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"未捕获的异常:\n{error_msg}")

    # 尝试写入日志文件
    try:
        with open("error_log.txt", "w", encoding="utf-8") as f:
            f.write(error_msg)
    except:
        pass

    # 调用默认的异常处理
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = excepthook

# 设置 PyQt 的调试标志
os.environ["QT_LOGGING_RULES"] = "qt.qpa.xcb=true"
os.environ["QT_DEBUG_PLUGINS"] = "1"

# PyQt6导入
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog,
        QMessageBox, QCheckBox, QDoubleSpinBox, QProgressBar,
        QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
        QStatusBar, QGridLayout, QComboBox, QTextBrowser, QRadioButton,
        QButtonGroup, QSplitter, QSplashScreen, QSpinBox, QFrame,
        QScrollArea
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings, QSize
    from PyQt6.QtGui import QFont, QTextCursor, QColor, QIcon, QPixmap, QMovie
except ImportError:
    print("错误: 未安装PyQt6，请运行: pip install PyQt6")
    sys.exit(1)

# 导入自定义模块
sys.path.insert(0, str(Path(__file__).parent))

try:
    from hfss_automation import HFSSAutomation
    from s_param_analyzer import SParamAnalyzer

    MODULES_OK = True
    print("✅ 基础模块导入成功")
except ImportError as e:
    print(f"⚠️ 基础模块导入失败: {e}")
    MODULES_OK = False

try:
    from optimization_tab import OptimizationTab

    OPTIMIZATION_TAB_OK = True
    print("✅ 无源器件仿真模块导入成功")
except ImportError as e:
    print(f"⚠️ 无源器件仿真模块导入失败: {e}")
    OPTIMIZATION_TAB_OK = False

# 导入传输线模块
try:
    from tline_builder import TLineScriptBuilder
    from tline_controller import TLineController
    from tline_analyzer import TLineAnalyzer
    from tline_agent import TLineAgent

    TLINE_MODULE_OK = True
    print("✅ 传输线模块导入成功")
except ImportError as e:
    print(f"⚠️ 传输线模块导入失败: {e}")
    TLINE_MODULE_OK = False


# main.py - 替换整个 TLineWorker 类 (约第90-170行)

class TLineWorker(QThread):
    """传输线仿真工作线程"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            self.log_signal.emit("=" * 60)
            self.log_signal.emit("🔌 传输线仿真启动")

            tline_type = self.config.get('tline_type', '微带线')
            line_configs = self.config.get('line_configs', [])
            target_freq = self.config.get('target_freq', 5.0)
            substrate = self.config.get('substrate', {})

            self.log_signal.emit(f"   传输线类型: {tline_type}")
            self.log_signal.emit(f"   线数量: {len(line_configs)}")
            self.log_signal.emit(f"   目标频率: {target_freq} GHz")
            self.log_signal.emit("=" * 60)

            # 构建脚本 - 使用 TLineScriptBuilder (新版本只有 set_line)
            from tline_builder import TLineScriptBuilder

            builder = TLineScriptBuilder(
                project_name=f"TLine_{datetime.now().strftime('%H%M%S')}",
                target_freq=target_freq,
                material=substrate.get('material', 'FR4_epoxy'),
                conductor="copper"
            )

            # 设置基板参数
            builder.set_common_params(
                W0=substrate.get('W0', 30.0),
                L0=substrate.get('L0', 50.0),
                H=substrate.get('H', 1.6)
            )

            # 新版本只支持单条线，取第一条线配置
            if line_configs and len(line_configs) > 0:
                config = line_configs[0]
                w = config.get('w', 2.5)
                l = config.get('l', 40.0)
                name = config.get('name', 'TL0')
                imp = config.get('imp', 50.0)
                builder.set_line(w=w, l=l, name=name, port_impedance=imp)
                self.log_signal.emit(f"   线宽: {w}mm, 线长: {l}mm")
            else:
                builder.set_line(w=2.5, l=40.0)
                self.log_signal.emit(f"   线宽: 2.5mm, 线长: 40.0mm")

            # 生成脚本
            script_dir = "T:/TLine_Scripts"
            os.makedirs(script_dir, exist_ok=True)
            script_path = f"{script_dir}/tline_{datetime.now().strftime('%H%M%S')}.py"
            builder.save_script(script_path)

            self.log_signal.emit(f"✅ 脚本已生成: {script_path}")

            # 运行仿真
            from tline_runner import TLineScriptRunner
            runner = TLineScriptRunner()
            result = runner.run_script(script_path)

            if result['success']:
                self.log_signal.emit("✅ 仿真完成")
                self.finished_signal.emit(result)
            else:
                self.log_signal.emit(f"❌ 仿真失败: {result.get('error')}")
                self.error_signal.emit(result.get('error', '未知错误'))

        except Exception as e:
            self.error_signal.emit(str(e))
            import traceback
            self.log_signal.emit(traceback.format_exc())


class TLineAIWorker(QThread):
    """传输线 AI 优化工作线程"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    result_signal = pyqtSignal(dict)
    best_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, tline_type: str = "微带线",
                 target_freq: float = 5.0,
                 target_s11: float = -15,
                 target_impedance: float = 50.0,
                 max_iterations: int = 15,
                 template_project: str = None):
        super().__init__()
        self.tline_type = tline_type
        self.target_freq = target_freq
        self.target_s11 = target_s11
        self.target_impedance = target_impedance
        self.max_iterations = max_iterations
        self.template_project = template_project
        self.agent = None
        self._is_running = True

    def stop(self):
        self._is_running = False
        if self.agent:
            self.agent.stop()

    def run(self):
        try:
            from tline_agent import TLineAgent
            from ai_brain import DecisionMode

            self.log_signal.emit("🔌 初始化传输线 AI Agent...")

            self.agent = TLineAgent(
                tline_type=self.tline_type,
                target_freq=self.target_freq,
                target_s11=self.target_s11,
                target_impedance=self.target_impedance,
                max_iterations=self.max_iterations,
                decision_mode=DecisionMode.HYBRID,
                llm_url="http://localhost:1234/v1",
                model_name="qwen2.5-coder-7b-instruct",
                llm_service="llm_studio",
                work_dir=f"T:/TLine_AI_Workspace_{self.tline_type}_{self.target_freq}GHz",
                template_project=self.template_project
            )

            # 执行优化
            result = self._run_optimization()

            if self._is_running:
                self.finished_signal.emit(result)

        except Exception as e:
            self.error_signal.emit(str(e))
            import traceback
            self.log_signal.emit(traceback.format_exc())

    def _run_optimization(self):
        """执行优化并捕获回调"""
        iteration = 0
        for iteration in range(1, self.max_iterations + 1):
            if not self._is_running:
                break

            self.log_signal.emit(f"\n{'─' * 40}")
            self.log_signal.emit(f"📍 迭代 {iteration}/{self.max_iterations}")

            sim_result = self.agent.controller.run_simulation(self.agent.current_params)

            if not sim_result['success']:
                self.log_signal.emit(f"  ❌ 仿真失败: {sim_result.get('error')}")
                continue

            analysis = self.agent.analyzer.analyze(
                s_params_csv=sim_result.get('csv_s_params'),
                tdr_csv=sim_result.get('csv_tdr'),
                threshold_db=self.agent.target_s11
            )

            s11 = analysis.s11_min_db or 0
            imp = analysis.characteristic_impedance or 0
            is_pass = analysis.is_pass
            freq = analysis.s11_freq_ghz or self.target_freq
            bw = analysis.bandwidth_10db_ghz or 0

            # 计算得分
            score = 0
            if s11:
                score += 0.6 * max(0, min(1, (s11 - self.target_s11) / (-20 - self.target_s11)))
            if imp:
                imp_score = 1 - abs(imp - self.target_impedance) / self.target_impedance
                score += 0.4 * max(0, min(1, imp_score))

            self.log_signal.emit(f"  📊 S11: {s11:.2f} dB, 阻抗: {imp:.2f} Ω")
            self.log_signal.emit(f"  📊 得分: {score:.3f}, {'✅ 合格' if is_pass else '❌ 未达标'}")

            # 发送结果信号
            result_data = {
                'iteration': iteration,
                's11': s11,
                'impedance': imp,
                'freq': freq,
                'bandwidth': bw,
                'is_pass': is_pass,
                'score': score
            }
            self.result_signal.emit(result_data)
            self.progress_signal.emit(iteration, self.max_iterations)

            # 更新最佳
            if score > self.agent.best_score:
                self.agent.best_score = score
                self.agent.best_result = analysis
                self.agent.best_params = self.agent.current_params.copy()
                best_data = {
                    'iteration': iteration,
                    's11': s11,
                    'impedance': imp,
                    'freq': freq,
                    'bandwidth': bw,
                    'is_pass': is_pass,
                    'score': score
                }
                self.best_signal.emit(best_data)
                self.log_signal.emit(f"  🏆 新最佳! 得分={score:.3f}")

            if is_pass:
                self.log_signal.emit(f"\n🎉 传输线优化成功！S11={s11:.2f}dB, 阻抗={imp:.1f}Ω")
                break

            # AI决策
            decision_input = {
                's11_min_db': s11,
                'frequency_at_min_ghz': freq,
                'bandwidth_under_10db_ghz': bw,
                'is_pass': is_pass
            }

            decision = self.agent.brain.decide(self.agent.current_params, decision_input, iteration)
            self.log_signal.emit(f"  🧠 [{decision.model_name}] {decision.strategy}")
            self.agent.current_params = decision.new_params.copy()

            if decision.should_stop:
                break

        # 返回最终结果
        return {
            'success': self.agent.best_result is not None,
            'best_score': self.agent.best_score,
            'best_params': self.agent.best_params,
            'best_s11': self.agent.best_result.s11_min_db if self.agent.best_result else None,
            'best_impedance': self.agent.best_result.characteristic_impedance if self.agent.best_result else None,
            'iterations': iteration
        }


class TLineTab(QWidget):
    """传输线仿真标签页 - 支持 AI 自动优化"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.ai_worker = None
        self.line_configs = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ===== 左侧配置面板 =====
        left_panel = QWidget()
        left_panel.setMaximumWidth(550)
        left_layout = QVBoxLayout(left_panel)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # ---- 传输线类型选择 ----
        type_group = QGroupBox("📡 传输线类型")
        type_layout = QGridLayout(type_group)

        type_layout.addWidget(QLabel("结构类型:"), 0, 0)
        self.tline_type_combo = QComboBox()
        self.tline_type_combo.addItems([
            "微带线",
            "差分微带线",
            "耦合微带线",
            "带状线",
            "共面波导"
        ])
        self.tline_type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.tline_type_combo, 0, 1)

        scroll_layout.addWidget(type_group)

        # ---- 基板参数 ----
        substrate_group = QGroupBox("🧱 基板参数")
        substrate_layout = QGridLayout(substrate_group)

        substrate_layout.addWidget(QLabel("地宽度 W0 (mm):"), 0, 0)
        self.W0_spin = QDoubleSpinBox()
        self.W0_spin.setRange(10.0, 200.0)
        self.W0_spin.setValue(30.0)
        self.W0_spin.setSingleStep(1.0)
        substrate_layout.addWidget(self.W0_spin, 0, 1)

        substrate_layout.addWidget(QLabel("地长度 L0 (mm):"), 1, 0)
        self.L0_spin = QDoubleSpinBox()
        self.L0_spin.setRange(10.0, 200.0)
        self.L0_spin.setValue(50.0)
        self.L0_spin.setSingleStep(1.0)
        substrate_layout.addWidget(self.L0_spin, 1, 1)

        substrate_layout.addWidget(QLabel("介质厚度 H (mm):"), 2, 0)
        self.H_spin = QDoubleSpinBox()
        self.H_spin.setRange(0.1, 10.0)
        self.H_spin.setValue(1.6)
        self.H_spin.setSingleStep(0.1)
        substrate_layout.addWidget(self.H_spin, 2, 1)

        substrate_layout.addWidget(QLabel("介质材料:"), 3, 0)
        self.material_combo = QComboBox()
        self.material_combo.addItems(["FR4_epoxy", "RO4350B", "RO4003C", "RT5880"])
        substrate_layout.addWidget(self.material_combo, 3, 1)

        scroll_layout.addWidget(substrate_group)

        # ---- 线参数配置 ----
        line_group = QGroupBox("📐 线参数配置")
        line_layout = QGridLayout(line_group)

        # 线数量
        line_layout.addWidget(QLabel("线数量:"), 0, 0)
        self.line_count_spin = QSpinBox()
        self.line_count_spin.setRange(1, 20)
        self.line_count_spin.setValue(1)
        self.line_count_spin.valueChanged.connect(self._update_line_params)
        line_layout.addWidget(self.line_count_spin, 0, 1)

        # 线宽
        line_layout.addWidget(QLabel("线宽 (mm):"), 1, 0)
        self.line_w_spin = QDoubleSpinBox()
        self.line_w_spin.setRange(0.1, 20.0)
        self.line_w_spin.setValue(2.5)
        self.line_w_spin.setSingleStep(0.1)
        line_layout.addWidget(self.line_w_spin, 1, 1)

        # 线长
        line_layout.addWidget(QLabel("线长 (mm):"), 2, 0)
        self.line_l_spin = QDoubleSpinBox()
        self.line_l_spin.setRange(5.0, 200.0)
        self.line_l_spin.setValue(40.0)
        self.line_l_spin.setSingleStep(1.0)
        line_layout.addWidget(self.line_l_spin, 2, 1)

        # 线间距 (差分/耦合模式)
        line_layout.addWidget(QLabel("线间距 (mm):"), 3, 0)
        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(0.1, 20.0)
        self.spacing_spin.setValue(1.0)
        self.spacing_spin.setSingleStep(0.1)
        line_layout.addWidget(self.spacing_spin, 3, 1)

        # 端口阻抗
        line_layout.addWidget(QLabel("端口阻抗 (Ω):"), 4, 0)
        self.imp_spin = QDoubleSpinBox()
        self.imp_spin.setRange(25.0, 200.0)
        self.imp_spin.setValue(50.0)
        self.imp_spin.setSingleStep(1.0)
        line_layout.addWidget(self.imp_spin, 4, 1)

        scroll_layout.addWidget(line_group)

        # ---- 仿真设置 ----
        sim_group = QGroupBox("⚙️ 仿真设置")
        sim_layout = QGridLayout(sim_group)

        sim_layout.addWidget(QLabel("目标频率 (GHz):"), 0, 0)
        self.target_freq_spin = QDoubleSpinBox()
        self.target_freq_spin.setRange(0.5, 40.0)
        self.target_freq_spin.setValue(5.0)
        self.target_freq_spin.setSingleStep(0.5)
        sim_layout.addWidget(self.target_freq_spin, 0, 1)

        sim_layout.addWidget(QLabel("目标 S11 (dB):"), 1, 0)
        self.target_s11_spin = QDoubleSpinBox()
        self.target_s11_spin.setRange(-50, 0)
        self.target_s11_spin.setValue(-15)
        self.target_s11_spin.setSingleStep(1)
        sim_layout.addWidget(self.target_s11_spin, 1, 1)

        sim_layout.addWidget(QLabel("目标阻抗 (Ω):"), 2, 0)
        self.target_imp_spin = QDoubleSpinBox()
        self.target_imp_spin.setRange(25.0, 200.0)
        self.target_imp_spin.setValue(50.0)
        self.target_imp_spin.setSingleStep(1.0)
        sim_layout.addWidget(self.target_imp_spin, 2, 1)

        sim_layout.addWidget(QLabel("最大迭代:"), 3, 0)
        self.max_iter_spin = QSpinBox()
        self.max_iter_spin.setRange(3, 50)
        self.max_iter_spin.setValue(15)
        sim_layout.addWidget(self.max_iter_spin, 3, 1)

        scroll_layout.addWidget(sim_group)

        # ---- 控制按钮 ----
        btn_layout = QVBoxLayout()

        # 第一行：生成脚本 + 运行仿真
        row1_layout = QHBoxLayout()
        self.generate_btn = QPushButton("📝 生成脚本")
        self.generate_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        self.generate_btn.clicked.connect(self._generate_script)
        row1_layout.addWidget(self.generate_btn)

        self.run_btn = QPushButton("🚀 运行仿真")
        self.run_btn.setObjectName("start_btn")
        self.run_btn.setStyleSheet("""
            QPushButton#start_btn {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton#start_btn:hover {
                background-color: #66BB6A;
            }
            QPushButton#start_btn:disabled {
                background-color: #666;
            }
        """)
        self.run_btn.clicked.connect(self._run_simulation)
        row1_layout.addWidget(self.run_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ef5350;
            }
        """)
        self.stop_btn.clicked.connect(self._stop_simulation)
        row1_layout.addWidget(self.stop_btn)

        btn_layout.addLayout(row1_layout)

        # 第二行：AI 自动优化
        row2_layout = QHBoxLayout()
        self.ai_optimize_btn = QPushButton("🤖 AI 自动优化")
        self.ai_optimize_btn.setObjectName("ai_btn")
        self.ai_optimize_btn.setStyleSheet("""
            QPushButton#ai_btn {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton#ai_btn:hover {
                background-color: #AB47BC;
            }
            QPushButton#ai_btn:disabled {
                background-color: #666;
            }
        """)
        self.ai_optimize_btn.clicked.connect(self._run_ai_optimization)
        row2_layout.addWidget(self.ai_optimize_btn)

        self.ai_stop_btn = QPushButton("⏹ 停止 AI")
        self.ai_stop_btn.setEnabled(False)
        self.ai_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ef5350;
            }
        """)
        self.ai_stop_btn.clicked.connect(self._stop_ai_optimization)
        row2_layout.addWidget(self.ai_stop_btn)

        btn_layout.addLayout(row2_layout)
        scroll_layout.addLayout(btn_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        scroll_layout.addWidget(self.progress_bar)

        # ---- 线预览 ----
        preview_group = QGroupBox("📊 线配置预览")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        self.preview_text.setFont(QFont("Consolas", 9))
        preview_layout.addWidget(self.preview_text)
        scroll_layout.addWidget(preview_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        # ===== 右侧结果面板 =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 日志
        log_group = QGroupBox("📝 运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_btn)
        right_layout.addWidget(log_group, stretch=2)

        # 结果表格
        result_group = QGroupBox("📊 仿真/优化结果")
        result_layout = QVBoxLayout(result_group)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels(
            ["迭代", "S11 (dB)", "阻抗 (Ω)", "频率 (GHz)", "带宽 (GHz)", "状态"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        result_layout.addWidget(self.result_table)
        right_layout.addWidget(result_group, stretch=3)

        # 最佳结果
        best_group = QGroupBox("🏆 当前最佳")
        best_layout = QVBoxLayout(best_group)
        self.best_label = QLabel("等待优化...")
        self.best_label.setStyleSheet("""
            background-color: #0d1520;
            padding: 12px;
            border-radius: 5px;
            font-size: 11px;
            border: 1px solid #1a3a5c;
        """)
        self.best_label.setWordWrap(True)
        best_layout.addWidget(self.best_label)
        right_layout.addWidget(best_group)

        # 添加到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([550, 650])

        layout.addWidget(splitter)

        # 初始化预览
        self._update_line_params()

    def _on_type_changed(self, tline_type: str):
        """传输线类型切换"""
        if "差分" in tline_type:
            self.line_count_spin.setValue(2)
            self.spacing_spin.setEnabled(True)
            self.spacing_spin.setValue(1.0)
            self.line_w_spin.setValue(2.0)
        elif "耦合" in tline_type:
            self.line_count_spin.setValue(3)
            self.spacing_spin.setEnabled(True)
            self.spacing_spin.setValue(0.8)
            self.line_w_spin.setValue(2.0)
        else:
            self.line_count_spin.setValue(1)
            self.spacing_spin.setEnabled(False)
            self.line_w_spin.setValue(2.5)

        self._update_line_params()

    def _update_line_params(self):
        """更新线参数预览"""
        count = self.line_count_spin.value()
        w = self.line_w_spin.value()
        l = self.line_l_spin.value()
        spacing = self.spacing_spin.value()

        self.line_configs = []
        preview_lines = []

        if count == 1:
            self.line_configs.append({"w": w, "l": l, "x": 0, "y": 0, "name": "TL1", "imp": self.imp_spin.value()})
            preview_lines.append(f"TL1: 宽={w}mm, 长={l}mm, x=0mm")
        else:
            total_width = count * w + (count - 1) * spacing
            start_x = -total_width / 2 + w / 2

            for i in range(count):
                x_pos = start_x + i * (w + spacing)
                name = f"TL{i + 1}"
                self.line_configs.append({
                    "w": w, "l": l,
                    "x": x_pos, "y": 0,
                    "name": name,
                    "imp": self.imp_spin.value()
                })
                preview_lines.append(f"{name}: 宽={w}mm, 长={l}mm, x={x_pos:.2f}mm")

        self.preview_text.setText("\n".join(preview_lines))
        if count > 1:
            self.preview_text.append(f"\n总宽度: {total_width:.2f}mm")

    # main.py - TLineTab._generate_script 方法

    # main.py - TLineTab._generate_script 方法 (已修改为使用 TLineScriptBuilder)

    def _generate_script(self):
        """生成脚本"""
        try:
            from tline_builder import TLineScriptBuilder

            script_dir = "T:/TLine_Scripts"
            os.makedirs(script_dir, exist_ok=True)

            w = self.line_w_spin.value()
            l = self.line_l_spin.value()
            target_freq = self.target_freq_spin.value()

            substrate = {
                "W0": self.W0_spin.value(),
                "L0": self.L0_spin.value(),
                "H": self.H_spin.value(),
                "material": self.material_combo.currentText()
            }

            script_path = f"{script_dir}/tline_{datetime.now().strftime('%H%M%S')}.py"

            builder = TLineScriptBuilder(
                project_name=f"TLine_{datetime.now().strftime('%H%M%S')}",
                target_freq=target_freq,
                material=substrate.get('material', 'FR4_epoxy'),
                conductor="copper"
            )

            builder.set_common_params(
                W0=substrate['W0'],
                L0=substrate['L0'],
                H=substrate['H']
            )

            # 使用 set_line 而不是 add_line
            builder.set_line(w=w, l=l, name="TL0", port_impedance=self.imp_spin.value())

            builder.save_script(script_path)

            self._log(f"✅ 脚本已生成: {script_path}")
            self._log(f"   基板: W0={substrate['W0']}mm, L0={substrate['L0']}mm, H={substrate['H']}mm")
            self._log(f"   线宽: {w}mm, 线长: {l}mm")

        except Exception as e:
            self._log(f"❌ 生成脚本失败: {e}")
            import traceback
            self._log(traceback.format_exc())
    def _run_simulation(self):
        """运行仿真"""
        if not self.line_configs:
            QMessageBox.warning(self, "警告", "请先配置线参数")
            return

        self.run_btn.setEnabled(False)
        self.ai_optimize_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.result_table.setRowCount(0)

        config = {
            'tline_type': self.tline_type_combo.currentText(),
            'line_configs': self.line_configs,
            'target_freq': self.target_freq_spin.value(),
            'substrate': {
                'W0': self.W0_spin.value(),
                'L0': self.L0_spin.value(),
                'H': self.H_spin.value(),
                'material': self.material_combo.currentText()
            }
        }

        self.worker = TLineWorker(config)
        self.worker.log_signal.connect(self._log)
        self.worker.progress_signal.connect(lambda v, t: self.progress_bar.setValue(v))
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(lambda e: self._log(f"❌ {e}"))

        self.worker.start()

    def _run_ai_optimization(self):
        """运行 AI 自动优化"""
        # 检查模板项目是否存在
        template_project = r"T:\AnsysPrj\TLine_stdr_ai.aedt"
        if not os.path.exists(template_project):
            QMessageBox.warning(self, "警告", f"传输线模板项目不存在:\n{template_project}")
            return

        self.ai_optimize_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.ai_stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.result_table.setRowCount(0)
        self.best_label.setText("AI 优化进行中...")

        target_freq = self.target_freq_spin.value()
        target_s11 = self.target_s11_spin.value()
        target_imp = self.target_imp_spin.value()
        max_iter = self.max_iter_spin.value()

        self._log("=" * 60)
        self._log("🤖 传输线 AI 自动优化启动")
        self._log(f"   目标频率: {target_freq} GHz")
        self._log(f"   目标 S11: < {target_s11} dB")
        self._log(f"   目标阻抗: {target_imp} Ω")
        self._log(f"   最大迭代: {max_iter}")
        self._log("=" * 60)

        self.ai_worker = TLineAIWorker(
            tline_type=self.tline_type_combo.currentText(),
            target_freq=target_freq,
            target_s11=target_s11,
            target_impedance=target_imp,
            max_iterations=max_iter,
            template_project=template_project
        )
        self.ai_worker.log_signal.connect(self._log)
        self.ai_worker.progress_signal.connect(self._update_ai_progress)
        self.ai_worker.result_signal.connect(self._add_ai_result)
        self.ai_worker.best_signal.connect(self._update_ai_best)
        self.ai_worker.finished_signal.connect(self._on_ai_finished)
        self.ai_worker.error_signal.connect(lambda e: self._log(f"❌ {e}"))

        self.ai_worker.start()

    def _update_ai_progress(self, iteration: int, total: int):
        """更新 AI 优化进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(iteration)

    def _add_ai_result(self, data: Dict):
        """添加 AI 优化结果到表格"""
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)

        self._set_center_cell(row, 0, str(data.get('iteration', 0)))
        self._set_center_cell(row, 1, f"{data.get('s11', 0):.2f}")
        self._set_center_cell(row, 2, f"{data.get('impedance', 0):.1f}")
        self._set_center_cell(row, 3, f"{data.get('freq', 0):.4f}")
        self._set_center_cell(row, 4, f"{data.get('bandwidth', 0):.4f}")

        is_pass = data.get('is_pass', False)
        status_text = "✅ 合格" if is_pass else "❌ 未达标"
        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        status_item.setForeground(QColor("#00ff88") if is_pass else QColor("#ff3366"))
        self.result_table.setItem(row, 5, status_item)

    def _update_ai_best(self, data: Dict):
        """更新 AI 最佳结果"""
        text = f"""
🏆 当前最佳 [迭代 {data.get('iteration', 0)}]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 S11 = {data.get('s11', 0):.2f} dB
📊 阻抗 = {data.get('impedance', 0):.1f} Ω
🎯 频率 = {data.get('freq', 0):.4f} GHz
📈 带宽 = {data.get('bandwidth', 0):.4f} GHz
{'✅' if data.get('is_pass') else '❌'} 状态: {'合格' if data.get('is_pass') else '未达标'}
"""
        self.best_label.setText(text)

    def _on_ai_finished(self, final_result: Dict):
        """AI 优化完成"""
        self.ai_optimize_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.ai_stop_btn.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum())

        if final_result.get('success'):
            self._log(f"\n✅ AI 优化成功完成!")
            best_s11 = final_result.get('best_s11', 0)
            best_imp = final_result.get('best_impedance', 0)
            self._log(f"   最佳 S11: {best_s11:.2f} dB")
            self._log(f"   最佳阻抗: {best_imp:.1f} Ω")
        else:
            self._log(f"\n⚠️ AI 优化结束，未达到目标")

    def _stop_ai_optimization(self):
        """停止 AI 优化"""
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()
            self._log("⚠️ 正在停止 AI 优化...")

    def _stop_simulation(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._log("⚠️ 正在停止...")

    def _on_finished(self, result):
        self.run_btn.setEnabled(True)
        self.ai_optimize_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(100)

        if result.get('success'):
            self._log("✅ 仿真完成")
        else:
            self._log(f"❌ 仿真失败: {result.get('error')}")

    def _set_center_cell(self, row: int, col: int, text: str):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_table.setItem(row, col, item)

    def _log(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")

        if "✅" in text:
            formatted = f'<span style="color: #00ff88;">[{timestamp}] {text}</span>'
        elif "❌" in text:
            formatted = f'<span style="color: #ff3366;">[{timestamp}] {text}</span>'
        elif "🏆" in text or "📊" in text:
            formatted = f'<span style="color: #00ffff;">[{timestamp}] {text}</span>'
        elif "🧠" in text or "🤖" in text:
            formatted = f'<span style="color: #ffaa00;">[{timestamp}] {text}</span>'
        else:
            formatted = f'[{timestamp}] {text}'

        self.log_text.append(formatted)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)


class WorkflowWorker(QThread):
    """工作流工作线程"""
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    result = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.is_running = True
        self.results = []

    def stop(self):
        self.is_running = False
        self.log.emit("⚠️ 正在停止...")

    def _find_projects(self, source: str, is_file_mode: bool, file_list: List[str] = None) -> List[Path]:
        projects = []
        if is_file_mode and file_list:
            for file_path in file_list:
                p = Path(file_path)
                if p.exists() and p.suffix.lower() in ['.aedt', '.hfss']:
                    projects.append(p)
                else:
                    self.log.emit(f"⚠️ 文件不存在或格式不支持: {file_path}")
        else:
            dir_path = Path(source)
            if dir_path.exists() and dir_path.is_dir():
                projects.extend(dir_path.glob("*.aedt"))
                projects.extend(dir_path.glob("*.hfss"))
                projects.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            else:
                self.log.emit(f"⚠️ 目录不存在: {source}")
        return projects

    def run(self):
        try:
            source = self.config.get("source", "")
            is_file_mode = self.config.get("is_file_mode", False)
            file_list = self.config.get("file_list", [])
            output_dir = self.config.get("output_dir", "")

            if not source and not file_list:
                self.error.emit("请选择HFSS项目文件或目录")
                return

            projects = self._find_projects(source, is_file_mode, file_list)

            if not projects:
                self.error.emit(f"未找到HFSS项目文件 (.aedt 或 .hfss)")
                return

            base_path = Path(output_dir)
            temp_dir = base_path / "temp"
            correct_dir = base_path / "correct_designs"
            wrong_dir = base_path / "wrong_designs"
            reports_dir = base_path / "reports"

            for d in [temp_dir, correct_dir, wrong_dir, reports_dir]:
                d.mkdir(parents=True, exist_ok=True)

            total = len(projects)
            self.log.emit(f"\n{'=' * 60}")
            self.log.emit(f"🚀 开始智能工作流")
            self.log.emit(f"📄 找到 {total} 个HFSS项目")
            self.log.emit(f"📁 输出目录: {output_dir}")
            self.log.emit("")

            analyzer = SParamAnalyzer(
                lm_studio_url=self.config.get("lm_url", "http://localhost:1234"),
                enable_llm=self.config.get("use_llm", True)
            )

            # 先启动一个 HFSS 实例，所有项目复用
            from hfss_automation import HFSSAutomation
            shared_hfss = HFSSAutomation(visible=self.config.get("hfss_visible", False))
            if not shared_hfss.start():
                self.log.emit("⚠️ 启动 HFSS 失败")
                return
            self.log.emit("✅ HFSS 已启动，将处理所有项目")

            passed = 0
            for i, proj in enumerate(projects, 1):
                if not self.is_running:
                    break

                self.progress.emit(int(i / total * 100), f"处理: {proj.name}")
                result = self._process_project(proj, temp_dir, analyzer, i, total, shared_hfss)
                self.results.append(result)
                self.result.emit(result)

                if result.get('is_pass'):
                    passed += 1
                    target = correct_dir / proj.stem
                else:
                    target = wrong_dir / proj.stem

                if result.get('success'):
                    target.mkdir(parents=True, exist_ok=True)
                    for f in result.get('files', []):
                        if os.path.exists(f):
                            shutil.copy2(f, target / Path(f).name)

                    result_to_save = {k: v for k, v in result.items()
                                      if k not in ['files', 'analysis']}
                    with open(target / "analysis_result.json", 'w', encoding='utf-8') as fp:
                        json.dump(result_to_save, fp, ensure_ascii=False, indent=2, default=str)

                    if result.get('diagnosis'):
                        with open(target / "diagnosis.txt", 'w', encoding='utf-8') as fp:
                            fp.write(result['diagnosis'])

            # 关闭 HFSS
            shared_hfss.close_hfss()
            self.log.emit("✅ HFSS 已关闭")

            if self.config.get("generate_report", True):
                self.log.emit("\n📝 正在生成报告...")
                self._generate_html_report(reports_dir, passed, total, self.results)
                self.log.emit(f"✅ 报告已生成: {reports_dir}")

            if not self.config.get("keep_temp", False):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass

            self.finished.emit({
                'total': total,
                'passed': passed,
                'rate': passed / total * 100 if total > 0 else 0
            })

        except Exception as e:
            self.error.emit(str(e))
            import traceback
            traceback.print_exc()

    def _process_project(self, proj: Path, temp_dir: Path, analyzer, cur: int, total: int, hfss=None) -> Dict:
        result = {
            'project_name': proj.stem,
            'project_file': str(proj),
            'success': False,
            'is_pass': False,
            's11_min_db': None,
            'bandwidth_10db_ghz': None,
            'center_frequency_ghz': None,
            'q_value': None,
            'files': [],
            'timestamp': datetime.now().isoformat(),
            'error': None,
            'diagnosis': None,
            'bands': None
        }

        try:
            self.log.emit(f"\n{'─' * 40}")
            self.log.emit(f"[{cur}/{total}] 处理: {proj.name}")

            work_dir = temp_dir / f"{proj.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            work_dir.mkdir(parents=True, exist_ok=True)

            self.log.emit("   🔧 运行HFSS仿真...")

            if hfss is None:
                self.log.emit("   ❌ HFSS实例未提供")
                result['error'] = "HFSS实例未提供"
                return result

            # 打开项目
            if not hfss.open_project(str(proj)):
                result['error'] = "打开项目失败"
                self.log.emit(f"   ❌ 打开项目失败")
                return result

            # 运行分析
            if not hfss.analyze_all():
                result['error'] = "仿真失败"
                self.log.emit(f"   ❌ 仿真失败")
                hfss.close_project()
                return result

            # 等待仿真完成（轮询）
            oDesign = hfss.oProject.GetActiveDesign()
            max_wait = 120
            start_wait = time.time()
            self.log.emit(f"   ⏳ 等待仿真完成（超时{max_wait}秒）...")

            while time.time() - start_wait < max_wait:
                try:
                    analysis = oDesign.GetModule("AnalysisSetup")
                    if hasattr(analysis, 'IsSolving'):
                        if not analysis.IsSolving():
                            self.log.emit("   ✅ 仿真完成")
                            break
                except:
                    pass
                time.sleep(1)
            else:
                self.log.emit(f"   ⚠️ 仿真超时（{max_wait}秒）")

            # 导出 CSV
            csv_path = work_dir / "s11.csv"
            success, exported_csv = hfss.export_s_parameters_csv(str(csv_path))

            if success and exported_csv and os.path.exists(exported_csv):
                result['files'].append(exported_csv)
                self.log.emit(f"   ✅ CSV导出成功")

                # 分析结果
                analysis = analyzer.analyze(
                    exported_csv,
                    use_ai=self.config.get("use_llm", True),
                    threshold_db=self.config.get("threshold", -10)
                )

                result['s11_min_db'] = analysis.get('s11_min_db')
                result['bandwidth_10db_ghz'] = analysis.get('bandwidth_under_10db_ghz')
                result['center_frequency_ghz'] = analysis.get('center_frequency_ghz')
                result['q_value'] = analysis.get('q_value')
                result['is_pass'] = analysis.get('is_pass', False)
                result['diagnosis'] = analysis.get('llm_diagnosis', '')
                result['success'] = True

                self.log.emit(f"   📊 S11: {result['s11_min_db']:.2f} dB")
                self.log.emit(f"   🎯 判定: {'✅ 合格' if result['is_pass'] else '❌ 不合格'}")
            else:
                result['error'] = "CSV导出失败"
                self.log.emit(f"   ❌ CSV导出失败")

            # 关闭项目（不关闭 HFSS）
            hfss.close_project()

        except Exception as e:
            result['error'] = str(e)
            self.log.emit(f"   ❌ 错误: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _generate_html_report(self, reports_dir: Path, passed: int, total: int, results: List):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rate = passed / total * 100 if total > 0 else 0

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>WHYAVE-AI 智能仿真报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0a1a; padding: 20px; color: #c0d0e0; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: #0d1a2d; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,150,255,0.15); }}
        .header {{ background: linear-gradient(135deg, #003366 0%, #0066cc 50%, #00ccff 100%); color: white; padding: 30px; text-align: center; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; padding: 30px; }}
        .stat-card {{ background: #0a0f1a; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #1a3a5c; }}
        .stat-value {{ font-size: 36px; font-weight: bold; color: #00ffff; }}
        .stat-label {{ color: #6080a0; margin-top: 5px; }}
        .pass {{ color: #00ff88; }}
        .fail {{ color: #ff3366; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #1a2a3a; }}
        th {{ background: #0a0f1a; color: #00ccff; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
        .badge-pass {{ background: #00ff88; color: #0a0a1a; }}
        .badge-fail {{ background: #ff3366; color: white; }}
        .footer {{ background: #0a0f1a; padding: 20px; text-align: center; color: #6080a0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 WHYAVE-AI 智能仿真报告</h1>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        <div class="stats">
            <div class="stat-card"><div class="stat-value">{total}</div><div class="stat-label">总设计数</div></div>
            <div class="stat-card"><div class="stat-value pass">{passed}</div><div class="stat-label">合格设计</div></div>
            <div class="stat-card"><div class="stat-value fail">{total - passed}</div><div class="stat-label">不合格设计</div></div>
            <div class="stat-card"><div class="stat-value">{rate:.1f}%</div><div class="stat-label">通过率</div></div>
        </div>
        <div style="padding: 0 30px 30px 30px;">
            <h2>📋 详细结果</h2>
            <table>
                <thead><tr><th>设计名称</th><th>S11(dB)</th><th>带宽(GHz)</th><th>中心频率(GHz)</th><th>Q值</th><th>判定</th></tr></thead>
                <tbody>
"""
        for r in results:
            s11 = f"{r['s11_min_db']:.2f}" if r.get('s11_min_db') else "N/A"
            bw = f"{r['bandwidth_10db_ghz']:.4f}" if r.get('bandwidth_10db_ghz') else "N/A"
            center = f"{r['center_frequency_ghz']:.4f}" if r.get('center_frequency_ghz') else "N/A"
            q = f"{r['q_value']:.1f}" if r.get('q_value') else "N/A"
            is_pass = r.get('is_pass', False)
            badge_class = "badge-pass" if is_pass else "badge-fail"
            badge_text = "合格" if is_pass else "不合格"
            html += f"<tr><td>{r['project_name']}</td><td>{s11}</td><td>{bw}</td><td>{center}</td><td>{q}</td><td><span class='badge {badge_class}'>{badge_text}</span></td></tr>"

        html += """
                </tbody>
            </table>
        </div>
        <div class="footer">
            <p>WHYAVE-AI - AI-Agent驱动射频设计系统</p>
        </div>
    </div>
</body>
</html>"""

        with open(reports_dir / f"report_{timestamp}.html", 'w', encoding='utf-8') as f:
            f.write(html)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.selected_files = []
        self.config = self._load_config()

        self.setWindowTitle("WHYAVE-AI - AI-Agent驱动射频设计系统")
        self.setGeometry(100, 100, 1300, 850)

        # 深色科技风主题
        self._apply_dark_theme()

        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1a3a5c;
                background-color: #0a0a1a;
                border-radius: 8px;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                padding: 8px 20px;
                background-color: #0d1520;
                color: #6080a0;
                border: 1px solid #1a3a5c;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0d1a2d;
                color: #00ffff;
                border-bottom: 2px solid #00ccff;
            }
            QTabBar::tab:hover {
                background-color: #1a2a3a;
            }
        """)

        # main.py - 替换整个标签页创建部分（约第540-580行）

        # 工作流标签页
        workflow_tab = self._create_workflow_tab()
        tabs.addTab(workflow_tab, "🚀 智能工作流")

        # 传输线标签页
        if TLINE_MODULE_OK:
            self.tline_tab = TLineTab()
            tabs.addTab(self.tline_tab, "🔌 传输线仿真")
        else:
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            label = QLabel("传输线模块加载失败\n\n请确保传输线相关模块已正确安装")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #ffaa00; font-size: 14px; padding: 50px;")
            placeholder_layout.addWidget(label)
            tabs.addTab(placeholder, "🔌 传输线仿真")

        # 无源器件仿真标签页（原AI优化）
        if OPTIMIZATION_TAB_OK:
            self.optimization_tab = OptimizationTab()
            tabs.addTab(self.optimization_tab, "🔌 无源器件仿真")
        else:
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            label = QLabel("无源器件仿真模块加载失败\n\n请确保 optimization_tab.py 及相关依赖已正确安装")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #ff3366; font-size: 14px; padding: 50px;")
            placeholder_layout.addWidget(label)
            tabs.addTab(placeholder, "🔌 无源器件仿真")

        # 关于标签页
        about_tab = self._create_about_tab()
        tabs.addTab(about_tab, "ℹ️ 关于")

        layout.addWidget(tabs)

        # 状态栏
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪 | WHYAVE-AI | AI-Agent驱动射频设计系统 | 支持0.5-10GHz任意频段 | 多频优化")

        # 检测LLM
        QTimer.singleShot(1000, self._check_llm)

    def _apply_dark_theme(self):
        """应用深色科技风主题"""
        self.setStyleSheet("""
            QMainWindow { 
                background-color: #0a0a1a; 
            }
            QGroupBox { 
                font-weight: bold; 
                border: 1px solid #1a3a5c; 
                border-radius: 10px; 
                margin-top: 14px; 
                padding-top: 14px; 
                background-color: #0d1520;
                color: #00ccff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 2px 10px;
                color: #00ffff;
                background-color: #0a0a1a;
                border: 1px solid #1a3a5c;
                border-radius: 5px;
            }
            QPushButton { 
                padding: 8px 16px; 
                border-radius: 6px; 
                font-weight: bold;
                border: 1px solid #1a3a5c;
                background-color: #0d1a2d;
                color: #00ccff;
            }
            QPushButton:hover {
                background-color: #1a3a5c;
                border-color: #00ccff;
            }
            QPushButton:pressed {
                background-color: #003366;
            }
            QPushButton#start { 
                background-color: #0066cc; 
                color: white; 
                border-color: #00ccff;
            }
            QPushButton#start:hover { 
                background-color: #0088ff; 
            }
            QPushButton#stop { 
                background-color: #cc0033; 
                color: white; 
                border-color: #ff3366;
            }
            QPushButton#stop:hover { 
                background-color: #ff0044; 
            }
            QLabel {
                color: #c0d0e0;
            }
            QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox, QSpinBox {
                background-color: #0a0f1a;
                color: #00ffcc;
                border: 1px solid #1a3a5c;
                border-radius: 5px;
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #0a0f1a;
                color: #00ffcc;
                border: 1px solid #1a3a5c;
                selection-background-color: #1a3a5c;
            }
            QTableWidget {
                background-color: #0a0f1a;
                color: #c0d0e0;
                gridline-color: #1a2a3a;
                border: 1px solid #1a3a5c;
                border-radius: 5px;
                alternate-background-color: #0d1520;
            }
            QTableWidget::item:selected { 
                background-color: #1a3a5c;
                color: #00ffff;
            }
            QHeaderView::section {
                background-color: #0d1a2d;
                color: #00ccff;
                border: 1px solid #1a3a5c;
                padding: 5px;
            }
            QProgressBar {
                background-color: #0a0f1a;
                border: 1px solid #1a3a5c;
                border-radius: 5px;
                text-align: center;
                color: #00ffcc;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #003366, stop:0.5 #0066cc, stop:1 #00ccff);
                border-radius: 4px;
            }
            QStatusBar {
                background-color: #0d1520;
                color: #6080a0;
                border-top: 1px solid #1a3a5c;
            }
            QTextEdit {
                font-family: 'Consolas', monospace;
                color: #00ffcc;
            }
            QRadioButton {
                color: #c0d0e0;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #1a3a5c;
                border-radius: 8px;
                background-color: #0a0f1a;
            }
            QRadioButton::indicator:checked {
                border-color: #00ccff;
                background-color: #00ccff;
            }
            QCheckBox {
                color: #c0d0e0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #1a3a5c;
                border-radius: 3px;
                background-color: #0a0f1a;
            }
            QCheckBox::indicator:checked {
                border-color: #00ccff;
                background-color: #00ccff;
            }
            QSplitter::handle {
                background-color: #1a3a5c;
                width: 2px;
            }
            QScrollBar:vertical {
                background-color: #0a0a1a;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #1a3a5c;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def _create_workflow_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 输入模式选择
        mode_group = QGroupBox("输入模式")
        mode_layout = QHBoxLayout(mode_group)

        self.file_mode_rb = QRadioButton("选择文件 (.aedt)")
        self.file_mode_rb.setChecked(True)
        self.file_mode_rb.toggled.connect(self._on_mode_changed)

        self.folder_mode_rb = QRadioButton("选择文件夹（批量）")

        mode_layout.addWidget(self.file_mode_rb)
        mode_layout.addWidget(self.folder_mode_rb)
        mode_layout.addStretch()
        layout.addWidget(mode_group)

        # 文件选择区域
        self.file_group = QGroupBox("文件选择")
        file_layout = QGridLayout(self.file_group)

        file_layout.addWidget(QLabel("选择文件:"), 0, 0)
        self.file_list_edit = QLineEdit()
        self.file_list_edit.setReadOnly(True)
        self.file_list_edit.setPlaceholderText("点击按钮选择 .aedt 文件")
        file_layout.addWidget(self.file_list_edit, 0, 1)

        self.select_files_btn = QPushButton("📂 选择文件...")
        self.select_files_btn.clicked.connect(self._select_files)
        file_layout.addWidget(self.select_files_btn, 0, 2)

        self.clear_files_btn = QPushButton("🗑 清空")
        self.clear_files_btn.clicked.connect(self._clear_files)
        file_layout.addWidget(self.clear_files_btn, 0, 3)

        self.file_count_label = QLabel("已选择 0 个文件")
        self.file_count_label.setStyleSheet("color: #6080a0; padding: 5px;")
        file_layout.addWidget(self.file_count_label, 1, 0, 1, 4)
        layout.addWidget(self.file_group)

        # 文件夹选择区域
        self.folder_group = QGroupBox("文件夹选择")
        folder_layout = QGridLayout(self.folder_group)

        folder_layout.addWidget(QLabel("项目目录:"), 0, 0)
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("选择包含 .aedt 文件的文件夹")
        folder_layout.addWidget(self.project_edit, 0, 1)

        btn = QPushButton("📁 浏览...")
        btn.clicked.connect(lambda: self._browse_dir(self.project_edit))
        folder_layout.addWidget(btn, 0, 2)
        layout.addWidget(self.folder_group)

        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("输出目录:"), 0, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择输出目录")
        output_layout.addWidget(self.output_edit, 0, 1)

        btn2 = QPushButton("📁 浏览...")
        btn2.clicked.connect(lambda: self._browse_dir(self.output_edit))
        output_layout.addWidget(btn2, 0, 2)

        output_layout.addWidget(QLabel("S11阈值(dB):"), 1, 0)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-50, 0)
        self.threshold_spin.setValue(-10)
        self.threshold_spin.setSingleStep(1)
        output_layout.addWidget(self.threshold_spin, 1, 1)

        output_layout.addWidget(QLabel("LLM地址:"), 2, 0)
        self.llm_url_edit = QLineEdit()
        self.llm_url_edit.setText("http://localhost:1234")
        self.llm_url_edit.setPlaceholderText("http://localhost:1234")
        output_layout.addWidget(self.llm_url_edit, 2, 1, 1, 2)

        layout.addWidget(output_group)

        # 选项
        opt_group = QGroupBox("运行选项")
        opt_layout = QHBoxLayout(opt_group)

        self.use_llm_cb = QCheckBox("启用LLM智能诊断")
        self.use_llm_cb.setChecked(True)
        self.close_hfss_cb = QCheckBox("完成后关闭HFSS")
        self.close_hfss_cb.setChecked(True)
        self.keep_temp_cb = QCheckBox("保留临时文件")
        self.gen_report_cb = QCheckBox("生成报告")
        self.gen_report_cb.setChecked(True)

        opt_layout.addWidget(self.use_llm_cb)
        opt_layout.addWidget(self.close_hfss_cb)
        opt_layout.addWidget(self.keep_temp_cb)
        opt_layout.addWidget(self.gen_report_cb)
        opt_layout.addStretch()
        layout.addWidget(opt_group)

        # LLM状态
        self.llm_status_label = QLabel("🔍 正在检测LLM服务...")
        self.llm_status_label.setStyleSheet("padding: 8px; background: #0d1a2d; border-radius: 5px; color: #00ccff;")
        layout.addWidget(self.llm_status_label)

        # 按钮
        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("🚀 启动智能工作流")
        self.start_btn.setObjectName("start")
        self.start_btn.clicked.connect(self._start)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)

        self.test_llm_btn = QPushButton("🧪 测试LLM连接")
        self.test_llm_btn.clicked.connect(self._test_llm)

        btn_layout.addStretch()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.test_llm_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)

        result_group = QGroupBox("处理结果")
        r_layout = QVBoxLayout(result_group)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels(
            ["设计名称", "S11(dB)", "带宽(GHz)", "中心频率(GHz)", "Q值", "判定"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.setAlternatingRowColors(True)
        r_layout.addWidget(self.result_table)
        splitter.addWidget(result_group)

        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.log_text)

        clear_log_btn = QPushButton("🗑 清空日志")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_log_btn)
        splitter.addWidget(log_group)

        splitter.setSizes([300, 400])
        layout.addWidget(splitter)

        self._on_mode_changed()

        return tab

    def _create_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Logo区域
        gif_path = r"T:\py_prj\AIHFSS\N1\UI\rf_particle_animation.gif"
        if os.path.exists(gif_path):
            logo_label = QLabel()
            movie = QMovie(gif_path)
            movie.setScaledSize(QSize(300, 300))
            logo_label.setMovie(movie)
            movie.start()
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_label)

        title = QLabel("WHYAVE-AI")
        title.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #00ffff; margin-top: 10px;")
        layout.addWidget(title)

        subtitle = QLabel("AI-Agent驱动射频设计系统")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #6080a0; font-size: 14px;")
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        info = QTextBrowser()
        info.setOpenExternalLinks(True)
        info.setStyleSheet("background-color: #0a0f1a; color: #c0d0e0; border: 1px solid #1a3a5c; border-radius: 8px;")
        info.setHtml("""
        <h3 style="color: #00ccff;">✨ 核心功能</h3>
        <ul>
        <li><b>AI Agent 闭环优化</b> - LLM+物理规则混合决策，自动调参</li>
        <li><b>多频天线优化</b> - 支持2.45GHz+5GHz等双频/多频设计</li>
        <li><b>HFSS自动化仿真</b> - COM接口控制，自动运行仿真导出结果</li>
        <li><b>高精度收敛</b> - ±0.01 GHz 频率精度</li>
        <li><b>任意频段支持</b> - 0.5-10 GHz，自动调整介质板尺寸</li>
        <li><b>双模式决策</b> - 纯LLM / 纯规则 / 混合模式可选</li>
        <li><b>批量工作流</b> - 自动分类合格/不合格设计，生成报告</li>
        <li><b>经验学习</b> - 自动保存优化结果到知识库</li>
        </ul>

        <h3 style="color: #00ccff; margin-top: 15px;">🤖 技术架构</h3>
        <ul>
        <li><b>决策引擎</b> - LLM (Qwen/DeepSeek) + 物理规则混合</li>
        <li><b>仿真控制</b> - HFSS COM接口自动化</li>
        <li><b>数值分析</b> - NumPy/SciPy精确计算</li>
        <li><b>GUI界面</b> - PyQt6 深色科技风主题</li>
        </ul>

        <h3 style="color: #00ccff; margin-top: 15px;">📊 性能指标</h3>
        <ul>
        <li>收敛轮数: 6-30轮（多频需要更多迭代）</li>
        <li>频率精度: ±0.01 GHz</li>
        <li>2.0 GHz: 6轮收敛，S11=-31.4 dB</li>
        <li>2.45 GHz: 8轮收敛，S11=-24.9 dB</li>
        <li>双频优化: 15-25轮收敛</li>
        </ul>

        <h3 style="color: #00ccff; margin-top: 15px;">📡 多频优化使用</h3>
        <ul>
        <li>在"AI优化"标签页选择"多频优化"模式</li>
        <li>添加需要的频点（如2.45GHz和5GHz）</li>
        <li>设置S11目标和迭代次数</li>
        <li>确保HFSS模型支持多频结构（如开槽天线）</li>
        </ul>

        <p style="margin-top: 20px; color: #6080a0;">© 2026 WHYAVE-AI | AI-Agent驱动射频设计系统 | 多频优化版</p>
        """)
        layout.addWidget(info)

        return tab

    def _on_mode_changed(self):
        is_file_mode = self.file_mode_rb.isChecked()
        self.file_group.setVisible(is_file_mode)
        self.folder_group.setVisible(not is_file_mode)

    def _select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择HFSS项目文件",
            "", "HFSS项目文件 (*.aedt *.hfss);;所有文件 (*)"
        )
        if files:
            self.selected_files = files
            display_text = ", ".join([os.path.basename(f) for f in files[:3]])
            if len(files) > 3:
                display_text += f" 等{len(files)}个文件"
            self.file_list_edit.setText(display_text)
            self.file_count_label.setText(f"已选择 {len(files)} 个文件")

    def _clear_files(self):
        self.selected_files = []
        self.file_list_edit.clear()
        self.file_count_label.setText("已选择 0 个文件")

    def _browse_dir(self, edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "选择目录")
        if d:
            edit.setText(d)

    def _load_config(self) -> dict:
        default = {
            "project_dir": "",
            "output_dir": "",
            "threshold": -10,
            "use_llm": True,
            "lm_url": "http://localhost:1234",
            "close_hfss": True,
            "keep_temp": False,
            "generate_report": True
        }
        if os.path.exists("config.json"):
            try:
                with open("config.json", 'r', encoding='utf-8') as f:
                    default.update(json.load(f))
            except:
                pass
        return default

    def _save_config(self):
        cfg = {
            "project_dir": self.project_edit.text(),
            "output_dir": self.output_edit.text(),
            "threshold": self.threshold_spin.value(),
            "use_llm": self.use_llm_cb.isChecked(),
            "lm_url": self.llm_url_edit.text(),
            "close_hfss": self.close_hfss_cb.isChecked(),
            "keep_temp": self.keep_temp_cb.isChecked(),
            "generate_report": self.gen_report_cb.isChecked()
        }
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except:
            pass

    def _check_llm(self):
        try:
            import requests
            url = self.llm_url_edit.text()
            resp = requests.get(f"{url}/v1/models", timeout=5)
            if resp.status_code == 200:
                self.llm_status_label.setText("✅ LLM服务已连接 - 智能诊断可用")
                self.llm_status_label.setStyleSheet(
                    "padding: 8px; background: #0d2a1a; color: #00ff88; border-radius: 5px;")
            else:
                self._set_llm_unavailable()
        except:
            self._set_llm_unavailable()

    def _set_llm_unavailable(self):
        self.llm_status_label.setText("⚠️ LLM服务未连接 - 将使用基础分析模式")
        self.llm_status_label.setStyleSheet(
            "padding: 8px; background: #2a1a0d; color: #ffaa00; border-radius: 5px;")
        self.use_llm_cb.setEnabled(False)
        self.use_llm_cb.setChecked(False)

    def _test_llm(self):
        self._log("🔍 正在测试LLM连接...")
        try:
            import requests
            url = self.llm_url_edit.text()
            resp = requests.get(f"{url}/v1/models", timeout=5)
            if resp.status_code == 200:
                models = resp.json()
                model_names = [m.get('id', '') for m in models.get('data', [])]
                self._log(f"✅ LLM连接成功！可用模型: {len(model_names)}个")
                for m in model_names[:5]:
                    self._log(f"   - {m}")
                QMessageBox.information(self, "连接成功", f"LLM服务已连接\n可用模型: {len(model_names)}个")
            else:
                self._log(f"❌ 连接失败: HTTP {resp.status_code}")
                QMessageBox.warning(self, "连接失败", "无法连接到LLM服务")
        except Exception as e:
            self._log(f"❌ 连接失败: {e}")
            QMessageBox.warning(self, "连接失败",
                                f"无法连接到LLM服务\n\n请确保LM Studio或Ollama已启动\n\n错误: {e}")

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def _add_result_to_table(self, result: dict):
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)

        self.result_table.setItem(row, 0, QTableWidgetItem(result.get("project_name", "")))

        s11 = result.get("s11_min_db")
        s11_text = f"{s11:.2f}" if s11 else "N/A"
        self.result_table.setItem(row, 1, QTableWidgetItem(s11_text))

        bw = result.get("bandwidth_10db_ghz")
        bw_text = f"{bw:.4f}" if bw else "N/A"
        self.result_table.setItem(row, 2, QTableWidgetItem(bw_text))

        center = result.get("center_frequency_ghz")
        center_text = f"{center:.4f}" if center else "N/A"
        self.result_table.setItem(row, 3, QTableWidgetItem(center_text))

        q = result.get("q_value")
        q_text = f"{q:.1f}" if q else "N/A"
        self.result_table.setItem(row, 4, QTableWidgetItem(q_text))

        is_pass = result.get("is_pass", False)
        pass_text = "✅ 合格" if is_pass else "❌ 不合格"
        pass_item = QTableWidgetItem(pass_text)
        pass_item.setForeground(QColor("#00ff88") if is_pass else QColor("#ff3366"))
        self.result_table.setItem(row, 5, pass_item)

    def _add_multi_band_result_to_table(self, result: dict):
        """添加多频结果到表格"""
        bands = result.get('bands', {})
        if not bands:
            self._add_result_to_table(result)
            return

        row = self.result_table.rowCount()
        self.result_table.insertRow(row)

        self.result_table.setItem(row, 0, QTableWidgetItem(result.get("project_name", "")))

        s11_text = ""
        for band_name, band_info in bands.items():
            s11_val = band_info.get('s11_at_target', 'N/A')
            s11_text += f"{band_name}:{s11_val}dB "

        self.result_table.setItem(row, 1, QTableWidgetItem(s11_text.strip()))

        bw = result.get('bandwidth_10db_ghz', 'N/A')
        bw_text = f"{bw:.4f}" if isinstance(bw, (int, float)) else str(bw)
        self.result_table.setItem(row, 2, QTableWidgetItem(bw_text))

        center = result.get('center_frequency_ghz', 'N/A')
        self.result_table.setItem(row, 3, QTableWidgetItem(str(center)))

        q = result.get('q_value', 'N/A')
        self.result_table.setItem(row, 4, QTableWidgetItem(str(q)))

        is_pass = result.get('is_pass', False)
        pass_text = "✅ 全部合格" if is_pass else "❌ 未达标"
        pass_item = QTableWidgetItem(pass_text)
        pass_item.setForeground(QColor("#00ff88") if is_pass else QColor("#ffaa00"))
        self.result_table.setItem(row, 5, pass_item)

    def _start(self):
        is_file_mode = self.file_mode_rb.isChecked()

        if is_file_mode:
            if not self.selected_files:
                QMessageBox.warning(self, "警告", "请选择至少一个 .aedt 文件")
                return
            source = ""
            file_list = self.selected_files
        else:
            source = self.project_edit.text().strip()
            if not source or not os.path.exists(source):
                QMessageBox.warning(self, "警告", "请设置有效的HFSS项目目录")
                return
            file_list = []

        output_dir = self.output_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "警告", "请设置输出目录")
            return

        self._save_config()

        msg = f"🚀 启动智能工作流\n\n"
        if is_file_mode:
            msg += f"📄 文件模式: {len(self.selected_files)} 个文件\n"
        else:
            msg += f"📁 文件夹模式: {source}\n"
        msg += f"📁 输出目录: {output_dir}\n"
        msg += f"📊 S11阈值: {self.threshold_spin.value()} dB\n"
        msg += f"🤖 LLM诊断: {'启用' if self.use_llm_cb.isChecked() else '禁用'}\n\n继续？"

        reply = QMessageBox.question(self, "确认启动", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        cfg = {
            "source": source,
            "is_file_mode": is_file_mode,
            "file_list": file_list,
            "output_dir": output_dir,
            "threshold": self.threshold_spin.value(),
            "use_llm": self.use_llm_cb.isChecked(),
            "lm_url": self.llm_url_edit.text(),
            "close_hfss": self.close_hfss_cb.isChecked(),
            "force_close_hfss": False,
            "hfss_visible": False,
            "keep_temp": self.keep_temp_cb.isChecked(),
            "generate_report": self.gen_report_cb.isChecked()
        }

        self.worker = WorkflowWorker(cfg)
        self.worker.progress.connect(lambda v, m: self.progress_bar.setValue(v))
        self.worker.log.connect(self._log)
        self.worker.result.connect(self._add_result_to_table)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(lambda e: self._log(f"❌ {e}"))

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.result_table.setRowCount(0)

        self._log("=" * 60)
        self._log("🚀 智能工作流启动")
        self._log(f"📊 S11阈值: {self.threshold_spin.value()} dB")
        self._log(f"🤖 LLM诊断: {'启用' if self.use_llm_cb.isChecked() else '禁用'}")
        self._log("=" * 60)

        self.worker.start()

    def _stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._log("⚠️ 正在停止工作流...")

    def _on_finished(self, stats: dict):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

        self._log("\n" + "=" * 60)
        self._log("✅ 智能工作流完成")
        self._log(f"📊 总计: {stats['total']} | 合格: {stats['passed']} | 通过率: {stats['rate']:.1f}%")
        self._log("=" * 60)

        self.status.showMessage(f"完成 - 通过率: {stats['rate']:.1f}%")

        QMessageBox.information(self, "工作流完成",
                                f"✅ 智能工作流执行完成！\n\n"
                                f"总计项目: {stats['total']}\n"
                                f"合格设计: {stats['passed']}\n"
                                f"不合格设计: {stats['total'] - stats['passed']}\n"
                                f"通过率: {stats['rate']:.1f}%")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 启动画面
    gif_path = r"T:\py_prj\AIHFSS\N1\UI\rf_particle_animation.gif"
    if os.path.exists(gif_path):
        splash_pix = QPixmap(500, 500)
        splash_pix.fill(QColor("#0a0a1a"))
        splash = QSplashScreen(splash_pix)
        splash.setStyleSheet("background-color: #0a0a1a;")
        splash.showMessage("WHYAVE-AI\nAI-Agent驱动射频设计系统\n多频优化版\n正在加载...",
                           Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
                           QColor("#00ffff"))
        splash.show()
        app.processEvents()
    else:
        splash = None

    window = MainWindow()

    if splash:
        splash.finish(window)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()