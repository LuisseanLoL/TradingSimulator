"""
Performance Window for Stock Trading Game
Display equity curve and trade log
"""
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
from game_engine import Account
from utils import format_currency, format_percentage, format_number

# Configure matplotlib to use Chinese fonts
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign display


class PerformanceWindow:
    """Window to display trading performance"""
    
    def __init__(self, parent, account: Account):
        """Initialize performance window"""
        self.account = account
        self.window = ttkb.Toplevel(parent)
        self.window.title("交易表现")
        
        # --- 修改开始：设置窗口最大化 ---
        # 设置一个基础大小
        self.window.geometry("1280x800")
        
        try:
            # Windows 系统最大化
            self.window.state('zoomed')
        except:
            try:
                # Linux / Mac 系统最大化
                self.window.attributes('-zoomed', True)
            except:
                # 兜底方案：全屏尺寸
                w = self.window.winfo_screenwidth()
                h = self.window.winfo_screenheight()
                self.window.geometry(f"{w}x{h}")
        # --- 修改结束 ---
        
        self._create_widgets()
        self.update_display()
    
    def _create_widgets(self):
        """Create window widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Summary statistics
        stats_frame = ttk.LabelFrame(main_frame, text="绩效统计", padding=10)
        stats_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
        
        self.stats_labels = {}
        stats = [
            ('total_equity', '总资产'),
            ('total_profit', '总盈亏'),
            ('total_profit_pct', '收益率'),
            ('num_trades', '交易次数'),
        ]
        
        for i, (key, label) in enumerate(stats):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(stats_frame, text=f"{label}:").grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            value_label = ttk.Label(stats_frame, text="--", font=('Arial', 10, 'bold'))
            value_label.grid(row=row, column=col+1, sticky=tk.W, padx=5, pady=2)
            self.stats_labels[key] = value_label
        
        # Notebook for charts and trade log
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Equity curve tab
        equity_frame = ttk.Frame(notebook)
        notebook.add(equity_frame, text="资产曲线")
        
        # --- 修改开始：增加 dpi 参数以支持高分屏 ---
        # 默认 dpi=100，如果在 4K 屏上觉得字太小，可以改为 120 或 150
        self.equity_figure = Figure(figsize=(8, 5), dpi=100) 
        # --- 修改结束 ---
        
        self.equity_canvas = FigureCanvasTkAgg(self.equity_figure, equity_frame)
        self.equity_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Trade log tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="交易日志")
        
        # Trade log table
        columns = ('日期', '股票', '操作', '数量', '价格', '手续费', '金额')
        self.trade_tree = ttk.Treeview(log_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.trade_tree.heading(col, text=col)
            if col in ['数量', '价格', '手续费', '金额']:
                self.trade_tree.column(col, width=100, anchor=tk.E)
            else:
                self.trade_tree.column(col, width=100, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.trade_tree.yview)
        self.trade_tree.configure(yscrollcommand=scrollbar.set)
        
        self.trade_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_display(self):
        """Update all displays with current data"""
        self._update_statistics()
        self._update_equity_curve()
        self._update_trade_log()
    
    def _update_statistics(self):
        """Update summary statistics"""
        self.stats_labels['total_equity'].config(text=format_currency(self.account.total_equity))
        self.stats_labels['total_profit'].config(text=format_currency(self.account.total_profit))
        self.stats_labels['total_profit_pct'].config(text=format_percentage(self.account.total_profit_pct))
        self.stats_labels['num_trades'].config(text=str(len(self.account.trade_log.trades)))
        
        # Color code profit/loss
        profit_color = 'red' if self.account.total_profit >= 0 else 'green'
        self.stats_labels['total_profit'].config(foreground=profit_color)
        self.stats_labels['total_profit_pct'].config(foreground=profit_color)
    
    def _update_equity_curve(self):
        """Update equity curve chart"""
        self.equity_figure.clear()
        
        equity_df = self.account.get_equity_curve()
        
        if equity_df.empty:
            ax = self.equity_figure.add_subplot(111)
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', fontsize=14)
            self.equity_canvas.draw()
            return
        
        ax = self.equity_figure.add_subplot(111)
        
        x = range(len(equity_df))
        ax.plot(x, equity_df['total_equity'], label='总资产', linewidth=2, color='#3498db')
        ax.axhline(y=self.account.initial_cash, color='gray', linestyle='--', linewidth=1, label='初始资金')
        
        ax.set_xlabel('交易日')
        ax.set_ylabel('资产 (元)')
        ax.set_title('资产曲线')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Set x-axis labels
        step = max(1, len(equity_df) // 10)
        ax.set_xticks(range(0, len(equity_df), step))
        ax.set_xticklabels([equity_df.iloc[i]['date'] if i < len(equity_df) else '' 
                           for i in range(0, len(equity_df), step)], rotation=45)
        
        self.equity_figure.tight_layout()
        self.equity_canvas.draw()
    
    def _update_trade_log(self):
        """Update trade log table"""
        # Clear existing items
        for item in self.trade_tree.get_children():
            self.trade_tree.delete(item)
        
        # Add trades
        trades = self.account.trade_log.get_trades()
        for trade in reversed(trades):  # Show most recent first
            values = (
                trade.date,
                trade.code,
                trade.action,
                trade.quantity,
                f"{trade.price:.2f}",
                f"{trade.commission:.2f}",
                f"{trade.total_amount:.2f}"
            )
            
            # Color code by action
            tag = 'buy' if trade.action == 'BUY' else 'sell'
            self.trade_tree.insert('', tk.END, values=values, tags=(tag,))
        
        # Configure tags
        self.trade_tree.tag_configure('buy', foreground='red')
        self.trade_tree.tag_configure('sell', foreground='green')
