# 📈 股票交易模拟器 (Stock Trading Simulator Pro)

**Stock Trading Simulator Pro** 是一款基于 Python 开发的高性能桌面端股票复盘与模拟交易软件。

它专为量化交易员和股票投资者设计，采用 **DuckDB** 作为底层数据引擎，实现了毫秒级的历史数据读取。软件集成了专业的 K 线图表、丰富的技术指标、真实的账户模拟系统以及现代化的 GUI 界面。

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![DuckDB](https://img.shields.io/badge/Backend-DuckDB-yellow)
![GUI](https://img.shields.io/badge/GUI-ttkbootstrap-green)

## ✨ 核心特性

*   **🚀 高性能数据引擎**: 基于 DuckDB 的 Zero-copy 技术，无需将庞大的历史数据全部加载进内存，即可实现秒级查询和渲染。
*   **📊 专业级图表**:
    *   支持标准的蜡烛图（K线）。
    *   集成多种技术指标：MA, MACD, RSI, KDJ, BOLL。
    *   **独家指标**: 内置 Z_CGO (资金流向) 和 TFO (趋势因子) 等量化指标。
    *   支持十字光标悬停查看详细数据。
*   **🎮 沉浸式模拟交易**:
    *   **真实模拟**: 采用“今日决策，次日开盘价成交”的机制，杜绝未来函数，还原真实交易难度。
    *   支持买入、卖出、持仓管理。
    *   自动计算交易佣金和印花税。
*   **🖥️ 现代化界面**:
    *   支持高分屏（High-DPI）自适应，字体清晰锐利。
    *   基于 `ttkbootstrap` 的现代化 UI 主题。
    *   支持键盘快捷键操作，提升复盘效率。
*   **💾 存档系统**: 支持随时保存和读取游戏进度（JSON 格式），方便长周期复盘。
*   **🤖 自动播放**: 支持自动按日推进行情，通过回放历史感受市场波动。

## 📂 项目结构

```text
Stock_Trading_Game/
├── quant_database/          # 数据存放目录
│   ├── merged_all_stock_data.parquet  # [必须] 核心行情数据
│   └── stock_list.csv       # [可选] 股票名称映射表
├── config.py                # 全局配置文件
├── main_gui.py              # 程序主入口
├── chart_panel.py           # 图表绘制模块 (Matplotlib)
├── data_loader.py           # 数据加载模块 (DuckDB)
├── game_engine.py           # 交易撮合与账户核心逻辑
├── performance_window.py    # 绩效分析窗口
├── utils.py                 # 通用工具函数
└── README.md                # 说明文档
```

## 🛠️ 安装与配置

### 1. 环境要求

请确保已安装 Python 3.9 或更高版本。

### 2. 安装依赖库

使用 pip 安装项目所需的第三方库：

```bash
pip install pandas numpy matplotlib duckdb ttkbootstrap
```

### 3. 数据准备 (关键步骤)

本项目依赖本地数据文件运行，请确保您拥有符合格式的数据：

1.  **行情数据**: 需要一个包含历史行情的 Parquet 文件。
    *   文件名: `merged_all_stock_data.parquet`
    *   位置: 放入 `quant_database/` 目录。
    *   必须包含列: `date`, `code`, `open`, `high`, `low`, `close`, `vol` (或 volume)。
2.  **股票列表**: (可选) 用于显示股票中文名称。
    *   文件名: `stock_list.csv`
    *   位置: 放入 `quant_database/` 目录。

> 如需修改数据路径或文件名，请编辑 `config.py` 中的 `DATA_DIR` 和 `DATA_FILENAME`。
> 可在百度网盘下载通过网盘分享的文件：quant_database 链接: https://pan.baidu.com/s/1s2mPEnNCLvclim4ee-wRVg?pwd=sp4s 提取码: sp4s 

## 🚀 快速开始

在项目根目录下运行以下命令启动程序：

```bash
python main_gui.py
```

## 🎮 操作指南

### 快捷键

为了提高复盘效率，系统内置了以下快捷键：

| 按键 | 功能 |
| :--- | :--- |
| **Space (空格)** | 进入下一个交易日 |
| **→ (右箭头)** | 进入下一个交易日 |
| **← (左箭头)** | 返回上一个交易日 |
| **↑ (上箭头)** | 触发 **买入** 操作 |
| **↓ (下箭头)** | 触发 **卖出** 操作 |
| **Tab** | 切换到列表中的下一只股票 |
| **Shift + Tab** | 切换到列表中的上一只股票 |

### 交易规则说明
为了模拟真实的交易环境，防止“后视镜”效应：
1.  您看到的 K 线是**当前日期**的数据。
2.  您的买卖决策基于当前日期的收盘情况。
3.  **实际成交**将按照**下一个交易日**的**开盘价**进行撮合。

## ⚙️ 配置说明

您可以在 `config.py` 中调整游戏参数：

*   `INITIAL_CASH`: 初始资金（默认 100,000）。
*   `COMMISSION_RATE`: 交易佣金费率。
*   `CHART_WINDOW_DAYS`: 图表默认显示的 K 线天数。
*   `DEFAULT_INDICATORS`: 默认开启的技术指标。

## 📝 开发日志

*   **v1.0 (Pro)**
    *   引入 DuckDB 替换 Pandas 内存加载，启动速度提升 10 倍。
    *   新增“自动播放”功能。
    *   重构 GUI 布局，增加右侧交易面板。
    *   新增存档/读档功能。
    *   适配 2K/4K 高分屏显示。

## 🗓️ 开发路线图 (Roadmap)

- [x] 基础模拟引擎
- [x] 现代化 GUI 界面
- [x] 模拟模式（混沌世界）
- [ ] **GUI界面优化**
- [ ] **新闻头条支持**

## 🤝 贡献与支持

如果你发现了 Bug 或有新的功能建议，欢迎提交 Issue 或 Pull Request。

---
*Happy Trading!* 📈