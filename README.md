# RF-AIagent

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)]()

> 🚀 AI-Agent 驱动的射频设计系统 | HFSS 自动化仿真 | 智能优化

AI-Agent driven RF design system with HFSS automation for antennas, filters and transmission lines.

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🤖 **AI-Agent闭环优化** | LLM + 物理规则混合决策，自动调参 |
| 📡 **单频/双频天线优化** | 支持 2.45GHz + 5GHz 双频设计 |
| ⚡ **HFSS自动化仿真** | COM接口控制，自动运行仿真导出结果 |
| 🎯 **高精度收敛** | ±0.01 GHz 频率精度 |
| 🔧 **多器件支持** | 天线、滤波器、功分器、传输线 |
| 📊 **批量工作流** | 自动分类合格/不合格设计，生成报告 |

---

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| 收敛轮数 | 6-30 轮 |
| 频率精度 | ±0.01 GHz |
| 单频收敛 | 6-15 轮 |
| 双频收敛 | 15-30 轮 |

---

## 🤖 支持的器件

| 类型 | 器件 |
|------|------|
| 📡 单频天线 | 微带贴片天线、缝隙天线、PIFA天线 |
| 📡 双频天线 | 双频微带天线、双频缝隙天线 |
| 🔌 滤波器 | 带通、低通、高通滤波器 |
| 🔌 功分器 | Wilkinson、T型功分器 |
| 🔌 传输线 | 微带线、差分线、耦合线 |

---

## 🚀 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/hongwei1-c/RF-AIagent.git

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置路径
copy config_example.py config.py
# 编辑 config.py 修改你的本地路径

# 4. 启动程序
python main.py
