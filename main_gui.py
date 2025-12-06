"""
Main GUI for Stock Trading Game
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import pandas as pd
from typing import List, Optional
import config
from data_loader import DataLoader
from game_engine import Account
from chart_panel import ChartPanel
from performance_window import PerformanceWindow
from utils import format_currency, format_percentage, format_number
import json
from tkinter import filedialog


class StockTradingGame:
    """Main application window"""
    
    def __init__(self):
        """Initialize the game"""
        # Initialize data and game state
        self.data_loader = DataLoader()
        self.account = Account()

        # --- 新增：定义大盘指数代码 ---
        self.market_index_code = 'sh.000001' 
        # ---------------------------
        
        # Get available dates
        self.available_dates = self.data_loader.get_available_dates()
        # Start date will be set after selection (default to 15 days from start to show history)
        self.start_date_idx = 15  # Start with 15 days of history
        self.current_date_idx = self.start_date_idx
        self.current_date = self.available_dates[self.current_date_idx]
        
        # Stock list management
        self.watched_stocks: List[str] = []
        self.pinned_stocks: List[str] = []
        self.current_stock: Optional[str] = None

        # --- 新增：自动播放状态 ---
        self.is_playing = False
        # ------------------------
        
        # Create main window
        self.root = ttkb.Window(themename=config.THEME)
        self.root.title(config.WINDOW_TITLE)
        # --- 修改开始：设置窗口最大化 ---
        # 原代码：self.root.geometry(config.WINDOW_SIZE)
        
        # 设置一个基础大小，防止极少数情况下最大化失败导致窗口太小
        self.root.geometry("1280x800")
        
        try:
            # Windows 系统最大化命令
            self.root.state('zoomed')
        except:
            try:
                # Linux / Mac 系统最大化命令
                self.root.attributes('-zoomed', True)
            except:
                # 兜底方案：获取屏幕尺寸并设置
                w = self.root.winfo_screenwidth()
                h = self.root.winfo_screenheight()
                self.root.geometry(f"{w}x{h}")
        # --- 修改结束 ---
        
        # Create UI
        self._create_menu()
        self._create_widgets()
        
        # Show stock selection dialog
        self.root.after(100, self._show_stock_selection)

        # 绑定快捷键
        self.root.bind('<space>', lambda e: self._next_day())  # 空格键：下一天
        self.root.bind('<Left>', lambda e: self._prev_day())   # 左箭头：上一天
        self.root.bind('<Right>', lambda e: self._next_day())  # 右箭头：下一天
        self.root.bind('<Up>', lambda e: self._buy_stock())       # B键：买入
        self.root.bind('<Down>', lambda e: self._sell_stock())      # S键：卖出
        # --- 新增：Tab 键循环切换股票 ---
        # 1 代表向下循环，-1 代表向上循环
        self.root.bind('<Tab>', lambda e: self._cycle_stock(1))
        self.root.bind('<Shift-Tab>', lambda e: self._cycle_stock(-1))
    
    def _create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="重新选股", command=self._show_stock_selection)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # --- 新增存档/读档菜单 ---
        file_menu.add_command(label="保存存档", command=self._save_game)
        file_menu.add_command(label="读取存档", command=self._load_game)
        file_menu.add_separator()
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="查看", menu=view_menu)
        view_menu.add_command(label="交易表现", command=self._show_performance)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self._show_about)
    
    def _create_widgets(self):
        """Create main window widgets"""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 1. 先创建并 Pack 左侧栏 (Left Sidebar)
        left_frame = ttk.Frame(main_container, width=560)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        self._create_stock_list(left_frame)
        
        # 2. 【关键修改】紧接着创建并 Pack 右侧栏 (Right Sidebar)
        # 必须在中间面板之前 Pack 它，否则它会被挤出去
        right_frame = ttk.Frame(main_container, width=420)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_frame.pack_propagate(False)
        
        self._create_right_panel(right_frame)
        
        # 3. 最后创建并 Pack 中间面板 (Center Panel)
        # 因为它有 expand=True，它会自动填充左右栏中间剩余的区域
        center_frame = ttk.Frame(main_container)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self._create_center_panel(center_frame)
    
    def _create_stock_list(self, parent):
        """Create stock list sidebar using fast Treeview"""
        # Title
        ttk.Label(parent, text="股票列表", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Search box
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(fill=tk.X)
        
        # --- 修改开始：使用 Treeview ---
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=2)
        
        columns = ("stock", "price", "pct")
        self.stock_tree = ttk.Treeview(
            list_frame, 
            columns=columns, 
            show="headings", 
            selectmode="browse",
            height=20
        )
        
        # 修改表头文字
        self.stock_tree.heading("stock", text="代码/名称", anchor="w") # 改这里
        self.stock_tree.heading("price", text="现价", anchor="e")
        self.stock_tree.heading("pct", text="涨幅", anchor="e")
        
        # 调整列宽 (总宽约220)
        self.stock_tree.column("stock", width=100, minwidth=90, anchor="w") # 加宽
        self.stock_tree.column("price", width=55, minwidth=50, anchor="e")
        self.stock_tree.column("pct", width=55, minwidth=50, anchor="e")
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.stock_tree.yview)
        self.stock_tree.configure(yscrollcommand=scrollbar.set)
        
        self.stock_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # --- 关键：配置颜色 Tag ---
        # 这里的 foreground 颜色就是字体的颜色
        self.stock_tree.tag_configure("up", foreground=config.COLOR_RISE)  # 红
        self.stock_tree.tag_configure("down", foreground=config.COLOR_FALL) # 绿
        self.stock_tree.tag_configure("flat", foreground="gray")
        # ------------------------

        # 绑定事件
        self.stock_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.stock_tree.bind("<Button-3>", self._on_tree_right_click)

    def _create_center_panel(self, parent):
        """Create center panel with chart only (Trade controls moved to right)"""
        # Top info bar
        info_frame = ttk.Frame(parent)
        info_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        # 大盘行情条
        self.market_bar_frame = ttk.Frame(info_frame, padding=5, bootstyle="secondary")
        self.market_bar_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        self.market_label = ttk.Label(
            self.market_bar_frame, 
            text="正在加载大盘数据...", 
            font=('Microsoft YaHei', 12, 'bold'),
            foreground="white",
            background="#6c757d",
            anchor="center"
        )
        self.market_label.pack(fill=tk.X)

        # Date display and navigation
        date_frame = ttk.Frame(info_frame)
        date_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(date_frame, text="当前日期:").pack(side=tk.LEFT, padx=5)
        self.date_label = ttk.Label(date_frame, text=self.current_date, font=('Arial', 11, 'bold'))
        self.date_label.pack(side=tk.LEFT)
        
        # --- 修改：调整按钮布局，加入自动播放 ---
        # 1. 自动播放按钮
        self.play_btn = ttk.Button(
            date_frame, 
            text="▶ 自动", 
            command=self._toggle_autoplay,
            bootstyle="primary-outline", # 轮廓样式，比较美观
            width=8
        )
        self.play_btn.pack(side=tk.LEFT, padx=(20, 5))
        
        # 2. 下一日按钮
        ttk.Button(
            date_frame, 
            text="下一日 ▶", 
            command=self._next_day, 
            width=10
        ).pack(side=tk.LEFT, padx=5)
        # ------------------------------------
        
        # Stock info
        stock_info_frame = ttk.Frame(info_frame)
        stock_info_frame.pack(side=tk.RIGHT)
        
        self.stock_info_label = ttk.Label(stock_info_frame, text="请选择股票", font=('Arial', 10))
        self.stock_info_label.pack()
        
        # Chart panel
        self.chart_panel = ChartPanel(parent)
        self.chart_panel.get_frame().pack(fill=tk.BOTH, expand=True)
    
    def _create_right_panel(self, parent):
        """Create right panel with Account, TRADING, and Metrics"""
        # 1. Account summary
        account_frame = ttk.LabelFrame(parent, text="账户信息", padding=10)
        account_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.account_labels = {}
        account_fields = [
            ('cash', '可用现金'),
            ('market_value', '持仓市值'),
            ('total_equity', '总资产'),
            ('profit', '总盈亏'),
            ('profit_pct', '收益率')
        ]
        
        for key, label in account_fields:
            frame = ttk.Frame(account_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=f"{label}:").pack(side=tk.LEFT)
            value_label = ttk.Label(frame, text="--", font=('Arial', 9, 'bold'))
            value_label.pack(side=tk.RIGHT)
            self.account_labels[key] = value_label

        # ==========================================
        # 2. 新增：交易操作面板 (Trading Panel)
        # ==========================================
        trade_frame = ttk.LabelFrame(parent, text="交易操作 (次日开盘价成交)", padding=10, bootstyle="info")
        trade_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 显示预计成交价
        price_row = ttk.Frame(trade_frame)
        price_row.pack(fill=tk.X, pady=5)
        ttk.Label(price_row, text="预计单价:").pack(side=tk.LEFT)
        self.trade_price_label = ttk.Label(price_row, text="--", font=('Arial', 10, 'bold'), foreground="#e67e22")
        self.trade_price_label.pack(side=tk.RIGHT)

        # 数量输入
        qty_row = ttk.Frame(trade_frame)
        qty_row.pack(fill=tk.X, pady=5)
        ttk.Label(qty_row, text="交易数量:").pack(side=tk.LEFT)
        
        self.quantity_var = tk.StringVar(value="100")
        # 绑定事件：当输入改变时，自动重新计算总额
        self.quantity_var.trace("w", self._update_trade_estimate)
        
        qty_entry = ttk.Entry(qty_row, textvariable=self.quantity_var, width=10, justify="right")
        qty_entry.pack(side=tk.RIGHT)

        # 显示预计总额
        amt_row = ttk.Frame(trade_frame)
        amt_row.pack(fill=tk.X, pady=5)
        ttk.Label(amt_row, text="预计金额:").pack(side=tk.LEFT)
        self.trade_amount_label = ttk.Label(amt_row, text="--", font=('Arial', 10, 'bold'))
        self.trade_amount_label.pack(side=tk.RIGHT)

        # 按钮区域
        btn_row = ttk.Frame(trade_frame)
        btn_row.pack(fill=tk.X, pady=(10, 5))
        
        # 使用 Grid 布局让按钮等宽
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)
        
        buy_btn = ttk.Button(btn_row, text="买入", command=self._buy_stock, bootstyle="success")
        buy_btn.grid(row=0, column=0, padx=2, sticky="ew")
        
        sell_btn = ttk.Button(btn_row, text="卖出", command=self._sell_stock, bootstyle="danger")
        sell_btn.grid(row=0, column=1, padx=2, sticky="ew")
        
        # 状态提示
        self.trade_status_label = ttk.Label(trade_frame, text="准备就绪", font=('Arial', 8), foreground="gray", anchor="center")
        self.trade_status_label.pack(fill=tk.X, pady=(5,0))
        # ==========================================

        # 3. Current positions
        pos_frame = ttk.LabelFrame(parent, text="当前持仓", padding=5)
        pos_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        columns = ('股票', '数量', '盈亏%') # 简化列以适应宽度
        self.position_tree = ttk.Treeview(pos_frame, columns=columns, show='headings', height=6)
        
        self.position_tree.heading('股票', text='股票')
        self.position_tree.column('股票', width=60, anchor=tk.CENTER)
        self.position_tree.heading('数量', text='数量')
        self.position_tree.column('数量', width=60, anchor=tk.E)
        self.position_tree.heading('盈亏%', text='盈亏%')
        self.position_tree.column('盈亏%', width=60, anchor=tk.E)
        
        pos_scroll = ttk.Scrollbar(pos_frame, orient=tk.VERTICAL, command=self.position_tree.yview)
        self.position_tree.configure(yscrollcommand=pos_scroll.set)
        
        self.position_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pos_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 4. Metrics
        metrics_frame = ttk.LabelFrame(parent, text="财务指标 (TTM)", padding=10)
        metrics_frame.pack(fill=tk.X, side=tk.BOTTOM) # 放在最下面
        
        self.metrics_labels = {}
        metrics_fields = [
            ('peTTM', '市盈率(PE)'),
            ('pbMRQ', '市净率(PB)'),
            ('psTTM', '市销率(PS)'),
            ('pcfNcfTTM', '市现率(PCF)'),
        ]
        
        for key, label in metrics_fields:
            frame = ttk.Frame(metrics_frame)
            frame.pack(fill=tk.X, pady=1)
            ttk.Label(frame, text=f"{label}:").pack(side=tk.LEFT)
            value_label = ttk.Label(frame, text="--")
            value_label.pack(side=tk.RIGHT)
            self.metrics_labels[key] = value_label
    
    def _show_stock_selection(self):
        """Show stock selection dialog (Updated with Board Filters)"""
        dialog = tk.Toplevel(self.root)
        dialog.title("游戏设置")
        dialog.geometry("720x1000") # 高度再增加一点以容纳新选项
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="股票交易模拟", font=('Microsoft YaHei', 16, 'bold')).pack(pady=15)
        
        # 0. 读档按钮 (保持不变)
        load_frame = ttk.Frame(dialog)
        load_frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Button(load_frame, text="📂 读取旧存档", command=lambda: [self._load_game() and dialog.destroy()], bootstyle="secondary-outline").pack(fill=tk.X)

        # 1. 游戏模式 (保持不变)
        mode_frame = ttk.LabelFrame(dialog, text="1. 游戏模式", padding=15)
        mode_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.mode_var = tk.StringVar(value="history")
        self.start_date_display = ttk.Label(dialog, text=f"当前起始日期: {self.current_date}", foreground="blue", font=('Arial', 10, 'bold'))
        
        def on_mode_change():
            mode = self.mode_var.get()
            if mode == "simulation":
                self.data_loader.set_mode("simulation")
                self.available_dates = self.data_loader.get_available_dates()
                self.current_date = self.available_dates[0]
                self.start_date_display.config(text="模拟模式: 日期将自动生成 (Sim-Day-001)")
                for child in date_btn_frame.winfo_children(): child.configure(state="disabled")
            else:
                self.data_loader.set_mode("history")
                self.available_dates = self.data_loader.get_available_dates()
                self.current_date = self.available_dates[self.current_date_idx]
                self.start_date_display.config(text=f"当前起始日期: {self.current_date}")
                for child in date_btn_frame.winfo_children(): child.configure(state="normal")

        ttk.Radiobutton(mode_frame, text="历史回测 (真实历史数据)", variable=self.mode_var, value="history", command=on_mode_change).pack(anchor="w", pady=2)
        ttk.Radiobutton(mode_frame, text="模拟挑战 (模拟世界生成)", variable=self.mode_var, value="simulation", command=on_mode_change).pack(anchor="w", pady=2)

        # 2. 设定时间 (保持不变)
        date_frame = ttk.LabelFrame(dialog, text="2. 设定时间 (仅历史模式)", padding=15)
        date_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.start_date_display.pack_forget()
        self.start_date_display = ttk.Label(date_frame, text=f"当前: {self.current_date}", foreground="#007bff", font=('Arial', 10, 'bold'))
        self.start_date_display.pack(pady=(0, 10))
        
        date_btn_frame = ttk.Frame(date_frame)
        date_btn_frame.pack(fill=tk.X)
        ttk.Button(date_btn_frame, text="🎲 随机历史日期", command=self._set_random_start_date, bootstyle="info-outline").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(date_btn_frame, text="📅 指定日期", command=self._set_custom_start_date, bootstyle="info-outline").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # --- 3. 筛选条件 (新增部分) ---
        filter_frame = ttk.LabelFrame(dialog, text="3. 板块筛选", padding=15)
        filter_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 定义状态变量
        self.filter_main = tk.BooleanVar(value=True)   # 主板
        self.filter_300 = tk.BooleanVar(value=False)    # 创业板
        self.filter_688 = tk.BooleanVar(value=False)   # 科创板 (默认不选，新手友好)
        
        # 放置复选框 (一行放三个)
        cb_frame = ttk.Frame(filter_frame)
        cb_frame.pack(fill=tk.X)
        
        ttk.Checkbutton(cb_frame, text="主板 (60/00)", variable=self.filter_main, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(cb_frame, text="创业板 (300)", variable=self.filter_300, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(cb_frame, text="科创板 (688)", variable=self.filter_688, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)
        # ---------------------------

        # 4. 开始游戏 (标题改为步骤4)
        stock_frame = ttk.LabelFrame(dialog, text="4. 开始游戏", padding=15)
        stock_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(stock_frame, text="指定单只股票", command=lambda: self._select_single_stock(dialog), width=20).pack(pady=5)
        
        # 随机选股按钮 (会用到上面的筛选条件)
        ttk.Button(stock_frame, text="随机 10 只股票", command=lambda: self._select_random_stocks(dialog), width=20, bootstyle="primary").pack(pady=5)
        
        ttk.Button(stock_frame, text="市场全部股票", command=lambda: self._select_all_stocks(dialog), width=20).pack(pady=5)

    def _set_random_start_date(self):
        """Set a random start date"""
        import random
        # 范围：从第15天 到 倒数第100天
        min_idx = 15
        max_idx = max(15, len(self.available_dates) - 100)
        
        self.start_date_idx = random.randint(min_idx, max_idx)
        self.current_date_idx = self.start_date_idx
        self.current_date = self.available_dates[self.current_date_idx]
        
        # 更新主界面显示
        self.date_label.config(text=self.current_date)
        
        # --- 关键：同时更新弹窗里的显示 ---
        # 检查 start_date_display 是否存在且可用
        try:
            if hasattr(self, 'start_date_display') and self.start_date_display.winfo_exists():
                self.start_date_display.config(text=f"当前起始日期: {self.current_date}")
        except:
            pass
            
        self._update_market_bar()
    
    def _set_custom_start_date(self):
        """Set a custom start date"""
        date_str = simpledialog.askstring(
            "指定日期",
            f"请输入日期 (YYYY-MM-DD)\n可用范围: {self.available_dates[15]} 至 {self.available_dates[-100]}",
            parent=self.root
        )
        if date_str and date_str in self.available_dates:
            idx = self.available_dates.index(date_str)
            if idx >= 15:  # Ensure at least 15 days of history
                self.start_date_idx = idx
                self.current_date_idx = self.start_date_idx
                self.current_date = self.available_dates[self.current_date_idx]
                self.date_label.config(text=self.current_date)
                self.start_date_display.config(text=f"当前: {self.current_date}")
                self._update_market_bar()
            else:
                messagebox.showwarning("警告", "日期太早,需要至少15个交易日的历史")
        elif date_str:
            messagebox.showwarning("警告", "无效的日期")
    
    def _select_single_stock(self, dialog):
        """Select single stock"""
        code = simpledialog.askstring("输入股票代码", "请输入6位股票代码:", parent=dialog)
        if code:
            # --- 新增：模拟模式下的日期重置逻辑 ---
            if self.data_loader.sim_mode:
                # 重新同步日期列表（防止缓存问题）
                self.available_dates = self.data_loader.get_available_dates()
                # 重置到第一天
                self.start_date_idx = 0
                self.current_date_idx = 0
                self.current_date = self.available_dates[0]
                # 更新日期显示
                self.date_label.config(text=self.current_date)
                self._update_market_bar()
            # ----------------------------------

            self.watched_stocks = [code]
            self._refresh_stock_list()
            self._update_chart()
            self._update_account_display()
            self._update_trade_estimate() # 刷新预估价
            dialog.destroy()
    
    def _select_random_stocks(self, dialog):
        """Select random 10 stocks with Board Filtering"""
        # 1. 收集筛选前缀
        prefixes = []
        if self.filter_main.get():
            prefixes.extend(['00', '60']) # 主板
        if self.filter_300.get():
            prefixes.append('300')        # 创业板
        if self.filter_688.get():
            prefixes.append('688')        # 科创板
            
        # 2. 校验是否至少选了一个
        if not prefixes:
            messagebox.showwarning("提示", "请至少选择一个板块！")
            return

        # 3. 同步日期 (原有逻辑)
        self.available_dates = self.data_loader.get_available_dates()
        target_date_for_selection = self.current_date
        
        if self.data_loader.sim_mode:
            self.start_date_idx = 0
            self.current_date_idx = 0
            self.current_date = self.available_dates[0]
            self.date_label.config(text=self.current_date)
            self._update_market_bar()
            target_date_for_selection = "2023-06-01" 
        else:
            target_date_for_selection = self.current_date

        # 4. 传参给 data_loader (新增 prefixes 参数)
        stocks = self.data_loader.get_random_stocks(target_date_for_selection, 10, prefixes=prefixes)
        
        if not stocks:
            board_names = []
            if self.filter_main.get(): board_names.append("主板")
            if self.filter_300.get(): board_names.append("创业板")
            if self.filter_688.get(): board_names.append("科创板")
            name_str = "+".join(board_names)
            
            messagebox.showwarning("提示", f"在日期 {target_date_for_selection}\n[{name_str}] 没有找到可交易的股票。\n\n可能原因：\n1. 当年该板块还未开市（如科创板2019年才开）。\n2. 数据缺失。")
            return

        self.watched_stocks = stocks
        
        # 5. 刷新界面 (原有逻辑)
        self._refresh_stock_list()
        if self.watched_stocks:
            self.current_stock = self.watched_stocks[0]
            items = self.stock_tree.get_children()
            if items: self.stock_tree.selection_set(items[0])
        
        self._update_chart()
        self._update_account_display()
        self._update_trade_estimate()
        dialog.destroy()

    def _select_all_stocks(self, dialog):
        """Select all market stocks"""
        self.watched_stocks = self.data_loader.get_stock_list(self.current_date)
        self._refresh_stock_list()
        self._update_chart()
        self._update_account_display()
        dialog.destroy()
    
    def _refresh_stock_list(self):
        """Refresh stock list (Optimized Version)"""
        # 1. 清空旧数据
        for item in self.stock_tree.get_children():
            self.stock_tree.delete(item)
            
        # --- 优化开始：只查询我关注的股票 ---
        # 合并所有需要查询的代码（置顶 + 关注），去重
        target_codes = list(set(self.pinned_stocks + self.watched_stocks))
        
        # 如果列表为空（比如刚启动），可能不需要查库，或者查全部（取决于需求）
        # 这里为了不报错，如果为空就不查了
        if not target_codes:
            daily_df = pd.DataFrame()
        else:
            # 传入 target_codes，让 DuckDB 只吐出这几十条数据
            daily_df = self.data_loader.get_daily_snapshot(self.current_date, codes=target_codes)
        # --- 优化结束 ---
        
        price_map = {}
        if not daily_df.empty:
            pct_col = 'pctChg' if 'pctChg' in daily_df.columns else 'pct_chg'
            for _, row in daily_df.iterrows():
                try:
                    price_map[row['code']] = (float(row['close']), float(row[pct_col]))
                except:
                    price_map[row['code']] = (0.0, 0.0)

        # 3. 准备数据 (后续逻辑保持不变)
        search_term = self.search_var.get().upper().strip()
        display_list = []
        
        def match_search(c):
            if not search_term: return True
            if search_term in c: return True
            return False

        for code in self.pinned_stocks:
            if code in self.watched_stocks and match_search(code):
                display_list.append((code, True))
        
        for code in self.watched_stocks:
            if code not in self.pinned_stocks and match_search(code):
                display_list.append((code, False))

        # 4. 批量插入数据 (保持不变)
        for code, is_pinned in display_list:
            name = self.data_loader.get_stock_name(code)
            
            close, pct = 0.0, 0.0
            if code in price_map:
                close, pct = price_map[code]
            
            tag = "flat"
            if pct > 0: tag = "up"
            elif pct < 0: tag = "down"
            
            prefix = "📌 " if is_pinned else ""
            display_stock = f"{prefix}{code} {name}"
            
            self.stock_tree.insert(
                "", 
                "end", 
                iid=code, 
                values=(display_stock, f"{close:.2f}", f"{pct:+.2f}%"),
                tags=(tag,)
            )

    def _on_tree_select(self, event):
        """Handle Treeview selection"""
        selected_items = self.stock_tree.selection()
        if not selected_items:
            return
            
        # 我们在 insert 时把 iid 设置为了 code，所以直接获取即可
        code = selected_items[0]
        
        self.current_stock = code
        self._update_chart()
        self._update_metrics()
        self._update_trade_estimate()

    def _on_tree_right_click(self, event):
        """Handle right click on Treeview"""
        # 找到鼠标点击的那一行
        item_id = self.stock_tree.identify_row(event.y)
        if not item_id:
            return
            
        code = item_id
        
        if code in self.pinned_stocks:
            self.pinned_stocks.remove(code)
        else:
            self.pinned_stocks.append(code)
            
        self._refresh_stock_list()

    def _on_search(self, *args):
        """Handle search box input"""
        # 现在的列表是自定义绘制的，不需要在这里操作 insert/delete
        # 只需要触发刷新，刷新函数会读取 search_var 自动过滤
        self._refresh_stock_list()
    
    def _update_chart(self):
        """Update chart for current stock"""
        if not self.current_stock:
            return
        
        # Get historical data
        end_idx = self.current_date_idx
        days_before = max(15, config.CHART_WINDOW_DAYS)
        start_idx = max(0, end_idx - days_before + 1)
        
        start_date = self.available_dates[start_idx]
        end_date = self.current_date
        
        data = self.data_loader.get_stock_data(self.current_stock, start_date, end_date)
        
        if not data.empty:
            # --- 新增：获取当前股票的交易记录 ---
            trades = self.account.trade_log.get_trades_for_stock(self.current_stock)
            
            # --- 修改：传递数据 AND 交易记录 ---
            self.chart_panel.update_chart(data, trades)
            
            # Update stock info label
            current_data = data[data['date'] == self.current_date]
            if not current_data.empty:
                row = current_data.iloc[0]
                
                # 兼容代码
                pct_val = 0.0
                if 'pctChg' in row: pct_val = row['pctChg']
                elif 'pct_chg' in row: pct_val = row['pct_chg']

                info_text = f"{self.current_stock} | 开:{row['open']:.2f} 高:{row['high']:.2f} 低:{row['low']:.2f} 收:{row['close']:.2f} 涨跌:{pct_val:+.2f}%"
                self.stock_info_label.config(text=info_text)
        
        # 确保右侧交易面板的预估价也刷新
        self._update_trade_estimate()
    
    def _update_metrics(self):
        """Update financial metrics display"""
        if not self.current_stock:
            return
        
        # 从 DuckDB/Pandas 获取当天数据
        data = self.data_loader.get_stock_data_on_date(self.current_stock, self.current_date)
        
        if data:
            # 定义一个辅助函数来安全地格式化数字
            def fmt(val):
                try:
                    if val is None or pd.isna(val) or val == 0:
                        return "--"
                    return f"{float(val):.2f}"
                except:
                    return "--"

            # 使用新的键名 (peTTM, pbMRQ, psTTM, pcfNcfTTM)
            self.metrics_labels['peTTM'].config(text=fmt(data.get('peTTM')))
            self.metrics_labels['pbMRQ'].config(text=fmt(data.get('pbMRQ')))
            self.metrics_labels['psTTM'].config(text=fmt(data.get('psTTM')))
            self.metrics_labels['pcfNcfTTM'].config(text=fmt(data.get('pcfNcfTTM')))
        else:
            # 如果当天没有数据，重置为 --
            for key in ['peTTM', 'pbMRQ', 'psTTM', 'pcfNcfTTM']:
                self.metrics_labels[key].config(text="--")
    
    def _update_market_bar(self):
        """Update the market index bar at the top"""
        # 获取大盘数据
        data = self.data_loader.get_stock_data_on_date(self.market_index_code, self.current_date)
        
        if not data:
            self.market_label.config(text=f"上证指数 ({self.market_index_code}): 休市或无数据", background="#6c757d")
            return

        # 获取收盘价和涨跌幅 (兼容字段名)
        close = data['close']
        pct_val = 0.0
        if 'pctChg' in data:
            pct_val = data['pctChg']
        elif 'pct_chg' in data:
            pct_val = data['pct_chg']
            
        # 决定颜色和符号
        if pct_val > 0:
            bg_color = config.COLOR_RISE # 红
            symbol = "▲"
        elif pct_val < 0:
            bg_color = config.COLOR_FALL # 绿
            symbol = "▼"
        else:
            bg_color = "#6c757d" # 灰
            symbol = "-"
            
        # 格式化文本
        text = f"上证指数: {close:.2f}  {symbol} {pct_val:+.2f}%"
        
        # 更新 UI (Label 背景色需要通过样式或直接 configure 修改)
        # ttkbootstrap 的 Label 设置 background 可能需要特定写法，这里用 standard config 兼容
        self.market_label.config(text=text, background=bg_color)
    
    def _update_account_display(self):
        """Update account information display"""
        # Update prices for all positions
        prices = {}
        for code in self.account.positions.keys():
            data = self.data_loader.get_stock_data_on_date(code, self.current_date)
            if data:
                prices[code] = data['close']
        
        self.account.update_position_prices(prices)
        
        # Update account labels
        self.account_labels['cash'].config(text=format_currency(self.account.cash))
        self.account_labels['market_value'].config(text=format_currency(self.account.total_market_value))
        self.account_labels['total_equity'].config(text=format_currency(self.account.total_equity))
        self.account_labels['profit'].config(text=format_currency(self.account.total_profit))
        self.account_labels['profit_pct'].config(text=format_percentage(self.account.total_profit_pct))
        
        # Color code profit/loss
        profit_color = 'red' if self.account.total_profit >= 0 else 'green'
        self.account_labels['profit'].config(foreground=profit_color)
        self.account_labels['profit_pct'].config(foreground=profit_color)
        
        # Update positions tree
        for item in self.position_tree.get_children():
            self.position_tree.delete(item)
        
        for pos in self.account.get_all_positions():
            # 修改：只显示 股票、数量、盈亏% 三列
            values = (
                pos.code,
                pos.quantity,
                f"{pos.profit_pct:+.2f}%"
            )
            tag = 'profit' if pos.profit >= 0 else 'loss'
            self.position_tree.insert('', tk.END, values=values, tags=(tag,))
        
        self.position_tree.tag_configure('profit', foreground='red')
        self.position_tree.tag_configure('loss', foreground='green')
    
    def _next_day(self):
        """Advance to next trading day"""
        if self.current_date_idx >= len(self.available_dates) - 1:
            messagebox.showinfo("提示", "已到最后一个交易日")
            return
        
        self.current_date_idx += 1
        self.current_date = self.available_dates[self.current_date_idx]
        self.date_label.config(text=self.current_date)
        
        # Record equity
        self.account.record_equity(self.current_date)
        
        # --- 新增调用 ---
        self._update_market_bar()
        self._update_trade_estimate()
        # ----------------
        
        # Update displays
        self._update_chart()
        self._update_metrics()
        self._update_account_display()
        # --- 新增：日期变了，刷新左侧列表价格 ---
        self._refresh_stock_list()
        
        self.trade_status_label.config(text="")
    
    def _prev_day(self):
        """Go to previous trading day"""
        # Allow going back to see history, but only to start_date_idx - 15 for context
        min_idx = max(0, self.start_date_idx - 15)
        if self.current_date_idx <= min_idx:
            messagebox.showinfo("提示", "已到最早可查看日期")
            return
        
        self.current_date_idx -= 1
        self.current_date = self.available_dates[self.current_date_idx]
        self.date_label.config(text=self.current_date)
        
        self._update_chart()
        self._update_metrics()
        self._update_account_display()
        self._update_market_bar()
        self._update_trade_estimate()
        # --- 新增：日期变了，刷新左侧列表价格 ---
        self._refresh_stock_list()

    def _toggle_autoplay(self):
        """Toggle auto-play state"""
        if self.is_playing:
            # 停止播放
            self.is_playing = False
            self.play_btn.config(text="▶ 自动", bootstyle="primary-outline")
        else:
            # 开始播放
            self.is_playing = True
            self.play_btn.config(text="⏸ 暂停", bootstyle="warning") # 变色提醒正在播放
            self._auto_play_step()

    def _auto_play_step(self):
        """Execute one step of auto-play and schedule next"""
        # 1. 如果状态变成停止，或者已经到最后一天，则停止
        if not self.is_playing:
            return
            
        if self.current_date_idx >= len(self.available_dates) - 1:
            self.is_playing = False
            self.play_btn.config(text="▶ 自动", bootstyle="primary-outline")
            messagebox.showinfo("提示", "回测结束")
            return

        # 2. 执行下一日
        self._next_day()
        
        # 3. 预约下一次执行 (时间单位 ms)
        # 300ms 是一个比较舒适的速度，既能看清K线变化，又不会太慢
        # 如果觉得太快可以改成 500，太慢改成 100
        if self.is_playing:
            self.root.after(300, self._auto_play_step)
    
    def _cycle_stock(self, direction: int):
        """Keyboard navigation for Treeview"""
        children = self.stock_tree.get_children()
        if not children:
            return "break"
            
        selected = self.stock_tree.selection()
        if not selected:
            current_idx = -1
        else:
            current_idx = children.index(selected[0])
            
        next_idx = (current_idx + direction) % len(children)
        next_item = children[next_idx]
        
        # 选中并滚动可见
        self.stock_tree.selection_set(next_item)
        self.stock_tree.see(next_item)
        
        # 触发选中逻辑
        self._on_tree_select(None)
        
        return "break"

    def _buy_stock(self):
        """Execute buy order"""
        if not self.current_stock:
            messagebox.showwarning("警告", "请先选择股票")
            return
        
        try:
            quantity = int(self.quantity_var.get())
            if quantity <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("警告", "请输入有效的数量")
            return
        
        # Get current price (use next day's open price for execution)
        next_date = self.data_loader.get_next_date(self.current_date)
        if not next_date:
            messagebox.showwarning("警告", "当前是最后一个交易日,无法交易")
            return
        
        next_data = self.data_loader.get_stock_data_on_date(self.current_stock, next_date)
        if not next_data:
            messagebox.showwarning("警告", "股票数据不可用")
            return
        
        price = next_data['open']
        
        # Execute buy
        success = self.account.buy(next_date, self.current_stock, quantity, price)
        
        if success:
            self.trade_status_label.config(
                text=f"✓ 买入成功: {quantity}股 @ ¥{price:.2f}",
                foreground="green"
            )
            self._update_account_display()
        else:
            self.trade_status_label.config(
                text="✗ 买入失败: 资金不足",
                foreground="red"
            )
    
    def _sell_stock(self):
        """Execute sell order"""
        if not self.current_stock:
            messagebox.showwarning("警告", "请先选择股票")
            return
        
        try:
            quantity = int(self.quantity_var.get())
            if quantity <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("警告", "请输入有效的数量")
            return
        
        # Get current price (use next day's open price for execution)
        next_date = self.data_loader.get_next_date(self.current_date)
        if not next_date:
            messagebox.showwarning("警告", "当前是最后一个交易日,无法交易")
            return
        
        next_data = self.data_loader.get_stock_data_on_date(self.current_stock, next_date)
        if not next_data:
            messagebox.showwarning("警告", "股票数据不可用")
            return
        
        price = next_data['open']
        
        # Execute sell
        success = self.account.sell(next_date, self.current_stock, quantity, price)
        
        if success:
            self.trade_status_label.config(
                text=f"✓ 卖出成功: {quantity}股 @ ¥{price:.2f}",
                foreground="green"
            )
            self._update_account_display()
        else:
            self.trade_status_label.config(
                text="✗ 卖出失败: 持仓不足",
                foreground="red"
            )
    
    def _show_performance(self):
        """Show performance window"""
        PerformanceWindow(self.root, self.account)
    
    def _show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "关于",
            "股票交易模拟器 v1.0\n\n"
            "使用历史数据进行股票交易模拟\n"
            "数据范围: 2012-2025年\n\n"
            "祝您交易愉快!"
        )
    
    def run(self):
        """Start the application"""
        self.root.mainloop()

    def _save_game(self):
        """Save current game state to a JSON file"""
        if not self.available_dates:
            messagebox.showwarning("错误", "数据尚未加载完成")
            return

        # 1. 收集游戏状态
        game_state = {
            'version': '1.0',
            'current_date': self.current_date,
            'watched_stocks': self.watched_stocks,
            'pinned_stocks': self.pinned_stocks,
            'current_stock': self.current_stock,
            # 序列化账户数据
            'account': self.account.to_dict()
        }
        
        # 2. 弹出保存文件对话框
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="保存游戏存档"
        )
        
        if not file_path:
            return
            
        # 3. 写入文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(game_state, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("成功", f"游戏已保存至:\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败:\n{str(e)}")

    def _load_game(self) -> bool:
        """
        Load game state from a JSON file.
        Returns: True if loaded successfully, False otherwise.
        """
        # 1. 弹出打开文件对话框
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="读取游戏存档"
        )
        
        if not file_path:
            return False # 用户取消
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # 2. 校验数据有效性
            loaded_date = state.get('current_date')
            if loaded_date not in self.available_dates:
                if loaded_date < self.available_dates[0] or loaded_date > self.available_dates[-1]:
                    messagebox.showerror("错误", f"存档日期 {loaded_date} 超出当前数据库范围！")
                    return False
                else:
                    if loaded_date not in self.available_dates:
                        messagebox.showwarning("警告", f"存档日期 {loaded_date} 在当前数据中不存在，可能数据源已变更。")
                        return False

            # 3. 恢复游戏状态
            self.current_date = loaded_date
            self.current_date_idx = self.available_dates.index(self.current_date)
            
            self.watched_stocks = state.get('watched_stocks', [])
            self.pinned_stocks = state.get('pinned_stocks', [])
            self.current_stock = state.get('current_stock')
            
            # 恢复账户
            self.account = Account.from_dict(state['account'])
            
            # 4. 刷新界面
            self.date_label.config(text=self.current_date)
            self._refresh_stock_list()
            
            if self.current_stock and self.current_stock not in self.data_loader.get_stock_list(self.current_date):
                 pass

            self._update_market_bar()
            self._update_chart()
            self._update_metrics()
            self._update_account_display()
            # 刷新右侧交易面板预估价
            self._update_trade_estimate()
            # --- 新增：日期变了，刷新左侧列表价格 ---
            self._refresh_stock_list()
            
            messagebox.showinfo("成功", "存档读取成功！")
            return True # 成功加载
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"读取存档失败:\n{str(e)}")
            return False
    
    def _update_trade_estimate(self, *args):
        """
        Calculate and display estimated trade amount based on CURRENT day's close price.
        修正：使用当日收盘价作为参考，避免泄露未来数据（次日开盘价）。
        """
        if not self.current_stock:
            self.trade_price_label.config(text="请选股")
            self.trade_amount_label.config(text="--")
            return

        # 1. 获取当日价格 (作为参考)
        # 逻辑：用户在做决策时，只能看到当天的收盘价。
        # 虽然实际成交是明天的开盘价，但预估金额应基于已知数据。
        current_data = self.data_loader.get_stock_data_on_date(self.current_stock, self.current_date)
        price = 0.0
        
        if current_data:
            price = current_data['close']
            # 可以选择加上 "(收)" 提示用户这是收盘价参考
            self.trade_price_label.config(text=f"¥{price:.2f}")
        else:
            self.trade_price_label.config(text="无数据")
            
        # 2. 计算预计总额
        try:
            qty_str = self.quantity_var.get()
            if not qty_str:
                self.trade_amount_label.config(text="--")
                return
                
            qty = int(qty_str)
            if price > 0:
                # 简单预估总额
                total = price * qty
                self.trade_amount_label.config(text=f"¥{total:,.2f}")
            else:
                self.trade_amount_label.config(text="--")
        except ValueError:
            self.trade_amount_label.config(text="数量无效")


def main():
    """Main entry point"""
    
    # --- 新增：开启高分屏(High-DPI)支持 ---
    try:
        import ctypes
        # 告诉 Windows 系统：我是高分屏程序，不要对我进行缩放（防止模糊）
        # SetProcessDpiAwareness(1) 表示 PROCESS_SYSTEM_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        # 兼容旧版 Windows (Win7/8)
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    # ------------------------------------

    app = StockTradingGame()
    
    # 如果在 4K 屏上觉得界面组件还是太小，可以在这里手动调整缩放比例
    # 例如：app.root.place_window_center() 之前设置
    # app.root.tk.call('tk', 'scaling', 2.0) 
    
    app.run()


if __name__ == "__main__":
    main()
