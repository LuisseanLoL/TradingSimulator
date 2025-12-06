"""
tech_calc.py
用于在模拟模式下实时计算技术指标
"""
import pandas as pd
import pandas_ta as ta
import numpy as np
from numba import njit

# --- Numba 加速函数 (直接复用 data_convert.py 中的逻辑) ---
@njit
def _calc_reference_price_numba(close_arr, turn_arr):
    n = len(close_arr)
    rp = np.zeros(n)
    rp[0] = close_arr[0]
    for i in range(1, n):
        t = turn_arr[i]
        if t > 1.0: t = 1.0
        if t < 0.0: t = 0.0
        rp[i] = rp[i-1] * (1 - t) + close_arr[i] * t
    return rp

@njit
def _calc_super_smoother_numba(src, length):
    n = len(src)
    out = np.zeros(n)
    a1 = np.exp(-1.414 * 3.14159 / length)
    b1 = 2 * a1 * np.cos(1.414 * 180 / length * 3.14159 / 180)
    c2 = b1
    c3 = -a1 * a1
    c1 = 1 - c2 - c3
    out[0] = src[0]
    out[1] = src[1]
    for i in range(2, n):
        out[i] = c1 * (src[i] + src[i-1]) / 2 + c2 * out[i-1] + c3 * out[i-2]
    return out

def calculate_technical_factors(df):
    """
    为生成的模拟数据重新计算所有技术指标
    """
    # 避免 SettingWithCopyWarning
    df = df.copy()
    
    close = df['close']
    
    # 1. 均线系统
    for p in [5, 10, 20, 60]:
        df[f'ma_{p}'] = ta.sma(close, length=p)

    # 2. 布林带
    bb = ta.bbands(close, length=20, std=2)
    if bb is not None:
        df['boll_upper'] = bb.iloc[:, 2]
        df['boll_lower'] = bb.iloc[:, 0]
        
    # 3. MACD
    macd = ta.macd(close, fast=12, slow=26, signal=9)
    if macd is not None:
        df['dif'] = macd.iloc[:, 0]
        df['macd'] = macd.iloc[:, 1] * 2
        df['dea'] = macd.iloc[:, 2]

    # 4. RSI
    for r in [6, 12, 24]:
        df[f'rsi_{r}'] = ta.rsi(close, length=r)

    # 5. KDJ
    kdj = ta.kdj(df['high'], df['low'], close, length=9, signal=3)
    if kdj is not None:
        df['kdj_k'] = kdj.iloc[:, 0]
        df['kdj_d'] = kdj.iloc[:, 1]
        df['kdj_j'] = kdj.iloc[:, 2]
        
    # 6. Z_CGO
    if 'turn' in df.columns:
        # 处理换手率
        raw_turn = df['turn'].fillna(0).values
        # 简单归一化判断
        if np.nanmax(raw_turn) > 5.0:
            turn_normalized = raw_turn / 100.0
        else:
            turn_normalized = raw_turn
            
        rp_array = _calc_reference_price_numba(close.values, turn_normalized)
        
        safe_rp = np.where(rp_array == 0, np.nan, rp_array)
        cgo_series = (close - safe_rp) / safe_rp
        
        cgo_mean = pd.Series(cgo_series).rolling(window=20).mean()
        cgo_std = pd.Series(cgo_series).rolling(window=20).std()
        df['z_cgo'] = (cgo_series - cgo_mean) / cgo_std

    # 7. TFO
    ssf_array = _calc_super_smoother_numba(close.values, 20)
    safe_ssf = np.where(ssf_array == 0, np.nan, ssf_array)
    df['tfo'] = (close - safe_ssf) / safe_ssf * 100
    
    # 清理计算产生的 NaN (前几行)
    df.fillna(0, inplace=True)
    
    return df