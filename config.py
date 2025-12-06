"""
Configuration settings for Stock Trading Game
"""
import os

# Directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
WINDOW_TITLE = "股票交易模拟器 (Pro Ver.)"
WINDOW_SIZE = "1400x900"
THEME = "cosmo"  # ttkbootstrap theme

# Color scheme
COLOR_RISE = "#FF4136"  # Red for price increase
COLOR_FALL = "#2ECC40"  # Green for price decrease
COLOR_BACKGROUND = "#FFFFFF"
COLOR_GRID = "#E0E0E0"

# Stock list display
MAX_STOCK_LIST_DISPLAY = 50
PINNED_STOCKS_COLOR = "#FFE66D"