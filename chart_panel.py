"""
Chart Panel for Stock Trading Game
Displays candlestick charts with technical indicators including Z_CGO, TFO and Trade Markers
With Crosshair Cursor Support
"""
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import pandas as pd
import config

# Configure matplotlib to use Chinese fonts
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False 


class ChartPanel:
    """Chart panel with candlestick and indicators"""
    
    def __init__(self, parent):
        """Initialize chart panel"""
        self.parent = parent
        self.frame = ttk.Frame(parent)
        self.current_data = None
        self.current_trades = [] 
        self.indicator_vars = {}
        
        # --- 十字光标相关变量 ---
        self.cursor_lines = [] # 存储垂直线和水平线
        self.info_text = None  # 左上角信息文本
        # ---------------------
        
        # Create UI
        self._create_widgets()
    
    def _create_widgets(self):
        """Create chart widgets"""
        # Control panel
        control_frame = ttk.Frame(self.frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="技术指标:").pack(side=tk.LEFT, padx=5)
        
        # Indicator checkboxes
        indicators = [
            ('MA', 'ma_5'),
            ('MACD', 'macd'),
            ('RSI', 'rsi'),
            ('KDJ', 'kdj'),
            ('BOLL', 'boll'),
            ('Z_CGO', 'z_cgo'),
            ('TFO', 'tfo')
        ]
        
        for label, key in indicators:
            default_val = config.DEFAULT_INDICATORS.get(key, False)
            var = tk.BooleanVar(value=default_val)
            self.indicator_vars[key] = var
            cb = ttk.Checkbutton(
                control_frame,
                text=label,
                variable=var,
                command=self._on_indicator_change
            )
            cb.pack(side=tk.LEFT, padx=2)
        
        # Chart area
        chart_container = ttk.Frame(self.frame)
        chart_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # 设置 DPI=100 适配高分屏
        self.figure = Figure(figsize=(10, 6), dpi=100) 
        self.canvas = FigureCanvasTkAgg(self.figure, chart_container)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # --- 绑定鼠标移动事件 (十字光标) ---
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        # --------------------------------
        
        # Add Matplotlib Navigation Toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, chart_container)
        toolbar.update()
    
    def get_frame(self):
        return self.frame
    
    def _on_indicator_change(self):
        if self.current_data is not None:
            self.update_chart(self.current_data, self.current_trades)
    
    # --- 新增：鼠标移动处理函数 ---
    def _on_mouse_move(self, event):
        """Handle mouse movement for crosshair"""
        if not event.inaxes or self.current_data is None or self.current_data.empty:
            return

        # 获取鼠标位置
        x, y = event.xdata, event.ydata
        
        # 1. 绘制/更新十字线
        # 如果是第一次，或者图表被清空过(lines为空)，则重新创建
        if not self.cursor_lines:
            # 在所有子图中创建垂直线
            for ax in self.figure.axes:
                v_line = ax.axvline(x, color='gray', linestyle='--', linewidth=0.8, alpha=0.8)
                self.cursor_lines.append(v_line)
            # 在当前子图中创建水平线 (只显示当前鼠标所在的那个图)
            self.h_line = event.inaxes.axhline(y, color='gray', linestyle='--', linewidth=0.8, alpha=0.8)
            self.cursor_lines.append(self.h_line)
        else:
            # 更新垂直线位置 (同步移动所有子图的垂直线)
            # cursor_lines 里前 N 个是垂直线，最后一个是水平线
            for line in self.cursor_lines[:-1]:
                line.set_xdata([x, x])
            
            # 更新水平线位置 (并确保它在当前 axes)
            # 如果跨越了子图，这里简单处理只更新 Y，如果要完美效果需要移除重绘，这里为了性能简化处理
            self.cursor_lines[-1].set_ydata([y, y])
            
            # 如果水平线不在当前 axes，移除并重建 (可选优化，防止水平线乱跑)
            if self.cursor_lines[-1].axes != event.inaxes:
                self.cursor_lines[-1].remove()
                self.cursor_lines[-1] = event.inaxes.axhline(y, color='gray', linestyle='--', linewidth=0.8, alpha=0.8)

        # 2. 显示左上角数值 (HUD)
        idx = int(round(x))
        if 0 <= idx < len(self.current_data):
            row = self.current_data.iloc[idx]
            
            # 尝试格式化日期
            date_val = row['date']
            try:
                date_str = pd.to_datetime(date_val).strftime('%Y-%m-%d')
            except:
                date_str = str(date_val).split(' ')[0]
            
            # 组装基础信息
            info = f"日期: {date_str}\n开: {row['open']:.2f}\n高: {row['high']:.2f}\n低: {row['low']:.2f}\n收: {row['close']:.2f}"
            
            # 组装指标信息 (如果存在)
            if 'ma_5' in row: info += f"\nMA5: {row['ma_5']:.2f}"
            if 'z_cgo' in row: info += f"\nZ_CGO: {row['z_cgo']:.2f}"
            if 'tfo' in row: info += f"\nTFO: {row['tfo']:.2f}"
            
            # 绘制文本框
            main_ax = self.figure.axes[0] # 永远在主图显示
            if self.info_text is None:
                self.info_text = main_ax.text(0.99, 0.99, '', transform=main_ax.transAxes, 
                                            va='top', ha='right', fontsize=9, 
                                            bbox=dict(boxstyle='round', facecolor='white', alpha=0.7, edgecolor='gray'))
            
            self.info_text.set_text(info)

        # 使用 draw_idle 优化性能 (不会每次移动都重绘，而是空闲时重绘)
        self.canvas.draw_idle()
    # ---------------------------

    def _format_date(self, x, pos=None):
        if self.current_data is None or self.current_data.empty:
            return ''
        idx = int(x)
        if 0 <= idx < len(self.current_data):
            date_val = self.current_data.iloc[idx]['date']
            try:
                return pd.to_datetime(date_val).strftime('%Y-%m-%d')
            except:
                return str(date_val).split(' ')[0]
        return ''
    
    def update_chart(self, data: pd.DataFrame, trades: list = None):
        """Update chart with new data"""
        self.current_data = data
        self.current_trades = trades if trades is not None else []
        
        # 重置光标对象，防止残留
        self.cursor_lines = []
        self.info_text = None
        
        self.figure.clear()
        
        if data.empty:
            return
        
        # Determine active subplots
        active_subplots = []
        if self.indicator_vars['macd'].get(): active_subplots.append('macd')
        if self.indicator_vars['rsi'].get(): active_subplots.append('rsi')
        if self.indicator_vars['kdj'].get(): active_subplots.append('kdj')
        if self.indicator_vars['z_cgo'].get(): active_subplots.append('z_cgo')
        if self.indicator_vars['tfo'].get(): active_subplots.append('tfo')
        
        # Calculate Layout
        num_rows = 2 + len(active_subplots)
        height_ratios = [3, 1] + [1] * len(active_subplots)
        
        gs = gridspec.GridSpec(num_rows, 1, height_ratios=height_ratios, figure=self.figure)
        
        # 1. Price (Main)
        ax_price = self.figure.add_subplot(gs[0])
        self._plot_candlestick(ax_price, data)
        plt.setp(ax_price.get_xticklabels(), visible=False)
        
        # 2. Volume
        ax_vol = self.figure.add_subplot(gs[1], sharex=ax_price)
        self._plot_volume(ax_vol, data)
        
        last_ax = ax_vol
        if active_subplots:
            plt.setp(ax_vol.get_xticklabels(), visible=False)
        
        # 3. Indicators
        for i, ind in enumerate(active_subplots):
            ax_ind = self.figure.add_subplot(gs[2+i], sharex=ax_price)
            
            if ind == 'macd': self._plot_macd(ax_ind, data)
            elif ind == 'rsi': self._plot_rsi(ax_ind, data)
            elif ind == 'kdj': self._plot_kdj(ax_ind, data)
            elif ind == 'z_cgo': self._plot_z_cgo(ax_ind, data)
            elif ind == 'tfo': self._plot_tfo(ax_ind, data)
            
            if i < len(active_subplots) - 1:
                plt.setp(ax_ind.get_xticklabels(), visible=False)
            
            last_ax = ax_ind
        
        # Configure X-Axis
        self._configure_xaxis(last_ax, len(data))
        
        # Set View Window
        data_len = len(data)
        window_size = config.CHART_WINDOW_DAYS
        if data_len > window_size:
            ax_price.set_xlim(data_len - window_size - 0.5, data_len - 0.5)
        else:
            ax_price.set_xlim(-0.5, max(window_size, data_len) - 0.5)
            
        self.figure.tight_layout()
        self.figure.subplots_adjust(hspace=0.05)
        self.canvas.draw()

    def _configure_xaxis(self, ax, data_len):
        ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=8, integer=True))
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(self._format_date))
        plt.setp(ax.get_xticklabels(), rotation=15, ha='right')

    def _plot_candlestick(self, ax, data: pd.DataFrame):
        """Plot candlestick with trade markers"""
        x_range = range(len(data))
        
        # 绘制网格线
        ax.grid(True, linestyle='--', alpha=0.4, color='#d9d9d9')
        
        for idx, (_, row) in enumerate(data.iterrows()):
            # --- 修改开始：更精准的颜色判断逻辑 ---
            open_p = row['open']
            close_p = row['close']
            
            if close_p > open_p:
                # 收盘 > 开盘：绝对涨 (红)
                color = config.COLOR_RISE
            elif close_p < open_p:
                # 收盘 < 开盘：绝对跌 (绿)
                color = config.COLOR_FALL
            else:
                # 收盘 == 开盘 (十字星或一字板)
                # 这时需要看涨跌幅：如果相对昨天是跌的，给绿色；否则给红色
                pct = 0.0
                if 'pctChg' in row: pct = row['pctChg']
                elif 'pct_chg' in row: pct = row['pct_chg']
                
                if pct < 0:
                    color = config.COLOR_FALL
                else:
                    color = config.COLOR_RISE
            # --- 修改结束 ---
            
            ax.plot([idx, idx], [row['low'], row['high']], color=color, linewidth=0.5)
            
            body_height = abs(close_p - open_p)
            body_bottom = min(open_p, close_p)
            
            # 视觉优化：如果高度为0（一字板），设一个极小值确保能看到一条横线
            if body_height == 0: 
                body_height = 0.005 # 稍微调细一点，看起来更精致
            
            rect = plt.Rectangle(
                (idx - config.CANDLESTICK_WIDTH/2, body_bottom),
                config.CANDLESTICK_WIDTH,
                body_height,
                facecolor=color,
                edgecolor=color
            )
            ax.add_patch(rect)
            
        if self.indicator_vars['ma_5'].get():
            if 'ma_5' in data.columns: ax.plot(x_range, data['ma_5'], label='MA5', linewidth=1)
            if 'ma_20' in data.columns: ax.plot(x_range, data['ma_20'], label='MA20', linewidth=1)
        
        if self.indicator_vars['boll'].get() and 'boll_upper' in data.columns:
             ax.plot(x_range, data['boll_upper'], linewidth=0.8, alpha=0.5, linestyle='--')
             ax.plot(x_range, data['boll_lower'], linewidth=0.8, alpha=0.5, linestyle='--')
             ax.fill_between(x_range, data['boll_upper'], data['boll_lower'], alpha=0.1)
        
        # 绘制买卖点
        if self.current_trades:
            date_to_idx = {}
            for i, d in enumerate(data['date']):
                d_str = str(d).split(' ')[0]
                date_to_idx[d_str] = i
            
            for trade in self.current_trades:
                t_date = str(trade.date).split(' ')[0]
                if t_date in date_to_idx:
                    idx = date_to_idx[t_date]
                    if trade.action == 'BUY':
                        low_price = data.iloc[idx]['low']
                        ax.annotate('B', xy=(idx, low_price), xytext=(idx, low_price * 0.98),
                                    arrowprops=dict(facecolor=config.COLOR_RISE, shrink=0.05, alpha=0.8, width=2, headwidth=6),
                                    ha='center', va='top', fontsize=8, color=config.COLOR_RISE, fontweight='bold')
                    elif trade.action == 'SELL':
                        high_price = data.iloc[idx]['high']
                        ax.annotate('S', xy=(idx, high_price), xytext=(idx, high_price * 1.02),
                                    arrowprops=dict(facecolor=config.COLOR_FALL, shrink=0.05, alpha=0.8, width=2, headwidth=6),
                                    ha='center', va='bottom', fontsize=8, color=config.COLOR_FALL, fontweight='bold')
        
        ax.set_ylabel('价格')
        ax.legend(loc='upper left', fontsize=7)

    def _plot_volume(self, ax, data: pd.DataFrame):
        if 'vol' in data.columns: vol_col = 'vol'
        elif 'volume' in data.columns: vol_col = 'volume'
        else: return
        
        x = range(len(data))
        colors = [config.COLOR_RISE if r['close'] >= r['open'] else config.COLOR_FALL for _, r in data.iterrows()]
        ax.bar(x, data[vol_col], color=colors, width=config.CANDLESTICK_WIDTH)
        ax.set_ylabel('成交量')
        ax.grid(True, linestyle='--', alpha=0.4, color='#d9d9d9')

    def _plot_macd(self, ax, data):
        if 'dif' not in data.columns: return
        x = range(len(data))
        ax.plot(x, data['dif'], label='DIF', linewidth=1)
        ax.plot(x, data['dea'], label='DEA', linewidth=1)
        colors = [config.COLOR_RISE if v >= 0 else config.COLOR_FALL for v in data['macd']]
        ax.bar(x, data['macd'], color=colors, alpha=0.5, label='MACD')
        ax.axhline(0, color='black', linewidth=0.5)
        ax.set_ylabel('MACD')
        ax.legend(loc='upper left', fontsize=7)
        ax.grid(True, linestyle='--', alpha=0.4, color='#d9d9d9')

    def _plot_rsi(self, ax, data):
        x = range(len(data))
        if 'rsi_6' in data.columns: ax.plot(x, data['rsi_6'], label='RSI6', linewidth=1)
        if 'rsi_12' in data.columns: ax.plot(x, data['rsi_12'], label='RSI12', linewidth=1)
        ax.axhline(70, color='red', linestyle='--', linewidth=0.5)
        ax.axhline(30, color='green', linestyle='--', linewidth=0.5)
        ax.set_ylabel('RSI')
        ax.legend(loc='upper left', fontsize=7)
        ax.grid(True, linestyle='--', alpha=0.4, color='#d9d9d9')

    def _plot_kdj(self, ax, data):
        if not all(col in data.columns for col in ['kdj_k', 'kdj_d', 'kdj_j']): return
        x = range(len(data))
        ax.plot(x, data['kdj_k'], label='K', linewidth=1)
        ax.plot(x, data['kdj_d'], label='D', linewidth=1)
        ax.plot(x, data['kdj_j'], label='J', linewidth=1)
        ax.set_ylabel('KDJ')
        ax.legend(loc='upper left', fontsize=7)
        ax.grid(True, linestyle='--', alpha=0.4, color='#d9d9d9')

    def _plot_z_cgo(self, ax, data: pd.DataFrame):
        if 'z_cgo' not in data.columns:
            ax.text(0.5, 0.5, 'Z_CGO数据缺失', ha='center')
            return
        x = range(len(data))
        vals = data['z_cgo'].fillna(0)
        colors = [config.COLOR_RISE if v >= 0 else config.COLOR_FALL for v in vals]
        ax.bar(x, vals, color=colors, alpha=0.8, width=config.CANDLESTICK_WIDTH)
        ax.axhline(y=2.0, color='gray', linestyle='--', linewidth=0.8)
        ax.axhline(y=-2.0, color='gray', linestyle='--', linewidth=0.8)
        ax.axhline(y=0, color='black', linewidth=0.5)
        ax.set_ylabel('Z_CGO')
        ax.grid(True, linestyle='--', alpha=0.4, color='#d9d9d9')

    def _plot_tfo(self, ax, data: pd.DataFrame):
        if 'tfo' not in data.columns:
            ax.text(0.5, 0.5, 'TFO数据缺失', ha='center')
            return
        x = range(len(data))
        ax.plot(x, data['tfo'], label='TFO', color='#9b59b6', linewidth=1.2)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax.fill_between(x, data['tfo'], 0, where=(data['tfo'] >= 0), facecolor=config.COLOR_RISE, alpha=0.1)
        ax.fill_between(x, data['tfo'], 0, where=(data['tfo'] < 0), facecolor=config.COLOR_FALL, alpha=0.1)
        ax.set_ylabel('TFO')
        ax.legend(loc='upper left', fontsize=7)
        ax.grid(True, linestyle='--', alpha=0.4, color='#d9d9d9')