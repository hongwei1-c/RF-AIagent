# WHYAVE-AI

AI-Agent 驱动的射频设计系统，支持 HFSS 自动化仿真和智能优化。

## 快速开始

1. 安装依赖: pip install -r requirements.txt
2. 配置路径: copy config_example.py config.py 然后修改路径
3. 启动: python main.py

## 功能

- AI Agent 闭环优化 (LLM + 物理规则)
- 单频/双频天线优化
- HFSS 自动化仿真
- 多器件支持 (天线/滤波器/功分器/传输线)

## 依赖

- Windows 10/11 + HFSS
- Python 3.8+
- PyQt6, numpy, scipy, matplotlib, pywin32
