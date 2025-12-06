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
import numpy as np

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
        self.figure = Figure(figsize=(10, 6), dpi=100, facecolor='#fbfbfb') 
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
        """Handle mouse movement for crosshair (性能优化版)"""
        if not event.inaxes or self.current_data is None or self.current_data.empty:
            return

        # 获取整数索引，避免浮点数造成的微小抖动导致的无效重绘
        x, y = event.xdata, event.ydata
        idx = int(round(x))
        
        # 1. 只有当鼠标跨越到新的 K 线时，才更新文本 (大幅减少文本渲染开销)
        # 记录上一次的索引
        if not hasattr(self, '_last_idx'): self._last_idx = -1
        
        update_text = (idx != self._last_idx)
        self._last_idx = idx

        # ... (中间代码保持不变：更新 cursor_lines 的 set_xdata/set_ydata) ...
        # 注意：这里粘贴你原有的 cursor_lines 更新逻辑
        if not self.cursor_lines:
             # 初始化 cursor_lines 代码...
             for ax in self.figure.axes:
                v_line = ax.axvline(x, color='gray', linestyle='--', linewidth=0.8, alpha=0.8)
                self.cursor_lines.append(v_line)
             self.h_line = event.inaxes.axhline(y, color='gray', linestyle='--', linewidth=0.8, alpha=0.8)
             self.cursor_lines.append(self.h_line)
        else:
             # 更新位置代码...
             for line in self.cursor_lines[:-1]: line.set_xdata([x, x])
             self.cursor_lines[-1].set_ydata([y, y])
             # 确保水平线在当前 axes
             if self.cursor_lines[-1].axes != event.inaxes:
                 self.cursor_lines[-1].remove()
                 self.cursor_lines[-1] = event.inaxes.axhline(y, color='gray', linestyle='--', linewidth=0.8, alpha=0.8)

        # 2. 条件更新文本
        if update_text:
            if 0 <= idx < len(self.current_data):
                row = self.current_data.iloc[idx]
                # ... (数据提取逻辑保持不变) ...
                
                # 简化：直接构造字符串
                date_str = str(row['date']).split(' ')[0]
                info = f"[{date_str}]\nOpen:{row['open']:.2f} High:{row['high']:.2f}\nLow:{row['low']:.2f} Close:{row['close']:.2f}"
                
                # 指标信息按需添加
                if 'ma_5' in row: info += f"\nMA5:{row['ma_5']:.2f}"
                
                # 获取主轴并更新
                main_ax = self.figure.axes[0]
                if self.info_text is None:
                    # 优化 bbox 样式，减少透明度计算
                    self.info_text = main_ax.text(
                        0.99, 0.99, '', transform=main_ax.transAxes, 
                        va='top', ha='right', fontsize=9, fontfamily='Arial',
                        bbox=dict(boxstyle='square,pad=0.3', facecolor='#f0f0f0', alpha=0.9, edgecolor='none')
                    )
                self.info_text.set_text(info)

        # 3. 关键：使用 blit=True 的思想 (TkAgg 不容易直接用，但可以用 update 代替 draw)
        # 如果你实施了第一步的 Vectorization，这里的 draw_idle 应该已经足够快了(<20ms)。
        self.canvas.draw_idle()

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
    
    def _style_axis(self, ax):
        """应用专业图表样式"""
        # 1. 设置背景 (透明或淡灰)
        ax.set_facecolor('white') 
        
        # 2. 网格线：极淡、虚线、置于底层
        ax.grid(True, linestyle='--', linewidth=0.6, color='#e0e0e0', alpha=0.6)
        ax.set_axisbelow(True) # 让网格线在K线后面

        # 3. 去掉顶部和右侧的边框 (Spines)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # 4. 左侧和底部边框颜色淡化
        ax.spines['left'].set_color('#cccccc')
        ax.spines['bottom'].set_color('#cccccc')
        
        # 5. 刻度文字颜色
        ax.tick_params(axis='x', colors='#666666', labelsize=8)
        ax.tick_params(axis='y', colors='#666666', labelsize=8)
    
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
        """
        [优化版] 使用向量化操作绘制K线，替代低效的循环 add_patch
        速度提升约 20x - 50x
        """
        if data.empty:
            return

        # 1. 准备数据
        # 确保索引是对齐的
        data = data.reset_index(drop=True)
        x_range = data.index.values
        
        opens = data['open'].values
        closes = data['close'].values
        highs = data['high'].values
        lows = data['low'].values
        
        # 2. 计算涨跌掩码 (Masks)
        # up: 收盘 >= 开盘
        up_mask = closes >= opens
        down_mask = ~up_mask
        
        # 3. 批量绘制影线 (Wicks) - 使用 vlines 极快
        # 涨的影线颜色
        ax.vlines(x_range[up_mask], lows[up_mask], highs[up_mask], 
                 color=config.COLOR_RISE, linewidth=0.8, alpha=0.9)
        # 跌的影线颜色
        ax.vlines(x_range[down_mask], lows[down_mask], highs[down_mask], 
                 color=config.COLOR_FALL, linewidth=0.8, alpha=0.9)
        
        # 4. 批量绘制实体 (Bodies) - 使用 bar 极快
        # 计算实体高度和底部位置
        # 涨：高度 = close - open, 底部 = open
        # 跌：高度 = open - close, 底部 = close
        heights = np.abs(closes - opens)
        bottoms = np.minimum(opens, closes)
        
        # 处理一字板（高度为0的情况），给一个极小高度以便能看见
        heights[heights == 0] = 0.005  # 视觉修正
        
        # 一次性绘制所有上涨的实体
        if np.any(up_mask):
            ax.bar(x_range[up_mask], heights[up_mask], bottom=bottoms[up_mask],
                  color=config.COLOR_RISE, width=config.CANDLESTICK_WIDTH, align='center')
            
        # 一次性绘制所有下跌的实体
        if np.any(down_mask):
            ax.bar(x_range[down_mask], heights[down_mask], bottom=bottoms[down_mask],
                  color=config.COLOR_FALL, width=config.CANDLESTICK_WIDTH, align='center')

        # 5. 绘制均线 (保持不变，plot 本身就是向量化的)
        if self.indicator_vars['ma_5'].get():
            if 'ma_5' in data.columns: ax.plot(x_range, data['ma_5'], label='MA5', linewidth=1)
            if 'ma_20' in data.columns: ax.plot(x_range, data['ma_20'], label='MA20', linewidth=1)
        
        if self.indicator_vars['boll'].get() and 'boll_upper' in data.columns:
             ax.plot(x_range, data['boll_upper'], linewidth=0.8, alpha=0.5, linestyle='--', color='#888')
             ax.plot(x_range, data['boll_lower'], linewidth=0.8, alpha=0.5, linestyle='--', color='#888')
             ax.fill_between(x_range, data['boll_upper'], data['boll_lower'], color='gray', alpha=0.1)
        
        # 6. 绘制买卖点 (标注数量通常不多，循环可以接受，或者使用 scatter 优化)
        if self.current_trades:
            self._plot_trade_markers(ax, data)
            
        # 7. 样式设置
        self._style_axis(ax)
        ax.set_ylabel('价格', color='#666666')
        ax.legend(loc='upper left', fontsize=8, frameon=False, labelcolor='#666666')
    
    def _plot_trade_markers(self, ax, data):
        """优化买卖点绘制"""
        # 创建日期到索引的快速映射
        date_map = {str(d).split(' ')[0]: i for i, d in enumerate(data['date'])}
        
        for trade in self.current_trades:
            t_date = str(trade.date).split(' ')[0]
            if t_date not in date_map:
                continue
                
            idx = date_map[t_date]
            
            if trade.action == 'BUY':
                low_price = data.iloc[idx]['low']
                # 使用 annotate 性能尚可，因为交易点通常很少
                ax.annotate('B', xy=(idx, low_price), xytext=(idx, low_price * 0.98),
                            arrowprops=dict(facecolor=config.COLOR_RISE, shrink=0.05, 
                                          alpha=0.8, width=2, headwidth=6),
                            ha='center', va='top', fontsize=8, 
                            color=config.COLOR_RISE, fontweight='bold')
            elif trade.action == 'SELL':
                high_price = data.iloc[idx]['high']
                ax.annotate('S', xy=(idx, high_price), xytext=(idx, high_price * 1.02),
                            arrowprops=dict(facecolor=config.COLOR_FALL, shrink=0.05, 
                                          alpha=0.8, width=2, headwidth=6),
                            ha='center', va='bottom', fontsize=8, 
                            color=config.COLOR_FALL, fontweight='bold')

    def _plot_volume(self, ax, data: pd.DataFrame):
        if 'vol' in data.columns: vol_col = 'vol'
        elif 'volume' in data.columns: vol_col = 'volume'
        else: return
        
        x = range(len(data))
        colors = [config.COLOR_RISE if r['close'] >= r['open'] else config.COLOR_FALL for _, r in data.iterrows()]
        ax.bar(x, data[vol_col], color=colors, width=config.CANDLESTICK_WIDTH, alpha=0.6)
        
        self._style_axis(ax)
        ax.set_ylabel('成交量', color='#666666')

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