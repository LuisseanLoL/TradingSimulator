"""
Configuration settings for Stock Trading Game
"""
import os
import sys  # 引入 sys

# --- 修改开始：智能识别运行路径 ---
if getattr(sys, 'frozen', False):
    # 如果是打包后的 EXE，基准目录是 EXE 所在的文件夹
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 如果是 Python 源码运行，基准目录是当前文件所在文件夹
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# --- 修改结束 ---
# 以前是 daily_full_factor_cache，现在改为指向存放 merged parquet 的目录
DATA_DIR = os.path.join(BASE_DIR, "quant_database")
DATA_FILENAME = "merged_all_stock_data.parquet"

# Game settings
INITIAL_CASH = 100_000.0  # Starting with 1 million yuan
COMMISSION_RATE = 0.0002  # 0.03% commission per trade
MIN_COMMISSION = 5.0  # Minimum 5 yuan per trade

# Chart settings
CHART_WINDOW_DAYS = 60  # Show last 60 days by default
CHART_STYLE = "seaborn-v0_8-darkgrid"
CANDLESTICK_WIDTH = 0.8

# Technical indicator defaults
DEFAULT_INDICATORS = {
    "ma_5": True,
    "ma_20": True,
    "macd": False,
    "rsi": False,
    "kdj": False,
    "boll": False,
    "z_cgo": False, # 新增
    "tfo": False,   # 新增
}

# GUI settings
WINDOW_TITLE = "股票交易模拟器 (Pro Ver.) - By Seanuyuil"
WINDOW_SIZE = "1400x900"

# --- 配色方案 (仿东方财富/TradingView风格) ---
# 涨 (红): 使用稍带粉调的红，不那么刺眼
COLOR_RISE = '#F6465D'  
# 跌 (绿): 使用青绿色，比纯绿更现代
COLOR_FALL = '#0ECB81'  
# 窗口主题 (推荐)
# 亮色推荐: 'litera', 'cosmo', 'flatly'
# 暗色推荐: 'darkly', 'cyborg'
THEME = 'litera'
COLOR_BACKGROUND = "#FFFFFF"
COLOR_GRID = "#f0f0f0"

# Stock list display
MAX_STOCK_LIST_DISPLAY = 50
PINNED_STOCKS_COLOR = "#FFE66D"

# --- 模拟模式配置 ---
SIM_WARMUP_DAYS = 200 # 为模拟数据增加预热期，确保初始技术指标准确