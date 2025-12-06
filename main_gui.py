"""
Main GUI for Stock Trading Game
集成功能:
1. 蒙特卡洛模拟/历史回测双模式
2. 板块筛选 (主板/创业板/科创板)
3. UI 美化 (卡片式布局、更现代的配色与字体)
4. 存档/读档
5. 自动播放与键盘快捷键
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import pandas as pd
from typing import List, Optional
import config
from data_loader import DataLoader
from game_engine import Account
from chart_panel import ChartPanel
from performance_window import PerformanceWindow
from utils import format_currency, format_percentage
import json
import ctypes # 用于高分屏支持

class StockTradingGame:
    """Main application window"""
    
    def __init__(self):
        """Initialize the game"""
        # Initialize data and game state
        self.data_loader = DataLoader()
        self.account = Account()

        # 定义大盘指数代码
        self.market_index_code = 'sh.000001' 
        
        # Get available dates
        self.available_dates = self.data_loader.get_available_dates()
        # Start date will be set after selection
        self.start_date_idx = 15  # Default buffer
        self.current_date_idx = self.start_date_idx
        self.current_date = self.available_dates[self.current_date_idx]
        
        # Stock list management
        self.watched_stocks: List[str] = []
        self.pinned_stocks: List[str] = []
        self.current_stock: Optional[str] = None

        # 自动播放状态
        self.is_playing = False
        
        # Create main window
        self.root = ttkb.Window(themename=config.THEME)
        self.root.title(config.WINDOW_TITLE)
        
        # --- 设置窗口最大化与适配 ---
        self.root.geometry("1280x800")
        try:
            self.root.state('zoomed') # Windows
        except:
            try:
                self.root.attributes('-zoomed', True) # Linux
            except:
                w = self.root.winfo_screenwidth()
                h = self.root.winfo_screenheight()
                self.root.geometry(f"{w}x{h}")
        # -------------------------
        
        # Create UI
        self._create_menu()
        self._create_widgets()
        
        # Show stock selection dialog after init
        self.root.after(100, self._show_stock_selection)

        # 绑定快捷键
        self.root.bind('<space>', lambda e: self._next_day())
        self.root.bind('<Left>', lambda e: self._prev_day())
        self.root.bind('<Right>', lambda e: self._next_day())
        self.root.bind('<Up>', lambda e: self._buy_stock())
        self.root.bind('<Down>', lambda e: self._sell_stock())
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
        file_menu.add_command(label="保存存档", command=self._save_game)
        file_menu.add_command(label="读取存档", command=self._load_game)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        
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
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 1. Left Sidebar (Stock List)
        left_frame = ttk.Frame(main_container, width=600)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False) # 固定宽度
        
        self._create_stock_list(left_frame)
        
        # 2. Right Sidebar (Controls & Info)
        right_frame = ttk.Frame(main_container, width=400)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_frame.pack_propagate(False) # 固定宽度
        
        self._create_right_panel(right_frame)
        
        # 3. Center Panel (Chart)
        center_frame = ttk.Frame(main_container)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self._create_center_panel(center_frame)
    
    def _create_stock_list(self, parent):
        """Create stock list sidebar with beautified Treeview"""
        ttk.Label(parent, text="股票列表", font=('Microsoft YaHei', 12, 'bold')).pack(pady=5)
        
        # Search box
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=('Arial', 10))
        search_entry.pack(fill=tk.X)
        
        # List Frame
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=2)
        
        columns = ("stock", "price", "pct")
        
        # [UI美化] 配置 Treeview 样式
        style = ttk.Style()
        style.configure("Treeview", 
                        font=('Arial', 10), 
                        rowheight=28) # 增加行高，更宽松
        style.configure("Treeview.Heading", 
                        font=('Microsoft YaHei', 9, 'bold'))

        self.stock_tree = ttk.Treeview(
            list_frame, 
            columns=columns, 
            show="headings", 
            selectmode="browse",
            height=20,
            bootstyle="primary"
        )
        
        self.stock_tree.heading("stock", text="代码/名称", anchor="w")
        self.stock_tree.heading("price", text="现价", anchor="e")
        self.stock_tree.heading("pct", text="涨幅", anchor="e")
        
        self.stock_tree.column("stock", width=110, minwidth=90, anchor="w")
        self.stock_tree.column("price", width=60, minwidth=50, anchor="e")
        self.stock_tree.column("pct", width=60, minwidth=50, anchor="e")
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.stock_tree.yview)
        self.stock_tree.configure(yscrollcommand=scrollbar.set)
        
        self.stock_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 配置颜色 Tag (支持斑马纹背景需配合 style，此处主要配置字体色)
        self.stock_tree.tag_configure("up", foreground=config.COLOR_RISE)
        self.stock_tree.tag_configure("down", foreground=config.COLOR_FALL)
        self.stock_tree.tag_configure("flat", foreground="gray")

        self.stock_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.stock_tree.bind("<Button-3>", self._on_tree_right_click)

    def _create_center_panel(self, parent):
        """Create center panel with chart and top controls"""
        # Top info bar
        info_frame = ttk.Frame(parent)
        info_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        # 大盘行情条 (UI美化：背景浅灰，文字带色)
        self.market_bar_frame = ttkb.Frame(info_frame, padding=8, bootstyle="light")
        self.market_bar_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        self.market_label = ttk.Label(
            self.market_bar_frame, 
            text="正在加载大盘数据...", 
            font=('Microsoft YaHei', 14, 'bold'),
            foreground="#666666",
            background="#f8f9fa",
            anchor="center"
        )
        self.market_label.pack(fill=tk.X)

        # Date display and navigation
        date_frame = ttk.Frame(info_frame)
        date_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(date_frame, text="当前日期:").pack(side=tk.LEFT, padx=5)
        self.date_label = ttk.Label(date_frame, text=self.current_date, font=('Arial', 12, 'bold'))
        self.date_label.pack(side=tk.LEFT)
        
        # 自动播放与下一日
        self.play_btn = ttkb.Button(
            date_frame, 
            text="▶ 自动", 
            command=self._toggle_autoplay,
            bootstyle="primary-outline",
            width=8
        )
        self.play_btn.pack(side=tk.LEFT, padx=(20, 5))
        
        ttk.Button(
            date_frame, 
            text="下一日 ▶", 
            command=self._next_day, 
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        # Stock info
        stock_info_frame = ttk.Frame(info_frame)
        stock_info_frame.pack(side=tk.RIGHT)
        
        self.stock_info_label = ttk.Label(stock_info_frame, text="请选择股票", font=('Arial', 10))
        self.stock_info_label.pack()
        
        # Chart panel
        self.chart_panel = ChartPanel(parent)
        self.chart_panel.get_frame().pack(fill=tk.BOTH, expand=True)
    
    def _create_right_panel(self, parent):
        """Create right panel with Modern UI (Card Style)"""
        
        # --- 1. 账户概览卡片 ---
        account_frame = ttk.LabelFrame(parent, text=" 💼 账户资产 ", padding=15, bootstyle="primary")
        account_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Grid layout for account info
        ttk.Label(account_frame, text="总资产", foreground='gray').grid(row=0, column=0, sticky='w')
        self.account_labels = {}
        
        self.account_labels['total_equity'] = ttk.Label(account_frame, text="--", font=('Microsoft YaHei', 16, 'bold'), foreground='#333')
        self.account_labels['total_equity'].grid(row=1, column=0, sticky='w', columnspan=2, pady=(0, 10))

        ttk.Label(account_frame, text="可用现金", font=('Arial', 9), foreground='gray').grid(row=2, column=0, sticky='w')
        ttk.Label(account_frame, text="持仓市值", font=('Arial', 9), foreground='gray').grid(row=2, column=1, sticky='w', padx=10)
        
        self.account_labels['cash'] = ttk.Label(account_frame, text="--", font=('Arial', 10))
        self.account_labels['cash'].grid(row=3, column=0, sticky='w')
        
        self.account_labels['market_value'] = ttk.Label(account_frame, text="--", font=('Arial', 10))
        self.account_labels['market_value'].grid(row=3, column=1, sticky='w', padx=10)

        ttk.Separator(account_frame).grid(row=4, column=0, columnspan=2, sticky='ew', pady=10)
        
        ttk.Label(account_frame, text="总盈亏", foreground='gray').grid(row=5, column=0, sticky='w')
        self.account_labels['profit'] = ttk.Label(account_frame, text="--", font=('Arial', 11, 'bold'))
        self.account_labels['profit'].grid(row=6, column=0, sticky='w')
        
        self.account_labels['profit_pct'] = ttk.Label(account_frame, text="--", font=('Arial', 11, 'bold'))
        self.account_labels['profit_pct'].grid(row=6, column=1, sticky='w', padx=10)

        # --- 2. 交易面板卡片 ---
        trade_frame = ttk.LabelFrame(parent, text=" ⚡ 快速交易 ", padding=15, bootstyle="info")
        trade_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Price Estimate
        p_frame = ttk.Frame(trade_frame)
        p_frame.pack(fill=tk.X, pady=5)
        ttk.Label(p_frame, text="预估单价:").pack(side=tk.LEFT)
        self.trade_price_label = ttk.Label(p_frame, text="--", font=('Arial', 12, 'bold'), foreground="#e67e22")
        self.trade_price_label.pack(side=tk.RIGHT)
        
        # Quantity
        q_frame = ttk.Frame(trade_frame)
        q_frame.pack(fill=tk.X, pady=5)
        ttk.Label(q_frame, text="数量(股):").pack(side=tk.LEFT)
        
        self.quantity_var = tk.StringVar(value="100")
        self.quantity_var.trace("w", self._update_trade_estimate)
        # 仓位快捷键 Frame
        pos_btn_frame = ttk.Frame(trade_frame)
        pos_btn_frame.pack(fill=tk.X, pady=2)
        
        def set_pos(percent):
            # 获取参考价格 (当前收盘价)
            try:
                price_str = self.trade_price_label.cget("text").replace("¥", "")
                price = float(price_str)
                if price <= 0: return
                
                # 计算最大可买股数
                max_cash = self.account.cash * percent
                # 向下取整到 100 股
                shares = int(max_cash / price / 100) * 100
                if shares < 0: shares = 0
                
                self.quantity_var.set(str(shares))
            except:
                pass

        ttk.Button(pos_btn_frame, text="1/4", width=4, style="info-outline", command=lambda: set_pos(0.25)).pack(side=tk.LEFT, padx=2)
        ttk.Button(pos_btn_frame, text="1/2", width=4, style="info-outline", command=lambda: set_pos(0.5)).pack(side=tk.LEFT, padx=2)
        ttk.Button(pos_btn_frame, text="全仓", width=4, style="warning-outline", command=lambda: set_pos(0.99)).pack(side=tk.LEFT, padx=2)
        
        qty_entry = ttk.Entry(q_frame, textvariable=self.quantity_var, width=12, justify="center", font=('Arial', 10))
        qty_entry.pack(side=tk.RIGHT)

        # Total Amount
        amt_row = ttk.Frame(trade_frame)
        amt_row.pack(fill=tk.X, pady=5)
        ttk.Label(amt_row, text="预计金额:").pack(side=tk.LEFT)
        self.trade_amount_label = ttk.Label(amt_row, text="--", font=('Arial', 10, 'bold'))
        self.trade_amount_label.pack(side=tk.RIGHT)

        # Buttons
        btn_frame = ttk.Frame(trade_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttkb.Button(btn_frame, text="买 入", command=self._buy_stock, bootstyle="success", width=10).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ttkb.Button(btn_frame, text="卖 出", command=self._sell_stock, bootstyle="danger", width=10).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))
        
        self.trade_status_label = ttk.Label(trade_frame, text="准备就绪", font=('Arial', 8), foreground="gray", anchor="center")
        self.trade_status_label.pack(fill=tk.X, pady=(5,0))

        # --- 3. 持仓列表 ---
        pos_frame = ttk.LabelFrame(parent, text="当前持仓", padding=5)
        pos_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        cols = ('股票', '数量', '盈亏%')
        self.position_tree = ttk.Treeview(pos_frame, columns=cols, show='headings', height=6, bootstyle="primary")
        
        self.position_tree.heading('股票', text='股票')
        self.position_tree.column('股票', width=70, anchor=tk.CENTER)
        self.position_tree.heading('数量', text='数量')
        self.position_tree.column('数量', width=60, anchor=tk.E)
        self.position_tree.heading('盈亏%', text='盈亏%')
        self.position_tree.column('盈亏%', width=70, anchor=tk.E)
        
        pos_scroll = ttk.Scrollbar(pos_frame, orient=tk.VERTICAL, command=self.position_tree.yview)
        self.position_tree.configure(yscrollcommand=pos_scroll.set)
        
        self.position_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pos_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # --- 4. Metrics ---
        metrics_frame = ttk.LabelFrame(parent, text="财务指标 (TTM)", padding=10)
        metrics_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
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
        """Show stock selection dialog (With Board Filters & Beautified)"""
        dialog = tk.Toplevel(self.root)
        dialog.title("游戏设置")
        dialog.geometry("600x900") # 调整大小以适应所有选项
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="股票交易模拟", font=('Microsoft YaHei', 16, 'bold')).pack(pady=15)
        
        # 0. 读档
        load_frame = ttk.Frame(dialog)
        load_frame.pack(fill=tk.X, padx=20, pady=5)
        ttkb.Button(load_frame, text="📂 读取旧存档", command=lambda: [self._load_game() and dialog.destroy()], bootstyle="secondary-outline").pack(fill=tk.X)

        # 1. 游戏模式
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
        ttk.Radiobutton(mode_frame, text="模拟挑战 (混沌世界生成)", variable=self.mode_var, value="simulation", command=on_mode_change).pack(anchor="w", pady=2)

        # 2. 设定时间
        date_frame = ttk.LabelFrame(dialog, text="2. 设定时间 (仅历史模式)", padding=15)
        date_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.start_date_display.pack_forget()
        self.start_date_display = ttk.Label(date_frame, text=f"当前: {self.current_date}", foreground="#007bff", font=('Arial', 10, 'bold'))
        self.start_date_display.pack(pady=(0, 10))
        
        date_btn_frame = ttk.Frame(date_frame)
        date_btn_frame.pack(fill=tk.X)
        ttkb.Button(date_btn_frame, text="🎲 随机历史日期", command=self._set_random_start_date, bootstyle="info-outline").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttkb.Button(date_btn_frame, text="📅 指定日期", command=self._set_custom_start_date, bootstyle="info-outline").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # 3. 板块筛选
        filter_frame = ttk.LabelFrame(dialog, text="3. 板块筛选", padding=15)
        filter_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.filter_main = tk.BooleanVar(value=True)   # 主板
        self.filter_300 = tk.BooleanVar(value=False)   # 创业板
        self.filter_688 = tk.BooleanVar(value=False)   # 科创板
        
        cb_frame = ttk.Frame(filter_frame)
        cb_frame.pack(fill=tk.X)
        # 必须使用 ttkb.Checkbutton 以支持 bootstyle
        ttkb.Checkbutton(cb_frame, text="主板 (60/00)", variable=self.filter_main, bootstyle="round-toggle").pack(side=tk.LEFT, padx=5)
        ttkb.Checkbutton(cb_frame, text="创业板 (300)", variable=self.filter_300, bootstyle="round-toggle").pack(side=tk.LEFT, padx=5)
        ttkb.Checkbutton(cb_frame, text="科创板 (688)", variable=self.filter_688, bootstyle="round-toggle").pack(side=tk.LEFT, padx=5)

        # 4. 开始游戏
        stock_frame = ttk.LabelFrame(dialog, text="4. 开始游戏", padding=15)
        stock_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(stock_frame, text="指定单只股票", command=lambda: self._select_single_stock(dialog), width=20).pack(pady=5)
        ttkb.Button(stock_frame, text="随机 10 只股票", command=lambda: self._select_random_stocks(dialog), width=20, bootstyle="primary").pack(pady=5)
        ttk.Button(stock_frame, text="市场全部股票", command=lambda: self._select_all_stocks(dialog), width=20).pack(pady=5)

    def _set_random_start_date(self):
        """Set a random start date"""
        import random
        min_idx = 15
        max_idx = max(15, len(self.available_dates) - 100)
        
        self.start_date_idx = random.randint(min_idx, max_idx)
        self.current_date_idx = self.start_date_idx
        self.current_date = self.available_dates[self.current_date_idx]
        
        self.date_label.config(text=self.current_date)
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
            if idx >= 15:
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
            # 模拟模式下的日期重置
            if self.data_loader.sim_mode:
                self.available_dates = self.data_loader.get_available_dates()
                self.start_date_idx = 0
                self.current_date_idx = 0
                self.current_date = self.available_dates[0]
                self.date_label.config(text=self.current_date)
                self._update_market_bar()

            self.watched_stocks = [code]
            self._refresh_stock_list()
            self._update_chart()
            self._update_account_display()
            self._update_trade_estimate()
            dialog.destroy()
    
    def _select_random_stocks(self, dialog):
        """Select random stocks with Board Filtering"""
        # 1. 收集筛选
        prefixes = []
        if self.filter_main.get(): prefixes.extend(['00', '60'])
        if self.filter_300.get(): prefixes.append('300')
        if self.filter_688.get(): prefixes.append('688')
            
        if not prefixes:
            messagebox.showwarning("提示", "请至少选择一个板块！")
            return

        # 2. 准备日期
        self.available_dates = self.data_loader.get_available_dates()
        target_date_for_selection = self.current_date
        
        if self.data_loader.sim_mode:
            self.start_date_idx = 0
            self.current_date_idx = 0
            self.current_date = self.available_dates[0]
            self.date_label.config(text=self.current_date)
            self._update_market_bar()
            target_date_for_selection = "2023-06-01" 
        
        # 3. 选股
        stocks = self.data_loader.get_random_stocks(target_date_for_selection, 10, prefixes=prefixes)
        
        if not stocks:
            messagebox.showwarning("提示", f"在日期 {target_date_for_selection} 未找到符合板块要求的股票。")
            return

        self.watched_stocks = stocks
        
        # 4. 刷新
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
        """Refresh stock list"""
        # 清空
        for item in self.stock_tree.get_children():
            self.stock_tree.delete(item)
            
        # 查询数据
        target_codes = list(set(self.pinned_stocks + self.watched_stocks))
        if not target_codes:
            daily_df = pd.DataFrame()
        else:
            daily_df = self.data_loader.get_daily_snapshot(self.current_date, codes=target_codes)
        
        price_map = {}
        if not daily_df.empty:
            pct_col = 'pctChg' if 'pctChg' in daily_df.columns else 'pct_chg'
            for _, row in daily_df.iterrows():
                try:
                    price_map[row['code']] = (float(row['close']), float(row[pct_col]))
                except:
                    price_map[row['code']] = (0.0, 0.0)

        # 过滤与排序
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

        # 插入 Treeview
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
        selected_items = self.stock_tree.selection()
        if not selected_items: return
        self.current_stock = selected_items[0]
        self._update_chart()
        self._update_metrics()
        self._update_trade_estimate()

    def _on_tree_right_click(self, event):
        item_id = self.stock_tree.identify_row(event.y)
        if not item_id: return
        code = item_id
        if code in self.pinned_stocks:
            self.pinned_stocks.remove(code)
        else:
            self.pinned_stocks.append(code)
        self._refresh_stock_list()

    def _on_search(self, *args):
        self._refresh_stock_list()
    
    def _update_chart(self):
        if not self.current_stock: return
        
        end_idx = self.current_date_idx
        days_before = max(15, config.CHART_WINDOW_DAYS)
        start_idx = max(0, end_idx - days_before + 1)
        start_date = self.available_dates[start_idx]
        end_date = self.current_date
        
        data = self.data_loader.get_stock_data(self.current_stock, start_date, end_date)
        
        if not data.empty:
            trades = self.account.trade_log.get_trades_for_stock(self.current_stock)
            self.chart_panel.update_chart(data, trades)
            
            current_data = data[data['date'] == self.current_date]
            if not current_data.empty:
                row = current_data.iloc[0]
                pct_val = 0.0
                if 'pctChg' in row: pct_val = row['pctChg']
                elif 'pct_chg' in row: pct_val = row['pct_chg']
                info_text = f"{self.current_stock} | 开:{row['open']:.2f} 高:{row['high']:.2f} 低:{row['low']:.2f} 收:{row['close']:.2f} 涨跌:{pct_val:+.2f}%"
                self.stock_info_label.config(text=info_text)
        
        self._update_trade_estimate()
    
    def _update_metrics(self):
        if not self.current_stock: return
        data = self.data_loader.get_stock_data_on_date(self.current_stock, self.current_date)
        
        def fmt(val):
            try:
                if val is None or pd.isna(val) or val == 0: return "--"
                return f"{float(val):.2f}"
            except: return "--"

        if data:
            self.metrics_labels['peTTM'].config(text=fmt(data.get('peTTM')))
            self.metrics_labels['pbMRQ'].config(text=fmt(data.get('pbMRQ')))
            self.metrics_labels['psTTM'].config(text=fmt(data.get('psTTM')))
            self.metrics_labels['pcfNcfTTM'].config(text=fmt(data.get('pcfNcfTTM')))
        else:
            for key in self.metrics_labels: self.metrics_labels[key].config(text="--")
    
    def _update_market_bar(self):
        data = self.data_loader.get_stock_data_on_date(self.market_index_code, self.current_date)
        if not data:
            self.market_label.config(text=f"上证指数 ({self.market_index_code}): 休市或无数据", background="#f8f9fa", foreground="#666")
            return

        close = data['close']
        pct_val = data.get('pctChg', data.get('pct_chg', 0.0))
        
        symbol = "▲" if pct_val > 0 else "▼" if pct_val < 0 else "-"
        color = config.COLOR_RISE if pct_val > 0 else config.COLOR_FALL if pct_val < 0 else "#666"
        
        text = f"上证指数: {close:.2f}   {symbol} {pct_val:+.2f}%"
        self.market_label.config(text=text, foreground=color, background="#f8f9fa")
    
    def _update_account_display(self):
        prices = {}
        for code in self.account.positions.keys():
            data = self.data_loader.get_stock_data_on_date(code, self.current_date)
            if data: prices[code] = data['close']
        
        self.account.update_position_prices(prices)
        
        self.account_labels['cash'].config(text=format_currency(self.account.cash))
        self.account_labels['market_value'].config(text=format_currency(self.account.total_market_value))
        self.account_labels['total_equity'].config(text=format_currency(self.account.total_equity))
        self.account_labels['profit'].config(text=format_currency(self.account.total_profit))
        self.account_labels['profit_pct'].config(text=format_percentage(self.account.total_profit_pct))
        
        profit_color = config.COLOR_RISE if self.account.total_profit >= 0 else config.COLOR_FALL
        self.account_labels['profit'].config(foreground=profit_color)
        self.account_labels['profit_pct'].config(foreground=profit_color)
        
        for item in self.position_tree.get_children():
            self.position_tree.delete(item)
        
        for pos in self.account.get_all_positions():
            values = (pos.code, pos.quantity, f"{pos.profit_pct:+.2f}%")
            tag = 'profit' if pos.profit >= 0 else 'loss'
            self.position_tree.insert('', tk.END, values=values, tags=(tag,))
        
        self.position_tree.tag_configure('profit', foreground=config.COLOR_RISE)
        self.position_tree.tag_configure('loss', foreground=config.COLOR_FALL)
    
    def _next_day(self):
        if self.current_date_idx >= len(self.available_dates) - 1:
            messagebox.showinfo("提示", "已到最后一个交易日")
            self.is_playing = False
            self.play_btn.config(text="▶ 自动", bootstyle="primary-outline")
            return
        
        self.current_date_idx += 1
        self.current_date = self.available_dates[self.current_date_idx]
        self.date_label.config(text=self.current_date)
        
        self.account.record_equity(self.current_date)
        
        self._update_market_bar()
        self._update_trade_estimate()
        self._update_chart()
        self._update_metrics()
        self._update_account_display()
        self._refresh_stock_list()
        self.trade_status_label.config(text="")
    
    def _prev_day(self):
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
        self._refresh_stock_list()

    def _toggle_autoplay(self):
        if self.is_playing:
            self.is_playing = False
            self.play_btn.config(text="▶ 自动", bootstyle="primary-outline")
        else:
            self.is_playing = True
            self.play_btn.config(text="⏸ 暂停", bootstyle="warning")
            self._auto_play_step()

    def _auto_play_step(self):
        if not self.is_playing: return
        self._next_day()
        if self.is_playing:
            self.root.after(300, self._auto_play_step)
    
    def _cycle_stock(self, direction: int):
        children = self.stock_tree.get_children()
        if not children: return "break"
        selected = self.stock_tree.selection()
        if not selected:
            current_idx = -1
        else:
            current_idx = children.index(selected[0])
        next_idx = (current_idx + direction) % len(children)
        next_item = children[next_idx]
        self.stock_tree.selection_set(next_item)
        self.stock_tree.see(next_item)
        self._on_tree_select(None)
        return "break"

    def _buy_stock(self):
        if not self.current_stock:
            messagebox.showwarning("警告", "请先选择股票")
            return
        try:
            quantity = int(self.quantity_var.get())
            if quantity <= 0: raise ValueError()
        except ValueError:
            messagebox.showwarning("警告", "请输入有效的数量")
            return
        
        next_date = self.data_loader.get_next_date(self.current_date)
        if not next_date:
            messagebox.showwarning("警告", "无法获取次日数据")
            return
        next_data = self.data_loader.get_stock_data_on_date(self.current_stock, next_date)
        if not next_data:
            messagebox.showwarning("警告", "次日数据缺失")
            return
        
        price = next_data['open']
        success = self.account.buy(next_date, self.current_stock, quantity, price)
        
        if success:
            self.trade_status_label.config(text=f"✓ 买入: {quantity}股 @ {price:.2f}", foreground="green")
            self._update_account_display()
        else:
            self.trade_status_label.config(text="✗ 资金不足", foreground="red")
    
    def _sell_stock(self):
        if not self.current_stock:
            messagebox.showwarning("警告", "请先选择股票")
            return
        try:
            quantity = int(self.quantity_var.get())
            if quantity <= 0: raise ValueError()
        except ValueError:
            messagebox.showwarning("警告", "请输入有效的数量")
            return
        
        next_date = self.data_loader.get_next_date(self.current_date)
        if not next_date:
            messagebox.showwarning("警告", "无法获取次日数据")
            return
        next_data = self.data_loader.get_stock_data_on_date(self.current_stock, next_date)
        if not next_data:
            messagebox.showwarning("警告", "次日数据缺失")
            return
            
        price = next_data['open']
        success = self.account.sell(next_date, self.current_stock, quantity, price)
        
        if success:
            self.trade_status_label.config(text=f"✓ 卖出: {quantity}股 @ {price:.2f}", foreground="green")
            self._update_account_display()
        else:
            self.trade_status_label.config(text="✗ 持仓不足", foreground="red")
    
    def _show_performance(self):
        PerformanceWindow(self.root, self.account)
    
    def _show_about(self):
        messagebox.showinfo("关于", "股票交易模拟器 v2.0 (Pro)\n包含历史回测与蒙特卡洛模拟挑战\n数据范围: 2012-2025")
    
    def _save_game(self):
        if not self.available_dates: return
        game_state = {
            'version': '2.0',
            'current_date': self.current_date,
            'watched_stocks': self.watched_stocks,
            'pinned_stocks': self.pinned_stocks,
            'current_stock': self.current_stock,
            'account': self.account.to_dict()
        }
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(game_state, f, indent=4)
                messagebox.showinfo("成功", f"存档已保存: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", str(e))

    def _load_game(self) -> bool:
        file_path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not file_path: return False
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            loaded_date = state.get('current_date')
            if loaded_date not in self.available_dates:
                 if loaded_date < self.available_dates[0] or loaded_date > self.available_dates[-1]:
                     messagebox.showerror("错误", "存档日期超出数据范围")
                     return False

            self.current_date = loaded_date
            self.current_date_idx = self.available_dates.index(self.current_date)
            self.watched_stocks = state.get('watched_stocks', [])
            self.pinned_stocks = state.get('pinned_stocks', [])
            self.current_stock = state.get('current_stock')
            self.account = Account.from_dict(state['account'])
            
            self.date_label.config(text=self.current_date)
            self._update_market_bar()
            self._update_chart()
            self._update_metrics()
            self._update_account_display()
            self._refresh_stock_list()
            messagebox.showinfo("成功", "存档读取成功")
            return True
        except Exception as e:
            messagebox.showerror("错误", str(e))
            return False
    
    def _update_trade_estimate(self, *args):
        if not self.current_stock:
            self.trade_price_label.config(text="请选股")
            self.trade_amount_label.config(text="--")
            return
        
        data = self.data_loader.get_stock_data_on_date(self.current_stock, self.current_date)
        price = data['close'] if data else 0.0
        self.trade_price_label.config(text=f"¥{price:.2f}" if data else "无数据")
        
        try:
            qty = int(self.quantity_var.get())
            if price > 0:
                self.trade_amount_label.config(text=f"¥{price*qty:,.2f}")
            else:
                self.trade_amount_label.config(text="--")
        except:
            self.trade_amount_label.config(text="--")

    def run(self):
        self.root.mainloop()

def main():
    # 高分屏支持
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except: pass
        
    app = StockTradingGame()
    app.run()

if __name__ == "__main__":
    main()