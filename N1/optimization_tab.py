# -*- coding: utf-8 -*-
"""
无源器件仿真标签页 - AI Agent 优化
整合天线自动优化功能
支持单频优化和双频优化
支持多种器件类型的变量显示
支持 LLM Studio 本地模式和 DeepSeek API 云端模式
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QCheckBox, QTextEdit, QFileDialog,
    QProgressBar, QMessageBox, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QDoubleSpinBox, QSpinBox,
    QComboBox, QSplitter, QRadioButton, QButtonGroup, QFrame,
    QScrollArea
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor, QTextCursor, QBrush

sys.path.insert(0, str(Path(__file__).parent))

# ===== 关键修改：从 antenna_agent 导入，不再是 agent_main =====
from antenna_agent import AntennaAgent, DualBandAntennaAgent
from ai_brain import DecisionMode
from antenna_knowledge_base import MATERIAL_LIBRARY

# 定义各器件类型的变量配置
DEVICE_COLUMN_CONFIG = {
    # 单频天线类
    "微带贴片天线": {
        "columns": ["迭代", "l(mm)", "w(mm)", "w0(mm)", "l0(mm)", "w1(mm)", "d1(mm)", "w2(mm)", "d2(mm)", "S11(dB)",
                    "频率(GHz)", "状态"],
        "param_keys": ['l', 'w', 'w0', 'l0', 'w1', 'd1', 'w2', 'd2'],
        "decimal_places": {'w0': 1, 'l0': 1, 'd1': 1, 'default': 2}
    },
    "缝隙天线": {
        "columns": ["迭代", "slot_l(mm)", "slot_w(mm)", "patch_l(mm)", "patch_w(mm)", "w0(mm)", "l0(mm)", "feed_w(mm)",
                    "feed_offset(mm)", "S11(dB)", "频率(GHz)", "状态"],
        "param_keys": ['slot_l', 'slot_w', 'patch_l', 'patch_w', 'w0', 'l0', 'feed_w', 'feed_offset'],
        "decimal_places": {'w0': 1, 'l0': 1, 'default': 2}
    },
    "PIFA天线": {
        "columns": ["迭代", "patch_l(mm)", "patch_w(mm)", "patch_h(mm)", "short_w(mm)", "feed_x(mm)", "ground_l(mm)",
                    "ground_w(mm)", "S11(dB)", "频率(GHz)", "状态"],
        "param_keys": ['patch_l', 'patch_w', 'patch_h', 'short_w', 'feed_x', 'ground_l', 'ground_w'],
        "decimal_places": {'patch_h': 1, 'ground_l': 1, 'ground_w': 1, 'default': 2}
    },

    # 双频天线类
    "双频微带天线": {
        "columns": ["迭代", "Ls(mm)", "Ws(mm)", "L0(mm)", "W0(mm)", "l1(mm)", "l2(mm)", "低频S11(dB)", "低频频率(GHz)",
                    "高频S11(dB)", "高频频率(GHz)", "状态"],
        "param_keys": ['Ls', 'Ws', 'L0', 'W0', 'l1', 'l2'],
        "decimal_places": {'Ls': 1, 'Ws': 1, 'L0': 2, 'W0': 2, 'l1': 2, 'l2': 2, 'default': 2},
        "is_dual": True
    },
    "双频缝隙天线": {
        "columns": ["迭代", "slot1_l(mm)", "slot1_w(mm)", "slot2_l(mm)", "slot2_w(mm)", "spacing(mm)", "w0(mm)",
                    "l0(mm)", "低频S11(dB)", "低频频率(GHz)", "高频S11(dB)", "高频频率(GHz)", "状态"],
        "param_keys": ['slot1_l', 'slot1_w', 'slot2_l', 'slot2_w', 'spacing', 'w0', 'l0'],
        "decimal_places": {'spacing': 1, 'w0': 1, 'l0': 1, 'default': 2},
        "is_dual": True
    },

    # 滤波器类
    "微带带通滤波器": {
        "columns": ["迭代", "cl1(mm)", "cw1(mm)", "cl2(mm)", "cw2(mm)", "cl3(mm)", "cw3(mm)", "gap1(mm)", "gap2(mm)",
                    "feed_w(mm)", "S21(dB)", "中心频率(GHz)", "带宽(GHz)", "状态"],
        "param_keys": ['cl1', 'cw1', 'cl2', 'cw2', 'cl3', 'cw3', 'gap1', 'gap2', 'feed_w'],
        "decimal_places": {'default': 2},
        "is_filter": True
    },
    "微带低通滤波器": {
        "columns": ["迭代", "high_z_l(mm)", "high_z_w(mm)", "low_z_l(mm)", "low_z_w(mm)", "stages", "feed_w(mm)",
                    "S21(dB)", "截止频率(GHz)", "状态"],
        "param_keys": ['high_z_l', 'high_z_w', 'low_z_l', 'low_z_w', 'stages', 'feed_w'],
        "decimal_places": {'high_z_w': 2, 'low_z_w': 2, 'default': 2},
        "has_stages": True
    },
    "微带高通滤波器": {
        "columns": ["迭代", "cap_l(mm)", "cap_w(mm)", "ind_l(mm)", "ind_w(mm)", "stages", "feed_w(mm)", "S21(dB)",
                    "截止频率(GHz)", "状态"],
        "param_keys": ['cap_l', 'cap_w', 'ind_l', 'ind_w', 'stages', 'feed_w'],
        "decimal_places": {'cap_w': 2, 'ind_w': 2, 'default': 2},
        "has_stages": True
    },

    # 功分器类
    "Wilkinson功分器": {
        "columns": ["迭代", "branch_l(mm)", "branch_w(mm)", "feed_w(mm)", "resistor(Ω)", "angle(°)", "w0(mm)", "l0(mm)",
                    "S11(dB)", "S21(dB)", "S31(dB)", "隔离度(dB)", "状态"],
        "param_keys": ['branch_l', 'branch_w', 'feed_w', 'resistor', 'angle', 'w0', 'l0'],
        "decimal_places": {'branch_w': 2, 'feed_w': 2, 'angle': 0, 'w0': 1, 'l0': 1, 'default': 2},
        "is_power_divider": True
    },
    "T型功分器": {
        "columns": ["迭代", "branch_l(mm)", "branch_w(mm)", "feed_w(mm)", "w0(mm)", "l0(mm)", "S11(dB)", "S21(dB)",
                    "S31(dB)", "状态"],
        "param_keys": ['branch_l', 'branch_w', 'feed_w', 'w0', 'l0'],
        "decimal_places": {'branch_w': 2, 'feed_w': 2, 'w0': 1, 'l0': 1, 'default': 2},
        "is_power_divider": True
    },
}


class OptimizationWorker(QThread):
    """单频优化工作线程"""

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    iteration_signal = pyqtSignal(dict)
    best_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.agent: Optional[AntennaAgent] = None
        self._is_running = True

    def stop(self):
        self._is_running = False
        if self.agent:
            self.agent.stop()

    def run(self):
        try:
            import io

            class EmittingStream(io.StringIO):
                def __init__(self, signal):
                    super().__init__()
                    self.signal = signal

                def write(self, text):
                    if text and text.strip():
                        self.signal.emit(text.strip())
                    super().write(text)

                def flush(self):
                    pass

            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = EmittingStream(self.log_signal)
            sys.stderr = EmittingStream(self.log_signal)

            try:
                mode_map = {
                    'llm': DecisionMode.LLM_ONLY,
                    'rule': DecisionMode.RULE_ONLY,
                    'rule_first': DecisionMode.RULE_FIRST_LLM_FALLBACK,
                    'llm_first': DecisionMode.LLM_FIRST_RULE_FALLBACK,
                    'hybrid': DecisionMode.HYBRID,
                }

                self.agent = AntennaAgent(
                    material_name=self.config.get('material', 'FR4'),
                    target_freq=self.config.get('target_freq', 2.45),
                    target_s11=self.config.get('target_s11', -15),
                    max_iterations=self.config.get('max_iterations', 20),
                    decision_mode=mode_map.get(self.config.get('mode', 'llm'), DecisionMode.LLM_ONLY),
                    llm_url=self.config.get('llm_url', 'http://localhost:1234/v1'),
                    model_name=self.config.get('model_name', 'qwen2.5-coder-7b-instruct'),
                    llm_service=self.config.get('llm_service', 'llm_studio'),
                    api_key=self.config.get('api_key', None),
                    work_dir=self.config.get('work_dir', 'T:/HFSS_Agent_Workspace'),
                    template_project=self.config.get('project_path', ''),
                    device_type=self.config.get('device_type', '微带贴片天线'),
                )

                self.agent.on_iteration = self._on_iteration
                self.agent.on_decision = self._on_decision
                self.agent.on_best = self._on_best

                model = self.config.get('model_name', 'qwen2.5-coder-7b-instruct')
                service_names = {
                    "llm_studio": "LLM Studio (本地)",
                    "deepseek_api": "DeepSeek API (云端)",
                    "ollama": "Ollama (本地)"
                }
                service = self.config.get('llm_service', 'llm_studio')

                self.log_signal.emit("=" * 60)
                self.log_signal.emit("🤖 AI Agent 优化启动")
                self.log_signal.emit(f"   材料: {self.config.get('material', 'FR4')}")
                self.log_signal.emit(
                    f"   目标: {self.config.get('target_freq', 2.45)} GHz, S11 < {self.config.get('target_s11', -15)} dB")
                self.log_signal.emit(f"   LLM服务: {service_names.get(service, service)}")
                self.log_signal.emit(f"   模型: {model}")
                self.log_signal.emit(f"   模式: {self.config.get('mode', 'llm')}")
                self.log_signal.emit(f"   器件: {self.config.get('device_type', '微带贴片天线')}")
                self.log_signal.emit("=" * 60)

                final_result = self.agent.optimize()

                if self._is_running:
                    self.finished_signal.emit(final_result)

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        except Exception as e:
            self.error_signal.emit(str(e))
            import traceback
            self.log_signal.emit(traceback.format_exc())

    def _on_iteration(self, iteration: int, params: Dict, result: Dict):
        self.progress_signal.emit(iteration, self.config.get('max_iterations', 20))

        data = {
            'iteration': iteration,
            'params': params.copy(),
            's11': result.get('s11_min_db', 0),
            'freq': result.get('frequency_at_min_ghz', 0),
            'bw': result.get('bandwidth_under_10db_ghz', 0),
            'is_pass': result.get('is_pass', False),
        }
        self.iteration_signal.emit(data)

    def _on_best(self, iteration: int, params: Dict, result: Dict):
        data = {
            'iteration': iteration,
            'params': params.copy(),
            's11': result.get('s11_min_db', 0),
            'freq': result.get('frequency_at_min_ghz', 0),
            'bw': result.get('bandwidth_under_10db_ghz', 0),
            'is_pass': result.get('is_pass', False),
        }
        self.best_signal.emit(data)

    def _on_decision(self, decision):
        model_tag = f"[{decision.model_name}] " if decision.model_name else ""
        self.log_signal.emit(f"🧠 {model_tag}{decision.analysis}")
        self.log_signal.emit(f"📋 {decision.strategy}")


class DualBandOptimizationWorker(QThread):
    """双频优化工作线程"""

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    iteration_signal = pyqtSignal(dict)
    best_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.agent: Optional[DualBandAntennaAgent] = None
        self._is_running = True

    def stop(self):
        self._is_running = False
        if self.agent:
            self.agent.stop()

    def run(self):
        try:
            import io

            class EmittingStream(io.StringIO):
                def __init__(self, signal):
                    super().__init__()
                    self.signal = signal

                def write(self, text):
                    if text and text.strip():
                        self.signal.emit(text.strip())
                    super().write(text)

                def flush(self):
                    pass

            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = EmittingStream(self.log_signal)
            sys.stderr = EmittingStream(self.log_signal)

            try:
                mode_map = {
                    'llm': DecisionMode.LLM_ONLY,
                    'rule': DecisionMode.RULE_ONLY,
                    'rule_first': DecisionMode.RULE_FIRST_LLM_FALLBACK,
                    'llm_first': DecisionMode.LLM_FIRST_RULE_FALLBACK,
                    'hybrid': DecisionMode.HYBRID,
                }

                self.agent = DualBandAntennaAgent(
                    material_name=self.config.get('material', 'FR4'),
                    target_freqs=self.config.get('target_freqs', [2.45, 5.0]),
                    target_s11=self.config.get('target_s11', -15),
                    max_iterations=self.config.get('max_iterations', 30),
                    decision_mode=mode_map.get(self.config.get('mode', 'llm'), DecisionMode.LLM_ONLY),
                    llm_url=self.config.get('llm_url', 'http://localhost:1234/v1'),
                    model_name=self.config.get('model_name', 'deepseek-v4-pro'),
                    llm_service=self.config.get('llm_service', 'llm_studio'),
                    api_key=self.config.get('api_key', None),
                    work_dir=self.config.get('work_dir', 'T:/HFSS_Agent_Workspace'),
                    template_project=self.config.get('project_path', ''),
                    device_type=self.config.get('device_type', '双频微带天线'),
                )

                self.agent.on_iteration = self._on_iteration
                self.agent.on_best = self._on_best

                model = self.config.get('model_name', 'deepseek-v4-pro')
                service_names = {
                    "llm_studio": "LLM Studio (本地)",
                    "deepseek_api": "DeepSeek API (云端)",
                    "ollama": "Ollama (本地)"
                }
                service = self.config.get('llm_service', 'llm_studio')
                target_freqs = self.config.get('target_freqs', [2.45, 5.0])

                self.log_signal.emit("=" * 60)
                self.log_signal.emit("🤖 AI Agent 双频优化启动")
                self.log_signal.emit(f"   材料: {self.config.get('material', 'FR4')}")
                self.log_signal.emit(
                    f"   目标低频: {target_freqs[0]} GHz, S11 < {self.config.get('target_s11', -15)} dB")
                self.log_signal.emit(
                    f"   目标高频: {target_freqs[1]} GHz, S11 < {self.config.get('target_s11', -15)} dB")
                self.log_signal.emit(f"   LLM服务: {service_names.get(service, service)}")
                self.log_signal.emit(f"   模型: {model}")
                self.log_signal.emit(f"   模式: {self.config.get('mode', 'llm')}")
                self.log_signal.emit(f"   器件: {self.config.get('device_type', '双频微带天线')}")
                self.log_signal.emit("=" * 60)

                final_result = self.agent.optimize()

                if self._is_running:
                    self.finished_signal.emit(final_result)

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        except Exception as e:
            self.error_signal.emit(str(e))
            import traceback
            self.log_signal.emit(traceback.format_exc())

    def _on_iteration(self, iteration: int, params: Dict, result: Dict):
        self.progress_signal.emit(iteration, self.config.get('max_iterations', 30))

        data = {
            'iteration': iteration,
            'params': params.copy(),
            'result': result,
            'low_s11': result.get('low_s11', 0),
            'high_s11': result.get('high_s11', 0),
            'low_freq_error': result.get('low_freq_error', 0),
            'high_freq_error': result.get('high_freq_error', 0),
            'is_pass': result.get('is_pass', False),
            'overall_score': result.get('overall_score', 0),
        }
        self.iteration_signal.emit(data)

    def _on_best(self, iteration: int, params: Dict, result: Dict):
        data = {
            'iteration': iteration,
            'params': params.copy(),
            'result': result,
            'low_s11': result.get('low_s11', 0),
            'high_s11': result.get('high_s11', 0),
            'low_freq_error': result.get('low_freq_error', 0),
            'high_freq_error': result.get('high_freq_error', 0),
            'is_pass': result.get('is_pass', False),
            'overall_score': result.get('overall_score', 0),
        }
        self.best_signal.emit(data)


class OptimizationTab(QWidget):
    """无源器件仿真标签页"""

    def __init__(self, config: Dict = None):
        super().__init__()
        self.config = config or {}
        self.worker: Optional[OptimizationWorker] = None
        self.dual_worker: Optional[DualBandOptimizationWorker] = None
        self.best_result: Optional[Dict] = None
        self.iteration_results: list = []
        self.is_dual_mode = False
        self.current_device_type = "微带贴片天线"
        self.current_column_config = None

        # 用于高亮显示最佳行
        self._best_dual_score = 0
        self._best_dual_row = -1
        self._best_single_score = 0
        self._best_single_row = -1

        # 先初始化UI组件为None
        self.result_table = None
        self.log_text = None
        self.best_label = None
        self.progress_bar = None
        self.start_btn = None
        self.stop_btn = None
        self.device_type_combo = None
        self.sim_type_combo = None
        self.single_freq_rb = None
        self.dual_freq_rb = None
        self.single_freq_group = None
        self.dual_freq_group = None
        self.freq_spin = None
        self.s11_spin = None
        self.low_freq_spin = None
        self.low_s11_spin = None
        self.high_freq_spin = None
        self.high_s11_spin = None
        self.project_edit = None
        self.workdir_edit = None
        self.material_combo = None
        self.iter_spin = None
        self.model_combo = None
        self.mode_combo = None
        self.llm_edit = None
        self.llm_service_combo = None
        self.api_key_edit = None
        self.llm_status = None
        self.chat_input = None

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = self._create_config_panel()
        splitter.addWidget(left_panel)

        right_panel = self._create_result_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([450, 850])
        main_layout.addWidget(splitter)

    def _create_result_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 迭代历史表格
        table_group = QGroupBox("📊 迭代历史")
        table_layout = QVBoxLayout(table_group)

        self.result_table = QTableWidget()
        self._setup_default_table_columns()

        table_layout.addWidget(self.result_table)
        layout.addWidget(table_group, stretch=3)

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

        layout.addWidget(log_group, stretch=2)

        return panel

    def _setup_default_table_columns(self):
        """设置默认表格列"""
        default_columns = ["迭代", "l(mm)", "w(mm)", "w0(mm)", "l0(mm)",
                           "w1(mm)", "d1(mm)", "w2(mm)", "d2(mm)",
                           "S11(dB)", "频率(GHz)", "状态"]
        self.result_table.setColumnCount(len(default_columns))
        self.result_table.setHorizontalHeaderLabels(default_columns)

        widths = [40, 50, 50, 50, 50, 45, 45, 45, 45, 70, 70, 60]
        for i, w in enumerate(widths):
            if i < len(default_columns):
                self.result_table.setColumnWidth(i, w)

        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.result_table.setAlternatingRowColors(True)

    def _update_result_table_columns(self):
        """根据当前器件类型更新结果表格列"""
        if self.result_table is None:
            return

        device_type = self.device_type_combo.currentText()
        config = DEVICE_COLUMN_CONFIG.get(device_type, DEVICE_COLUMN_CONFIG["微带贴片天线"])
        self.current_column_config = config

        columns = config["columns"]
        self.result_table.setColumnCount(len(columns))
        self.result_table.setHorizontalHeaderLabels(columns)

        widths = [40]
        for i in range(1, len(columns)):
            col_name = columns[i]
            if "S11" in col_name:
                widths.append(70)
            elif "频率" in col_name or "GHz" in col_name:
                widths.append(70)
            elif "频偏" in col_name:
                widths.append(70)
            elif "状态" in col_name:
                widths.append(60)
            elif "mm" in col_name:
                widths.append(55)
            else:
                widths.append(55)

        while len(widths) < len(columns):
            widths.append(55)

        for i, w in enumerate(widths):
            if i < len(columns):
                self.result_table.setColumnWidth(i, w)

        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.result_table.setAlternatingRowColors(True)

    def _create_config_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        panel.setMaximumWidth(450)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # ===== 智能对话输入区 =====
        chat_group = QGroupBox("💬 快速启动（智能识别）")
        chat_layout = QVBoxLayout(chat_group)

        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("")
        self.chat_input.setStyleSheet("padding: 8px; font-size: 13px; min-height: 60px;")
        self.chat_input.returnPressed.connect(self.smart_start)
        input_layout.addWidget(self.chat_input)

        self.smart_start_btn = QPushButton("🚀 智能启动")
        self.smart_start_btn.setStyleSheet(
            "background-color: #2196F3; color: white; font-weight: bold; padding: 10px;"
        )
        self.smart_start_btn.clicked.connect(self.smart_start)
        input_layout.addWidget(self.smart_start_btn)

        chat_layout.addLayout(input_layout)

        examples_label = QLabel(
            "💡 示例: '2.45GHz S11<-15dB' | '5.8GHz 双频天线' | '双频 2.45G/5G' | 'WiFi双频天线' | '带通滤波器 2.4GHz'"
        )
        examples_label.setStyleSheet("color: #6080a0; font-size: 11px; padding: 5px;")
        examples_label.setWordWrap(True)
        chat_layout.addWidget(examples_label)

        scroll_layout.addWidget(chat_group)

        # ===== 仿真类型 + 器件类型选择 =====
        type_group = QGroupBox("📡 仿真配置")
        type_layout = QGridLayout(type_group)

        type_layout.addWidget(QLabel("仿真类型:"), 0, 0)
        self.sim_type_combo = QComboBox()
        self.sim_type_combo.addItems(["单频天线", "双频天线", "滤波器", "功分器"])
        self.sim_type_combo.setToolTip("选择仿真场景类型")
        self.sim_type_combo.currentTextChanged.connect(self._on_sim_type_changed)
        type_layout.addWidget(self.sim_type_combo, 0, 1)

        type_layout.addWidget(QLabel("器件类型:"), 1, 0)
        self.device_type_combo = QComboBox()
        self.device_type_combo.setToolTip("选择具体器件类型")
        self.device_type_combo.currentTextChanged.connect(self._on_device_type_changed)
        type_layout.addWidget(self.device_type_combo, 1, 1)

        scroll_layout.addWidget(type_group)

        # ===== 优化模式选择 =====
        mode_group = QGroupBox("🔧 优化模式")
        mode_layout = QHBoxLayout(mode_group)

        self.single_freq_rb = QRadioButton("单频优化")
        self.single_freq_rb.setChecked(True)
        self.dual_freq_rb = QRadioButton("双频优化")

        self.single_freq_rb.toggled.connect(self._on_optimization_mode_changed)
        self.dual_freq_rb.toggled.connect(self._on_optimization_mode_changed)

        mode_layout.addWidget(self.single_freq_rb)
        mode_layout.addWidget(self.dual_freq_rb)
        mode_layout.addStretch()

        scroll_layout.addWidget(mode_group)

        # ===== 单频优化设置 =====
        self.single_freq_group = QGroupBox("🎯 单频优化设置")
        single_layout = QGridLayout(self.single_freq_group)

        single_layout.addWidget(QLabel("目标频率 (GHz):"), 0, 0)
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.5, 10.0)
        self.freq_spin.setValue(2.45)
        self.freq_spin.setSingleStep(0.05)
        self.freq_spin.setDecimals(2)
        single_layout.addWidget(self.freq_spin, 0, 1)

        single_layout.addWidget(QLabel("目标 S11 (dB):"), 1, 0)
        self.s11_spin = QDoubleSpinBox()
        self.s11_spin.setRange(-40, 0)
        self.s11_spin.setValue(-15)
        self.s11_spin.setSingleStep(1)
        single_layout.addWidget(self.s11_spin, 1, 1)

        scroll_layout.addWidget(self.single_freq_group)

        # ===== 双频优化设置 =====
        self.dual_freq_group = QGroupBox("🎯 双频优化设置")
        dual_layout = QGridLayout(self.dual_freq_group)

        dual_layout.addWidget(QLabel("低频 (GHz):"), 0, 0)
        self.low_freq_spin = QDoubleSpinBox()
        self.low_freq_spin.setRange(0.5, 6.0)
        self.low_freq_spin.setValue(2.45)
        self.low_freq_spin.setSingleStep(0.05)
        self.low_freq_spin.setDecimals(2)
        dual_layout.addWidget(self.low_freq_spin, 0, 1)

        dual_layout.addWidget(QLabel("低频 S11 (dB):"), 0, 2)
        self.low_s11_spin = QDoubleSpinBox()
        self.low_s11_spin.setRange(-40, 0)
        self.low_s11_spin.setValue(-15)
        self.low_s11_spin.setSingleStep(1)
        dual_layout.addWidget(self.low_s11_spin, 0, 3)

        dual_layout.addWidget(QLabel("高频 (GHz):"), 1, 0)
        self.high_freq_spin = QDoubleSpinBox()
        self.high_freq_spin.setRange(2.0, 10.0)
        self.high_freq_spin.setValue(5.0)
        self.high_freq_spin.setSingleStep(0.1)
        self.high_freq_spin.setDecimals(2)
        dual_layout.addWidget(self.high_freq_spin, 1, 1)

        dual_layout.addWidget(QLabel("高频 S11 (dB):"), 1, 2)
        self.high_s11_spin = QDoubleSpinBox()
        self.high_s11_spin.setRange(-40, 0)
        self.high_s11_spin.setValue(-15)
        self.high_s11_spin.setSingleStep(1)
        dual_layout.addWidget(self.high_s11_spin, 1, 3)

        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("常用预设:"))

        wifi24_btn = QPushButton("2.4G+5G WiFi")
        wifi24_btn.clicked.connect(lambda: self._set_dual_preset(2.45, -15, 5.0, -15))
        preset_layout.addWidget(wifi24_btn)

        wifi6_btn = QPushButton("2.4G+5.8G")
        wifi6_btn.clicked.connect(lambda: self._set_dual_preset(2.45, -15, 5.8, -15))
        preset_layout.addWidget(wifi6_btn)

        dual_btn = QPushButton("1.8G+2.45G")
        dual_btn.clicked.connect(lambda: self._set_dual_preset(1.8, -15, 2.45, -15))
        preset_layout.addWidget(dual_btn)

        dual_layout.addLayout(preset_layout, 2, 0, 1, 4)

        scroll_layout.addWidget(self.dual_freq_group)

        self.dual_freq_group.setVisible(False)

        # ===== 项目配置 =====
        project_group = QGroupBox("📁 项目配置")
        project_layout = QGridLayout(project_group)

        project_layout.addWidget(QLabel("HFSS 项目:"), 0, 0)
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("选择 .aedt 文件")
        self.project_edit.setText("T:/AnsysPrj/AI-Patch.aedt")
        project_layout.addWidget(self.project_edit, 0, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_project)
        project_layout.addWidget(browse_btn, 0, 2)

        project_layout.addWidget(QLabel("工作目录:"), 1, 0)
        self.workdir_edit = QLineEdit("T:/HFSS_Agent_Workspace")
        project_layout.addWidget(self.workdir_edit, 1, 1)

        workdir_btn = QPushButton("浏览...")
        workdir_btn.clicked.connect(self.browse_workdir)
        project_layout.addWidget(workdir_btn, 1, 2)

        scroll_layout.addWidget(project_group)

        # ===== 材料选择 =====
        material_group = QGroupBox("📐 材料设置")
        material_layout = QGridLayout(material_group)

        material_layout.addWidget(QLabel("介质材料:"), 0, 0)
        self.material_combo = QComboBox()
        self.material_combo.addItems(list(MATERIAL_LIBRARY.keys()))
        material_layout.addWidget(self.material_combo, 0, 1)

        material_layout.addWidget(QLabel("最大迭代次数:"), 1, 0)
        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(3, 100)
        self.iter_spin.setValue(20)
        material_layout.addWidget(self.iter_spin, 1, 1)

        scroll_layout.addWidget(material_group)

        # ===== AI 配置 =====
        ai_group = QGroupBox("🤖 AI 配置")
        ai_layout = QGridLayout(ai_group)

        # LLM 服务选择
        ai_layout.addWidget(QLabel("LLM 服务:"), 0, 0)
        self.llm_service_combo = QComboBox()
        self.llm_service_combo.addItems([
            "llm_studio (本地)",
            "deepseek_api (云端)",
            "ollama (本地)"
        ])
        self.llm_service_combo.setCurrentText("llm_studio (本地)")
        self.llm_service_combo.currentTextChanged.connect(self._on_llm_service_changed)
        ai_layout.addWidget(self.llm_service_combo, 0, 1)

        # AI 模型选择
        ai_layout.addWidget(QLabel("AI 模型:"), 1, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "qwen2.5-coder-7b-instruct",
        ])
        self.model_combo.setCurrentText("qwen2.5-coder-7b-instruct")
        self.model_combo.setToolTip("选择本地部署的大模型")
        ai_layout.addWidget(self.model_combo, 1, 1)

        # API 地址
        ai_layout.addWidget(QLabel("API 地址:"), 2, 0)
        self.llm_edit = QLineEdit("http://localhost:1234/v1")
        self.llm_edit.setToolTip("LLM Studio 默认: http://localhost:1234/v1")
        ai_layout.addWidget(self.llm_edit, 2, 1)

        # API Key（默认隐藏）
        ai_layout.addWidget(QLabel("API Key:"), 3, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("输入 DeepSeek API Key (sk-...)")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setVisible(False)
        ai_layout.addWidget(self.api_key_edit, 3, 1)

        # 决策模式
        ai_layout.addWidget(QLabel("决策模式:"), 4, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['llm', 'rule', 'hybrid', 'rule_first', 'llm_first'])
        self.mode_combo.setCurrentText('llm')
        self.mode_combo.setToolTip("llm: 纯大模型决策\nrule: 纯物理规则\nhybrid: 规则+大模型验证")
        ai_layout.addWidget(self.mode_combo, 4, 1)

        # 测试连接按钮
        test_llm_btn = QPushButton("测试连接")
        test_llm_btn.clicked.connect(self.test_llm)
        ai_layout.addWidget(test_llm_btn, 5, 0, 1, 2)

        # LLM 状态
        self.llm_status = QLabel("⚫ 未检测")
        self.llm_status.setStyleSheet("padding: 3px; color: #6080a0;")
        ai_layout.addWidget(self.llm_status, 6, 0, 1, 2)

        scroll_layout.addWidget(ai_group)

        # ===== 控制按钮 =====
        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶ 开始优化")
        self.start_btn.setObjectName("start_btn")
        self.start_btn.setStyleSheet("""
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
        self.start_btn.clicked.connect(self.start_optimization)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■ 停止")
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
        self.stop_btn.clicked.connect(self.stop_optimization)
        btn_layout.addWidget(self.stop_btn)

        scroll_layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()
        scroll_layout.addWidget(self.progress_bar)

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
        scroll_layout.addWidget(best_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # 最后初始化器件选项
        self._update_device_options()

        return panel

    def _update_device_options(self):
        """根据仿真类型更新器件选项"""
        if self.sim_type_combo is None or self.device_type_combo is None:
            return

        sim_type = self.sim_type_combo.currentText()
        device_map = {
            "单频天线": ["微带贴片天线", "缝隙天线", "PIFA天线"],
            "双频天线": ["双频微带天线", "双频缝隙天线"],
            "滤波器": ["微带带通滤波器", "微带低通滤波器", "微带高通滤波器"],
            "功分器": ["Wilkinson功分器", "T型功分器"],
        }
        current_text = self.device_type_combo.currentText()
        self.device_type_combo.clear()
        self.device_type_combo.addItems(device_map.get(sim_type, ["微带贴片天线"]))

        idx = self.device_type_combo.findText(current_text)
        if idx >= 0:
            self.device_type_combo.setCurrentIndex(idx)

    def _on_sim_type_changed(self, sim_type: str):
        """根据仿真类型更新器件选项"""
        self._update_device_options()

    def _on_device_type_changed(self, device_type: str):
        """根据器件类型自动切换优化模式"""
        if self.result_table is None:
            return

        self.current_device_type = device_type

        config = DEVICE_COLUMN_CONFIG.get(device_type, DEVICE_COLUMN_CONFIG["微带贴片天线"])

        if config.get("is_dual", False):
            self.dual_freq_rb.setChecked(True)
        else:
            self.single_freq_rb.setChecked(True)

        self._update_result_table_columns()

    def _on_optimization_mode_changed(self):
        """优化模式切换"""
        if self.single_freq_group is None or self.dual_freq_group is None:
            return

        is_dual = self.dual_freq_rb.isChecked()
        self.is_dual_mode = is_dual
        self.single_freq_group.setVisible(not is_dual)
        self.dual_freq_group.setVisible(is_dual)

        if is_dual:
            if "双频" not in self.device_type_combo.currentText():
                idx = self.device_type_combo.findText("双频微带天线")
                if idx >= 0:
                    self.device_type_combo.setCurrentIndex(idx)
            self.iter_spin.setValue(30)
        else:
            if "双频" in self.device_type_combo.currentText():
                idx = self.device_type_combo.findText("微带贴片天线")
                if idx >= 0:
                    self.device_type_combo.setCurrentIndex(idx)
            self.iter_spin.setValue(20)

        self._update_result_table_columns()

    def _on_llm_service_changed(self, service: str):
        """LLM 服务切换 - 支持本地和云端"""
        is_deepseek = "deepseek" in service.lower()

        # 显示/隐藏 API Key 输入框
        self.api_key_edit.setVisible(is_deepseek)

        if is_deepseek:
            # 云端 DeepSeek 模式
            self.llm_edit.setText("https://api.deepseek.com/v1")
            self.llm_edit.setToolTip("DeepSeek API 地址")
            self.model_combo.clear()
            self.model_combo.addItems([
                "deepseek-v4-pro",
                "deepseek-chat",
                "deepseek-reasoner"
            ])
            self.model_combo.setCurrentText("deepseek-v4-pro")
            self.llm_status.setText("🔑 请输入 API Key")
            self.llm_status.setStyleSheet("padding: 3px; color: #ffaa00;")
        else:
            # 本地模式 (LLM Studio 或 Ollama)
            self.api_key_edit.setVisible(False)
            self.api_key_edit.clear()

            if "ollama" in service.lower():
                self.llm_edit.setText("http://localhost:11434")
                self.llm_edit.setToolTip("Ollama 本地服务")
                self.model_combo.clear()
                self.model_combo.addItems([
                    "qwen2.5:7b",
                    "qwen2.5:14b",
                    "llama3.1:8b",
                    "deepseek-r1:7b"
                ])
                self.model_combo.setCurrentText("qwen2.5:7b")
            else:
                # LLM Studio
                self.llm_edit.setText("http://localhost:1234/v1")
                self.llm_edit.setToolTip("LM Studio 本地服务")
                self.model_combo.clear()
                self.model_combo.addItems([
                    "qwen2.5-coder-7b-instruct"
                ])
                self.model_combo.setCurrentText("qwen2.5-coder-7b-instruct")

            self.llm_status.setText("⚫ 本地模式")
            self.llm_status.setStyleSheet("padding: 3px; color: #6080a0;")

    def _set_dual_preset(self, low_freq: float, low_s11: float, high_freq: float, high_s11: float):
        """设置双频预设值"""
        self.low_freq_spin.setValue(low_freq)
        self.low_s11_spin.setValue(low_s11)
        self.high_freq_spin.setValue(high_freq)
        self.high_s11_spin.setValue(high_s11)

        self.dual_freq_rb.setChecked(True)

        self._append_log(f"📌 已加载预设: {low_freq}GHz/{high_freq}GHz, S11<{low_s11}/{high_s11}dB")

    def browse_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 HFSS 项目", "", "HFSS Project (*.aedt);;All Files (*)"
        )
        if path:
            self.project_edit.setText(path)

    def browse_workdir(self):
        path = QFileDialog.getExistingDirectory(self, "选择工作目录")
        if path:
            self.workdir_edit.setText(path)

    def test_llm(self):
        """测试 LLM 连接"""
        import requests

        url = self.llm_edit.text().strip()
        service = self.llm_service_combo.currentText()
        is_deepseek = "deepseek" in service.lower()

        try:
            if is_deepseek:
                # DeepSeek API 测试
                api_key = self.api_key_edit.text().strip()
                if not api_key:
                    QMessageBox.warning(self, "警告", "请输入 DeepSeek API Key")
                    return

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                resp = requests.post(
                    f"{url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model_combo.currentText(),
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1
                    },
                    timeout=5
                )
                if resp.status_code == 200:
                    self.llm_status.setText("✅ DeepSeek 云端连接成功")
                    self.llm_status.setStyleSheet(
                        "padding: 3px; color: #00ff88; background: #0d2a1a; border-radius: 3px;")
                    QMessageBox.information(self, "成功",
                                            "DeepSeek API 连接成功！\n模型: " + self.model_combo.currentText())
                else:
                    self.llm_status.setText(f"❌ 连接失败: HTTP {resp.status_code}")
                    self.llm_status.setStyleSheet("padding: 3px; color: #ff3366;")
                    QMessageBox.warning(self, "失败", f"连接失败: HTTP {resp.status_code}\n请检查 API Key 是否正确")
            else:
                # 本地服务测试
                resp = requests.get(f"{url}/models", timeout=5)
                if resp.status_code == 200:
                    self.llm_status.setText("✅ 本地 LLM 服务可用")
                    self.llm_status.setStyleSheet(
                        "padding: 3px; color: #00ff88; background: #0d2a1a; border-radius: 3px;")
                    QMessageBox.information(self, "成功", "本地 LLM 服务连接成功！")
                else:
                    self.llm_status.setText("❌ 连接失败")
                    self.llm_status.setStyleSheet("padding: 3px; color: #ff3366;")
                    QMessageBox.warning(self, "失败", "无法连接到本地 LLM 服务\n请确保 LM Studio 或 Ollama 已启动")

        except requests.exceptions.ConnectionError:
            self.llm_status.setText("❌ 无法连接")
            self.llm_status.setStyleSheet("padding: 3px; color: #ff3366;")
            QMessageBox.warning(self, "错误", "无法连接到服务\n请检查地址是否正确，服务是否已启动")
        except Exception as e:
            self.llm_status.setText("❌ 错误")
            self.llm_status.setStyleSheet("padding: 3px; color: #ff3366;")
            QMessageBox.warning(self, "错误", f"连接失败: {e}")

    def _parse_requirements(self, text: str) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        """解析用户输入"""
        freq = None
        s11 = None
        sim_type = None
        device_type = None

        text_lower = text.lower()

        freq_match = re.search(r'(\d+\.?\d*)\s*(GHz|Ghz|ghz|G\b)', text)
        if freq_match:
            freq = float(freq_match.group(1))
        else:
            mhz_match = re.search(r'(\d+)\s*(MHz|Mhz|mhz)', text)
            if mhz_match:
                freq = float(mhz_match.group(1)) / 1000

        s11_match = re.search(r'[<≤]?\s*(-?\d+\.?\d*)\s*dB', text)
        if s11_match:
            s11 = float(s11_match.group(1))

        sim_type_keywords = {
            "单频天线": ["单频", "贴片天线", "微带天线", "patch"],
            "双频天线": ["双频", "dual", "双波段", "wifi双频"],
            "滤波器": ["滤波器", "filter", "带通", "低通", "高通"],
            "功分器": ["功分器", "power divider", "wilkinson"],
        }

        for sim, keywords in sim_type_keywords.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    sim_type = sim
                    break
            if sim_type:
                break

        device_keywords = {
            "微带贴片天线": ["贴片", "patch"],
            "缝隙天线": ["缝隙", "slot"],
            "PIFA天线": ["pifa"],
            "双频微带天线": ["双频贴片", "双频微带"],
            "微带带通滤波器": ["带通", "bandpass"],
            "微带低通滤波器": ["低通", "lowpass"],
            "微带高通滤波器": ["高通", "highpass"],
            "Wilkinson功分器": ["wilkinson", "威尔金森"],
            "T型功分器": ["t型", "t-junction"],
        }

        for device, keywords in device_keywords.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    device_type = device
                    break
            if device_type:
                break

        return freq, s11, sim_type, device_type

    def smart_start(self):
        """智能启动"""
        text = self.chat_input.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入设计需求")
            return

        is_dual = any(kw in text.lower() for kw in ['双频', 'dual', '双波段', '2.4g+5g', 'wifi双频'])

        if is_dual:
            freqs = re.findall(r'(\d+\.?\d*)\s*[gG]', text)
            if len(freqs) >= 2:
                low_freq = float(freqs[0])
                high_freq = float(freqs[1])
                self.low_freq_spin.setValue(low_freq)
                self.high_freq_spin.setValue(high_freq)

                s11_match = re.search(r'[<≤]?\s*(-?\d+\.?\d*)\s*dB', text)
                if s11_match:
                    target_s11 = float(s11_match.group(1))
                    self.low_s11_spin.setValue(target_s11)
                    self.high_s11_spin.setValue(target_s11)

                self.dual_freq_rb.setChecked(True)
                self._append_log(f"🔍 解析到双频需求: {low_freq}GHz / {high_freq}GHz")
                self.start_optimization()
                return

        freq, s11, sim_type, device_type = self._parse_requirements(text)

        if freq is not None:
            self.freq_spin.setValue(freq)
        if s11 is not None:
            self.s11_spin.setValue(s11)
        if sim_type is not None:
            idx = self.sim_type_combo.findText(sim_type)
            if idx >= 0:
                self.sim_type_combo.setCurrentIndex(idx)
        if device_type is not None:
            idx = self.device_type_combo.findText(device_type)
            if idx >= 0:
                self.device_type_combo.setCurrentIndex(idx)

        self.single_freq_rb.setChecked(True)
        self.start_optimization()

    def start_optimization(self):
        """开始优化"""
        project_path = self.project_edit.text().strip()
        if not project_path or not os.path.exists(project_path):
            QMessageBox.warning(self, "警告", "请选择有效的 HFSS 项目文件")
            return

        is_dual = self.dual_freq_rb.isChecked()
        device_type = self.device_type_combo.currentText()

        config_info = DEVICE_COLUMN_CONFIG.get(device_type, DEVICE_COLUMN_CONFIG["微带贴片天线"])
        self.current_column_config = config_info

        # 获取 LLM 服务配置
        service_text = self.llm_service_combo.currentText()
        if "deepseek" in service_text.lower():
            llm_service = "deepseek_api"
            api_key = self.api_key_edit.text().strip()
            if not api_key:
                QMessageBox.warning(self, "警告", "DeepSeek 模式需要输入 API Key")
                return
        elif "ollama" in service_text.lower():
            llm_service = "ollama"
            api_key = None
        else:
            llm_service = "llm_studio"
            api_key = None

        try:
            if is_dual:
                low_freq = self.low_freq_spin.value()
                high_freq = self.high_freq_spin.value()
                low_s11 = self.low_s11_spin.value()
                high_s11 = self.high_s11_spin.value()
                target_s11 = min(low_s11, high_s11)
                target_freqs = [low_freq, high_freq]
                iterations = self.iter_spin.value()
            else:
                target_freq = self.freq_spin.value()
                target_s11 = self.s11_spin.value()
                target_freqs = None
                iterations = self.iter_spin.value()
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的数值")
            return

        self.result_table.setRowCount(0)
        self._best_dual_score = 0
        self._best_dual_row = -1
        self._best_single_score = 0
        self._best_single_row = -1
        self.best_result = None

        self.log_text.clear()
        self.best_label.setText("优化中...")
        self.best_result = None
        self.iteration_results.clear()

        self._update_result_table_columns()

        config = {
            'project_path': project_path,
            'work_dir': self.workdir_edit.text().strip(),
            'material': self.material_combo.currentText(),
            'target_s11': target_s11,
            'max_iterations': iterations,
            'mode': self.mode_combo.currentText(),
            'model_name': self.model_combo.currentText(),
            'llm_url': self.llm_edit.text().strip(),
            'llm_service': llm_service,
            'api_key': api_key,
            'sim_type': self.sim_type_combo.currentText(),
            'device_type': device_type,
        }

        if is_dual:
            config['target_freqs'] = target_freqs
            config['target_freq'] = target_freqs[0]
            config['is_dual_band'] = True

            self.dual_worker = DualBandOptimizationWorker(config)
            self.dual_worker.log_signal.connect(self._append_log)
            self.dual_worker.progress_signal.connect(self.update_progress)
            self.dual_worker.iteration_signal.connect(self.add_dual_iteration_result)
            self.dual_worker.best_signal.connect(self.update_dual_best)
            self.dual_worker.finished_signal.connect(self.on_finished)
            self.dual_worker.error_signal.connect(self.on_error)

            self._append_log(f"🚀 启动双频优化: {target_freqs[0]}GHz / {target_freqs[1]}GHz")
            self._append_log(f"📊 S11目标: {low_s11}dB / {high_s11}dB")
            self._append_log(f"🤖 LLM服务: {llm_service}")

            self.dual_worker.start()
        else:
            config['target_freq'] = target_freq
            config['target_s11'] = target_s11
            config['is_dual_band'] = False

            self.worker = OptimizationWorker(config)
            self.worker.log_signal.connect(self._append_log)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.iteration_signal.connect(self.add_iteration_result)
            self.worker.best_signal.connect(self.update_best)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.error_signal.connect(self.on_error)

            self._append_log(f"🚀 启动单频优化: {target_freq}GHz, S11<{target_s11}dB")
            self._append_log(f"🤖 LLM服务: {llm_service}")

            self.worker.start()

        self._append_log(f"📡 器件类型: {device_type}")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)

    def stop_optimization(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._append_log("⚠️ 正在停止优化...")
        if self.dual_worker and self.dual_worker.isRunning():
            self.dual_worker.stop()
            self._append_log("⚠️ 正在停止优化...")

    def _append_log(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")

        if "✅" in text or "成功" in text:
            formatted = f'<span style="color: #00ff88;">[{timestamp}] {text}</span>'
        elif "❌" in text or "失败" in text or "错误" in text:
            formatted = f'<span style="color: #ff3366;">[{timestamp}] {text}</span>'
        elif "🔍" in text or "解析" in text:
            formatted = f'<span style="color: #00ccff;">[{timestamp}] {text}</span>'
        elif "🧠" in text:
            formatted = f'<span style="color: #ffaa00;">[{timestamp}] {text}</span>'
        elif "📊" in text or "🏆" in text:
            formatted = f'<span style="color: #00ffff;">[{timestamp}] {text}</span>'
        else:
            formatted = f'[{timestamp}] {text}'

        self.log_text.append(formatted)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def update_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def add_iteration_result(self, data: Dict):
        """添加单频迭代结果到表格"""
        self.iteration_results.append(data)

        row = self.result_table.rowCount()
        self.result_table.insertRow(row)

        device_type = self.device_type_combo.currentText()
        config = DEVICE_COLUMN_CONFIG.get(device_type, DEVICE_COLUMN_CONFIG["微带贴片天线"])
        param_keys = config["param_keys"]
        decimal_places = config.get("decimal_places", {"default": 2})

        col = 0
        self._set_center_cell(row, col, str(data['iteration']))
        col += 1

        params = data.get('params', {})
        for key in param_keys:
            val = params.get(key, 0)
            decimals = decimal_places.get(key, decimal_places.get("default", 2))
            if decimals == 1:
                self._set_center_cell(row, col, f"{val:.1f}")
            else:
                self._set_center_cell(row, col, f"{val:.2f}")
            col += 1

        s11 = data.get('s11', 0)
        freq = data.get('freq', 0)
        target_freq = self.freq_spin.value()
        target_s11 = self.s11_spin.value()

        # ===== 关键修改：同时检查 S11 和频率 =====
        s11_ok = s11 <= target_s11
        freq_ok = abs(freq - target_freq) <= 0.01  # 10MHz 容差
        is_pass = s11_ok and freq_ok

        # S11 显示
        s11_item = self._create_center_item(f"{s11:.2f}" if s11 else "N/A")
        if is_pass:
            s11_item.setForeground(QColor(0, 200, 0))
            s11_item.setBackground(QBrush(QColor(13, 42, 26)))
        elif s11 <= target_s11:
            s11_item.setForeground(QColor(255, 200, 0))  # S11达标但频率不达标 → 黄色
        else:
            s11_item.setForeground(QColor(255, 100, 100))
        self.result_table.setItem(row, col, s11_item)
        col += 1

        # 频率显示
        freq_item = self._create_center_item(f"{freq:.4f}" if freq else "N/A")
        if freq_ok:
            freq_item.setForeground(QColor(0, 200, 0))
        elif abs(freq - target_freq) < 0.05:
            freq_item.setForeground(QColor(255, 200, 0))  # 接近目标 → 黄色
        else:
            freq_item.setForeground(QColor(255, 100, 100))
        self.result_table.setItem(row, col, freq_item)
        col += 1

        # ===== 状态显示：只有 S11 和频率都达标才是合格 =====
        if is_pass:
            status_text = "✅ 合格"
            status_item = self._create_center_item(status_text)
            status_item.setForeground(QColor(0, 200, 0))
        elif s11_ok and not freq_ok:
            status_text = "⚠️ 频率偏移"
            status_item = self._create_center_item(status_text)
            status_item.setForeground(QColor(255, 200, 0))
        else:
            status_text = "❌ 不合格"
            status_item = self._create_center_item(status_text)
            status_item.setForeground(QColor(255, 100, 100))
        self.result_table.setItem(row, col, status_item)

        # ... 后续高亮代码保持不变 ...

        # 单频最佳行高亮显示
        current_score = 0
        if is_pass:
            max_iter = self.iter_spin.value() if hasattr(self, 'iter_spin') else 30
            current_score = 100 + (data['iteration'] / max_iter)
        else:
            current_score = -abs(s11) if s11 else 0

        should_highlight = False

        if is_pass:
            if self._best_single_row == -1:
                should_highlight = True
            else:
                prev_item = self.result_table.item(self._best_single_row, col)
                prev_is_pass = prev_item and "合格" in prev_item.text()
                if not prev_is_pass:
                    should_highlight = True
                elif data['iteration'] > self._best_single_score:
                    should_highlight = True
        else:
            if self._best_single_row == -1:
                should_highlight = True
            else:
                prev_item = self.result_table.item(self._best_single_row, col)
                prev_is_pass = prev_item and "合格" in prev_item.text()
                if not prev_is_pass and current_score > self._best_single_score:
                    should_highlight = True

        if should_highlight:
            if self._best_single_row >= 0:
                for c in range(self.result_table.columnCount()):
                    old_item = self.result_table.item(self._best_single_row, c)
                    if old_item:
                        old_item.setBackground(QBrush())
                        old_item.setForeground(QColor(200, 200, 200))

            self._best_single_score = data['iteration'] if is_pass else current_score
            self._best_single_row = row
            for c in range(self.result_table.columnCount()):
                new_item = self.result_table.item(row, c)
                if new_item:
                    new_item.setBackground(QBrush(QColor(30, 80, 30)))
                    new_item.setForeground(QColor(0, 255, 0))

        self.result_table.scrollToBottom()

    def add_dual_iteration_result(self, data: Dict):
        """添加双频迭代结果到表格"""
        self.iteration_results.append(data)

        row = self.result_table.rowCount()
        self.result_table.insertRow(row)

        device_type = self.device_type_combo.currentText()
        config = DEVICE_COLUMN_CONFIG.get(device_type, DEVICE_COLUMN_CONFIG["双频微带天线"])
        param_keys = config["param_keys"]
        decimal_places = config.get("decimal_places", {"default": 2})

        params = data.get('params', {})
        result = data.get('result', {})
        bands = result.get('bands', {})

        low_freq_target = self.low_freq_spin.value()
        high_freq_target = self.high_freq_spin.value()
        target_low_s11 = self.low_s11_spin.value()
        target_high_s11 = self.high_s11_spin.value()

        low_key = f"{low_freq_target}GHz"
        high_key = f"{high_freq_target}GHz"

        low_band = bands.get(low_key, {})
        high_band = bands.get(high_key, {})

        low_actual_freq = low_band.get('frequency_at_min_ghz', 0)
        high_actual_freq = high_band.get('frequency_at_min_ghz', 0)
        low_s11 = low_band.get('s11_at_target', 0)
        high_s11 = high_band.get('s11_at_target', 0)

        if low_s11 == 0:
            low_s11 = data.get('low_s11', 0)
        if high_s11 == 0:
            high_s11 = data.get('high_s11', 0)
        if low_actual_freq == 0:
            low_actual_freq = data.get('low_freq', 0)
        if high_actual_freq == 0:
            high_actual_freq = data.get('high_freq', 0)

        col = 0
        self._set_center_cell(row, col, str(data.get('iteration', 0)))
        col += 1

        for key in param_keys:
            val = params.get(key, 0)
            decimals = decimal_places.get(key, decimal_places.get("default", 2))

            if key in ['Ls', 'Ws']:
                self._set_center_cell(row, col, f"{val:.1f}" if val > 0 else "N/A")
            else:
                self._set_center_cell(row, col, f"{val:.2f}" if val > 0 else "N/A")
            col += 1

        low_s11_item = self._create_center_item(f"{low_s11:.2f}" if low_s11 else "N/A")
        if low_s11 <= target_low_s11:
            low_s11_item.setForeground(QColor(0, 200, 0))
        else:
            low_s11_item.setForeground(QColor(255, 100, 100))
        self.result_table.setItem(row, col, low_s11_item)
        col += 1

        low_freq_item = self._create_center_item(f"{low_actual_freq:.4f}" if low_actual_freq > 0 else "N/A")
        low_freq_ok = abs(low_actual_freq - low_freq_target) <= 0.01
        if low_freq_ok:
            low_freq_item.setForeground(QColor(0, 200, 0))
        elif abs(low_actual_freq - low_freq_target) < 0.05:
            low_freq_item.setForeground(QColor(255, 200, 0))
        else:
            low_freq_item.setForeground(QColor(255, 100, 100))
        self.result_table.setItem(row, col, low_freq_item)
        col += 1

        high_s11_item = self._create_center_item(f"{high_s11:.2f}" if high_s11 else "N/A")
        if high_s11 <= target_high_s11:
            high_s11_item.setForeground(QColor(0, 200, 0))
        else:
            high_s11_item.setForeground(QColor(255, 100, 100))
        self.result_table.setItem(row, col, high_s11_item)
        col += 1

        high_freq_item = self._create_center_item(f"{high_actual_freq:.4f}" if high_actual_freq > 0 else "N/A")
        high_freq_ok = abs(high_actual_freq - high_freq_target) <= 0.01
        if high_freq_ok:
            high_freq_item.setForeground(QColor(0, 200, 0))
        elif abs(high_actual_freq - high_freq_target) < 0.05:
            high_freq_item.setForeground(QColor(255, 200, 0))
        else:
            high_freq_item.setForeground(QColor(255, 100, 100))
        self.result_table.setItem(row, col, high_freq_item)
        col += 1

        s11_ok = (low_s11 <= target_low_s11) and (high_s11 <= target_high_s11)
        low_freq_ok_strict = abs(low_actual_freq - low_freq_target) <= 0.01
        high_freq_ok_strict = abs(high_actual_freq - high_freq_target) <= 0.01
        is_pass_strict = s11_ok and low_freq_ok_strict and high_freq_ok_strict

        if is_pass_strict:
            status_text = "✅ 双频合格"
            status_item = self._create_center_item(status_text)
            status_item.setForeground(QColor(0, 200, 0))
        else:
            status_text = "❌ 未达标"
            status_item = self._create_center_item(status_text)
            status_item.setForeground(QColor(255, 100, 100))

        self.result_table.setItem(row, col, status_item)

        # 双频最佳行高亮显示
        is_pass_result = is_pass_strict or (low_s11 <= target_low_s11 and high_s11 <= target_high_s11)
        iteration = data.get('iteration', 0)
        current_score = data.get('overall_score', 0)

        should_highlight = False

        if is_pass_result:
            if self._best_dual_row == -1:
                should_highlight = True
            else:
                prev_status_item = self.result_table.item(self._best_dual_row, col)
                prev_is_pass = prev_status_item and "合格" in prev_status_item.text()
                if not prev_is_pass:
                    should_highlight = True
                elif iteration > self._best_dual_score:
                    should_highlight = True
                elif current_score > self._best_dual_score:
                    should_highlight = True
        else:
            if self._best_dual_row == -1:
                should_highlight = True
            else:
                prev_status_item = self.result_table.item(self._best_dual_row, col)
                prev_is_pass = prev_status_item and "合格" in prev_status_item.text()
                if not prev_is_pass and current_score > self._best_dual_score:
                    should_highlight = True

        if should_highlight:
            if self._best_dual_row >= 0:
                for c in range(self.result_table.columnCount()):
                    old_item = self.result_table.item(self._best_dual_row, c)
                    if old_item:
                        old_item.setBackground(QBrush())
                        old_item.setForeground(QColor(200, 200, 200))

            self._best_dual_score = iteration if is_pass_result else current_score
            self._best_dual_row = row
            for c in range(self.result_table.columnCount()):
                new_item = self.result_table.item(row, c)
                if new_item:
                    new_item.setBackground(QBrush(QColor(30, 80, 30)))
                    new_item.setForeground(QColor(0, 255, 0))

        self.result_table.scrollToBottom()

    def _set_center_cell(self, row: int, col: int, text: str):
        item = self._create_center_item(text)
        self.result_table.setItem(row, col, item)

    def _create_center_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def update_best(self, data: Dict):
        """更新单频最佳结果显示"""
        params = data.get('params', {})
        model_name = self.model_combo.currentText()
        device_type = self.device_type_combo.currentText()
        s11 = data.get('s11', 0)
        freq = data.get('freq', 0)
        bw = data.get('bw', 0)
        is_pass = data.get('is_pass', False)
        target_freq = self.freq_spin.value()
        target_s11 = self.s11_spin.value()

        bw_mhz = bw * 1000 if bw else 0
        freq_error = abs(freq - target_freq) * 1000 if freq else 0

        params_str = ""
        for k, v in params.items():
            if k in ['w0', 'l0', 'd1']:
                params_str += f"  {k}={v:.1f} mm\n"
            elif k in ['stages']:
                params_str += f"  {k}={v:.0f}\n"
            else:
                params_str += f"  {k}={v:.2f} mm\n"

        text = f"""
🏆 迭代 {data['iteration']} [{model_name}]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 器件类型: {device_type}
📡 S11 = {s11:.2f} dB  {'✅ 达标' if s11 <= target_s11 else '❌ 未达标'}
🎯 频率 = {freq:.4f} GHz  (目标: {target_freq} GHz)
📈 频偏 = {freq_error:.0f} MHz
📊 -10dB带宽 = {bw_mhz:.0f} MHz
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 最优参数:
{params_str}
"""

        if is_pass:
            self.best_label.setStyleSheet("""
                background-color: #0d2a1a;
                padding: 12px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
                border: 2px solid #00ff88;
                color: #c0d0e0;
            """)
        else:
            self.best_label.setStyleSheet("""
                background-color: #0d1520;
                padding: 12px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
                border: 2px solid #1a3a5c;
                color: #c0d0e0;
            """)

        self.best_label.setText(text)

    def update_dual_best(self, data: Dict):
        """更新双频最佳结果显示"""
        params = data.get('params', {})
        result = data.get('result', {})
        model_name = self.model_combo.currentText()
        device_type = self.device_type_combo.currentText()
        iteration = data.get('iteration', 0)

        low_s11 = result.get('low_s11', 0)
        high_s11 = result.get('high_s11', 0)
        is_pass = result.get('is_pass', False)
        score = result.get('overall_score', 0)

        bands = result.get('bands', {})
        target_low_freq = self.low_freq_spin.value()
        target_high_freq = self.high_freq_spin.value()
        low_band = bands.get(f"{target_low_freq}GHz", {})
        high_band = bands.get(f"{target_high_freq}GHz", {})
        low_actual_freq = low_band.get('frequency_at_min_ghz', 0)
        high_actual_freq = high_band.get('frequency_at_min_ghz', 0)

        target_low_s11 = self.low_s11_spin.value()
        target_high_s11 = self.high_s11_spin.value()

        low_freq_error = abs(low_actual_freq - target_low_freq) * 1000 if low_actual_freq else 0
        high_freq_error = abs(high_actual_freq - target_high_freq) * 1000 if high_actual_freq else 0

        low_freq_ok = abs(low_actual_freq - target_low_freq) <= 0.01
        high_freq_ok = abs(high_actual_freq - target_high_freq) <= 0.01
        low_s11_ok = low_s11 <= target_low_s11
        high_s11_ok = high_s11 <= target_high_s11

        low_s11_status = "✅ 达标" if low_s11_ok else "❌ 未达标"
        high_s11_status = "✅ 达标" if high_s11_ok else "❌ 未达标"
        low_freq_status = "✅" if low_freq_ok else "❌"
        high_freq_status = "✅" if high_freq_ok else "❌"

        params_str = ""
        for k, v in params.items():
            if k in ['L0', 'W0']:
                params_str += f"  {k} = {v:.2f} mm\n"
            elif k in ['H']:
                params_str += f"  {k} = {v:.1f} mm\n"
            elif k in ['Ls', 'Ws']:
                params_str += f"  {k} = {v:.1f} mm\n"
            else:
                params_str += f"  {k} = {v:.2f} mm\n"

        text = f"""
🏆 双频优化最佳结果 [迭代 {iteration}] [{model_name}]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 器件类型: {device_type}

📡 低频 ({target_low_freq} GHz):
   S11 = {low_s11:.2f} dB  {low_s11_status}
   频率 = {low_actual_freq:.4f} GHz (目标: {target_low_freq} GHz)
   频偏 = {low_freq_error:.0f} MHz {low_freq_status}

📡 高频 ({target_high_freq} GHz):
   S11 = {high_s11:.2f} dB  {high_s11_status}
   频率 = {high_actual_freq:.4f} GHz (目标: {target_high_freq} GHz)
   频偏 = {high_freq_error:.0f} MHz {high_freq_status}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 综合得分: {score:.3f}
📐 最优参数:
{params_str}
"""

        if is_pass:
            self.best_label.setStyleSheet("""
                background-color: #0d2a1a;
                padding: 12px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
                border: 2px solid #00ff88;
                color: #c0d0e0;
            """)
        else:
            self.best_label.setStyleSheet("""
                background-color: #0d1520;
                padding: 12px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
                border: 2px solid #1a3a5c;
                color: #c0d0e0;
            """)

        self.best_label.setText(text)

    def on_finished(self, final_result: Dict):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum())

        model_name = self.model_combo.currentText()
        if final_result.get('success'):
            self._append_log(f"\n✅ 优化成功完成! [{model_name}]")
        else:
            self._append_log(f"\n⚠️ 优化结束，已达到最大迭代次数 [{model_name}]")

        if 'stats' in final_result:
            stats = final_result.get('stats', {})
            self._append_log(f"\n📊 决策统计 [{model_name}]: {stats}")

    def on_error(self, error_msg: str):
        self._append_log(f"\n❌ 错误: {error_msg}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "错误", error_msg)