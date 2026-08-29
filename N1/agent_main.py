#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WHYAVE-AI - AI-Agent驱动射频设计系统 主程序入口
"""

import sys
import os
from pathlib import Path

# ===== 从 antenna_agent 导入所有 Agent 类 =====
from antenna_agent import AntennaAgent, DualBandAntennaAgent
from tline_agent import TLineAgent
from ai_brain import DecisionMode

# 导出供其他模块使用
__all__ = [
    'AntennaAgent',
    'DualBandAntennaAgent',
    'TLineAgent',
    'DecisionMode'
]

# 如果直接运行，启动 GUI
if __name__ == "__main__":
    # 确保路径正确
    sys.path.insert(0, str(Path(__file__).parent))

    try:
        # 从 main.py 导入 GUI 主程序
        from main import main

        main()
    except ImportError as e:
        print(f"❌ 无法启动 GUI: {e}")
        print("请确保 main.py 存在")
        sys.exit(1)