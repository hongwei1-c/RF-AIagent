# RF-AIagent

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)]()

> 🚀 **AI-Agent 驱动的射频设计系统 | HFSS 自动化仿真 | 智能优化**
> AI-Agent driven RF design system with HFSS automation for antennas, filters, and transmission lines.

---

## 🚨 核心优势 (Core Advantages)

> **一句话完成仿真全流程闭环，你只需要会提需求。**
> **Achieve a full closed-loop simulation workflow with just one prompt. All you need to do is express your requirements.**

- **零门槛操作 (Zero learning curve)**：无需学习复杂的 HFSS 软件操作，无需打开 Codex 等外部智能体，直接在系统内输入需求即可。
  *No need to learn complex HFSS operations or open external agents like Codex. Simply input your requirements directly into the system.*
- **全流程自动闭环 (Full automated closed-loop)**：从需求理解、参数设定、建模仿真、结果导出到合格判定，整个物理仿真流程全由 AI-Agent 自主驱动完成。
  *From requirement understanding, parameter setting, modeling, and simulation, to result export and qualification, the entire physical simulation process is autonomously driven by the AI-Agent.*

---

## ✨ 核心功能 (Core Features)

| 功能 (Feature) | 说明 (Description) |
| :--- | :--- |
| 🤖 **AI-Agent闭环优化**<br>*(AI-Agent Closed-loop Optimization)* | LLM + 物理规则混合决策，自动调参<br>*LLM + physics-based hybrid decision-making with automatic parameter tuning.* |
| 📡 **单频/双频天线优化**<br>*(Single/Dual-band Antenna Optimization)* | 支持 2.45GHz + 5GHz 双频设计<br>*Supports 2.45GHz + 5GHz dual-band design.* |
| ⚡ **HFSS自动化仿真**<br>*(Automated HFSS Simulation)* | COM接口控制，自动运行仿真导出结果<br>*COM interface control, automatic simulation execution, and result export.* |
| 🎯 **高精度收敛**<br>*(High-precision Convergence)* | ±0.01 GHz 频率精度<br>*Frequency accuracy of ±0.01 GHz.* |
| 🔧 **多器件支持**<br>*(Multi-device Support)* | 天线、滤波器、功分器、传输线<br>*Antennas, filters, power dividers, transmission lines.* |
| 📊 **批量工作流**<br>*(Batch Workflow)* | 自动分类合格/不合格设计，生成报告<br>*Automatically classifies designs as pass/fail and generates reports.* |

---

## 📊 性能指标 (Performance Metrics)

| 指标 (Metric) | 数值 (Value) |
| :--- | :--- |
| 收敛轮数 (Convergence Rounds) | 6-30 轮 |
| 频率精度 (Frequency Accuracy) | ±0.01 GHz |
| 单频/双频天线收敛 (Antenna Convergence) | 3-10 轮 |

---

## 🤖 支持的器件 (Supported Devices)

| 类型 (Type) | 器件 (Devices) |
| :--- | :--- |
| 📡 单频天线 (Single-band) | 微带贴片天线、缝隙天线、PIFA天线<br>*Microstrip patch, slot, PIFA antennas* |
| 📡 双频天线 (Dual-band) | 双频微带天线、双频缝隙天线<br>*Dual-band microstrip, dual-band slot antennas* |
| 🔌 滤波器 (Filters) | 带通、低通、高通滤波器<br>*Band-pass, low-pass, high-pass filters* |
| 🔌 功分器 (Power Dividers) | Wilkinson、T型功分器<br>*Wilkinson, T-junction power dividers* |
| 🔌 传输线 (Transmission Lines) | 微带线、差分线、耦合线<br>*Microstrip, differential, coupled lines* |

---

## 🚀 快速开始 (Quick Start)

```bash
# 1. 克隆项目 (Clone the repository)
git clone https://github.com/hongwei1-c/RF-AIagent.git

# 2. 安装依赖 (Install dependencies)
pip install -r requirements.txt

# 3. 配置路径 (Configure paths)
copy config_example.py config.py
# 编辑 config.py 修改你的本地路径 (Edit config.py to modify your local paths)

# 4. 启动程序 (Run the program)
python main.py
