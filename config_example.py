# config_example.py - 复制为 config.py 并修改

from pathlib import Path

# ==================== 项目根目录 ====================
PROJECT_ROOT = Path(__file__).parent.absolute()

# ==================== HFSS 模板项目路径 ====================
# ⚠️ 请修改为你的实际路径
HFSS_TEMPLATE_PROJECT = r"C:\Users\YourName\Documents\HFSS\AI-Patch.aedt"
HFSS_DUAL_TEMPLATE = r"C:\Users\YourName\Documents\HFSS\dual_frequence_ai.aedt"
HFSS_TLINE_TEMPLATE = r"C:\Users\YourName\Documents\HFSS\TLine_stdr_ai.aedt"

# ==================== 输出目录 ====================
OUTPUT_BASE = Path("C:/HFSS_Output")  # ⚠️ 修改为你的输出目录

HFSS_CSV_OUTPUT = OUTPUT_BASE / "HFSS_CSV_Output"
TLINE_CSV_OUTPUT = OUTPUT_BASE / "TLine_CSV_Output"
HFSS_AGENT_WORKSPACE = OUTPUT_BASE / "HFSS_Agent_Workspace"
TLINE_AI_WORKSPACE = OUTPUT_BASE / "TLine_AI_Workspace"
TLINE_SCRIPTS = OUTPUT_BASE / "TLine_Scripts"
HFSS_RUNS = OUTPUT_BASE / "HFSS_Runs"

# ==================== LLM 服务配置 ====================
LLM_URL = "http://localhost:1234/v1"
LLM_MODEL = "qwen2.5-coder-7b-instruct"

# ==================== 材料默认值 ====================
DEFAULT_MATERIAL = "FR4"
DEFAULT_SUBSTRATE_H = 1.6  # mm

# ==================== 仿真参数 ====================
DEFAULT_THRESHOLD_S11 = -10  # dB
DEFAULT_TARGET_S11 = -15  # dB
DEFAULT_MAX_ITERATIONS = 20
FREQ_TOLERANCE = 0.01  # GHz