"""
Data Loader for Stock Trading Game
Powered by DuckDB for high-performance zero-copy data access
"""
import os
import pandas as pd
import numpy as np
import duckdb
from typing import List, Optional, Dict
import config
import random
# 引入我们刚才写的计算引擎
import tech_calc 

class DataLoader:
    """
    Load and manage stock market data using DuckDB.
    Instead of loading 18M rows into RAM, we query the Parquet file directly using SQL.
    """
    
    def __init__(self, data_dir: str = None):
        """Initialize DuckDB connection"""
        self.data_dir = data_dir or config.DATA_DIR
        self.file_path = os.path.join(self.data_dir, config.DATA_FILENAME)
        
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Data file not found: {self.file_path}")
            
        # 初始化 DuckDB 连接 (内存模式)
        self.con = duckdb.connect(database=':memory:')
        
        # 注册 Parquet 文件为虚拟视图
        # read_parquet 是 lazy 的，不会立即读取数据，瞬间完成
        print(f"正在连接数据库: {self.file_path} ...")
        self.con.execute(f"""
            CREATE OR REPLACE VIEW stock_data AS 
            SELECT * FROM read_parquet('{self.file_path}')
        """)
        
        self._available_dates: List[str] = []
        self._load_metadata()
        # --- 新增：加载股票名称 ---
        self.stock_names = {}
        self._load_stock_names()
        # --- 新增：模拟模式缓存 ---
        self.sim_mode = False       # 模式开关
        self.sim_data_cache = {}    # 缓存生成的模拟数据 {code: df}
        self.sim_dates = []         # 模拟模式下的日期列表
        # ------------------------

    def _load_stock_names(self):
        """Load stock names from csv"""
        name_file = os.path.join(self.data_dir, "stock_list.csv")
        if not os.path.exists(name_file):
            print("Warning: stock_list.csv not found.")
            return

        try:
            # 读取 CSV (code, code_name)
            # 假设 CSV 包含表头，如果没有表头需要调整 header 参数
            df = pd.read_csv(name_file, dtype=str)
            
            for _, row in df.iterrows():
                raw_code = row['code']
                name = row['code_name']
                
                # 处理前缀：sh.000001 -> 000001
                if '.' in raw_code:
                    clean_code = raw_code.split('.')[1]
                else:
                    clean_code = raw_code
                
                self.stock_names[clean_code] = name
            print(f"已加载 {len(self.stock_names)} 个股票名称。")
        except Exception as e:
            print(f"加载股票名称失败: {e}")

    def get_stock_name(self, code: str) -> str:
        """Get stock name by code"""
        return self.stock_names.get(code, "未知")
    
    def _load_metadata(self):
        """Load minimal metadata (dates) to memory"""
        print("正在索引交易日期...")
        # 查询所有唯一日期。DuckDB 极快，因为它只需要读取 Parquet 的某一列。
        # 假设 date 列在 Parquet 中是 Timestamp 或 String
        # 我们统一转为 String (YYYY-MM-DD)
        
        # 注意：使用 strftime 确保格式统一
        query = """
        SELECT DISTINCT strftime(date, '%Y-%m-%d') as date_str 
        FROM stock_data 
        ORDER BY date_str ASC
        """
        df = self.con.execute(query).df()
        self._available_dates = df['date_str'].tolist()
        
        print(f"DuckDB 就绪: 索引了 {len(self._available_dates)} 个交易日。")

    def get_available_dates(self) -> List[str]:
        if self.sim_mode:
            return self.sim_dates.copy() # 返回模拟日期
        return self._available_dates.copy() # 返回历史日期
    
    def get_daily_snapshot(self, date: str, codes: List[str] = None) -> pd.DataFrame:
        if self.sim_mode:
            # 模拟模式下，daily snapshot 比较慢，因为要循环查缓存
            # 优化：只对 watched_stocks 生成/查询
            results = []
            target_codes = codes if codes else []
            
            for c in target_codes:
                if c not in self.sim_data_cache:
                    self._generate_single_stock_sim(c)
                
                df = self.sim_data_cache[c]
                row = df[df['date'] == date]
                if not row.empty:
                    # 构造 snapshot 需要的字段
                    r = row.iloc[0]
                    # 兼容 pct 列名
                    p = r.get('pctChg', r.get('pct_chg', 0.0))
                    results.append({'code': c, 'close': r['close'], 'pctChg': p})
            
            return pd.DataFrame(results)
        else:
            # 历史模式 (原逻辑)
            base_query = "SELECT * FROM stock_data WHERE strftime(date, '%Y-%m-%d') = ?"
            params = [date]
            if codes is not None and len(codes) > 0:
                placeholders = ','.join(['?'] * len(codes))
                query = f"{base_query} AND code IN ({placeholders})"
                params.extend(codes)
            else:
                query = base_query
            return self.con.execute(query, params).df()

    def get_date_range(self) -> tuple:
        if not self._available_dates:
            return (None, None)
        return (self._available_dates[0], self._available_dates[-1])
    
    def get_next_date(self, current_date: str) -> Optional[str]:
        try:
            # 列表查找很快，不需要 SQL
            idx = self._available_dates.index(current_date)
            if idx < len(self._available_dates) - 1:
                return self._available_dates[idx + 1]
        except ValueError:
            pass
        return None
    
    def get_prev_date(self, current_date: str) -> Optional[str]:
        try:
            idx = self._available_dates.index(current_date)
            if idx > 0:
                return self._available_dates[idx - 1]
        except ValueError:
            pass
        return None
    
    def get_stock_list(self, date: str) -> List[str]:
        """Get list of stock codes available on given date"""
        query = "SELECT code FROM stock_data WHERE strftime(date, '%Y-%m-%d') = ?"
        df = self.con.execute(query, [date]).df()
        return df['code'].tolist()
    
    def get_stock_data(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get stock data (supports both History and Sim modes)"""
        
        if self.sim_mode:
            # 模拟模式：从缓存中切片
            if code not in self.sim_data_cache:
                # 如果还没生成，就现场生成 (第一次点击某股票时)
                self._generate_single_stock_sim(code)
            
            df = self.sim_data_cache[code]
            # 字符串比较日期
            mask = (df['date'] >= start_date) & (df['date'] <= end_date)
            return df.loc[mask].copy()
            
        else:
            # 历史模式：查数据库 (原逻辑)
            query = """
                SELECT * 
                FROM stock_data 
                WHERE code = ? 
                  AND strftime(date, '%Y-%m-%d') >= ? 
                  AND strftime(date, '%Y-%m-%d') <= ?
                ORDER BY date ASC
            """
            return self.con.execute(query, [code, start_date, end_date]).df()
        
    def get_stock_data_on_date(self, code: str, date: str) -> Optional[Dict]:
        if self.sim_mode:
            if code not in self.sim_data_cache:
                self._generate_single_stock_sim(code)
            df = self.sim_data_cache[code]
            row = df[df['date'] == date]
            if row.empty: return None
            return row.iloc[0].to_dict()
        else:
            # 原逻辑
            query = "SELECT * FROM stock_data WHERE code = ? AND strftime(date, '%Y-%m-%d') = ? LIMIT 1"
            df = self.con.execute(query, [code, date]).df()
            if df.empty: return None
            return df.iloc[0].to_dict()
    
    # --- 新增：切换模式 ---
    def set_mode(self, mode: str):
        """mode: 'history' or 'simulation'"""
        if mode == 'simulation':
            self.sim_mode = True
            # 生成一套通用的模拟日期轴 (比如 500 天)
            # 使用伪造日期格式，方便排序
            self.sim_dates = [f"Sim-Day-{i:04d}" for i in range(1, 1001)] 
            self.sim_data_cache = {} # 清空缓存
        else:
            self.sim_mode = False
            self.sim_data_cache = {}

    # --- 新增：生成单只股票的蒙特卡洛数据 ---
    def _generate_single_stock_sim(self, code: str):
        """
        核心算法：分块自举 (Block Bootstrapping)
        1. 获取该股票所有历史数据
        2. 随机切分片段并拼接
        3. 平滑价格断层
        4. 重算指标
        """
        # 1. 获取所有历史源数据
        query = "SELECT * FROM stock_data WHERE code = ? ORDER BY date ASC"
        src_df = self.con.execute(query, [code]).df()
        
        if src_df.empty or len(src_df) < 100:
            # 数据太少，没法模拟，生成一个空结构或者报错
            self.sim_data_cache[code] = pd.DataFrame()
            return

        # 2. 拼接参数
        total_days = len(self.sim_dates)
        chunk_size = 60 # 每个片段 60 天 (约一个季度)
        chunks = []
        
        current_len = 0
        last_close = src_df.iloc[0]['close'] # 初始价格
        
        # 3. 循环拼接
        while current_len < total_days:
            # 随机选择一个起始点
            max_start = len(src_df) - chunk_size - 1
            if max_start < 0: max_start = 0
            start_idx = random.randint(0, max_start)
            
            # 取出一个切片
            chunk = src_df.iloc[start_idx : start_idx + chunk_size].copy()
            if chunk.empty: break
            
            # --- 价格缝合 (Price Stitching) ---
            # 计算缩放比例：让当前块的开盘价 = 上一块的收盘价
            chunk_open = chunk.iloc[0]['open']
            if chunk_open == 0: chunk_open = 1.0 # 防除零
            
            scale = last_close / chunk_open
            
            # 调整所有价格字段
            for col in ['open', 'high', 'low', 'close']:
                chunk[col] = chunk[col] * scale
            
            # 涨跌幅 pctChg 不需要调整，因为比例缩放后幅度不变
            # 成交量 vol 保持原样，或者也可以随机缩放，这里保持原样保留量价关系
            
            chunks.append(chunk)
            current_len += len(chunk)
            last_close = chunk.iloc[-1]['close'] # 更新锚点价格
        
        # 4. 合并
        sim_df = pd.concat(chunks, ignore_index=True)
        # 截取所需长度
        sim_df = sim_df.iloc[:total_days].copy()
        
        # 5. 覆盖日期
        sim_df['date'] = self.sim_dates[:len(sim_df)]
        
        # 6. 重算技术指标 (关键步骤)
        # 因为拼接后原本的 MA, MACD 都会断裂，必须重算
        sim_df = tech_calc.calculate_technical_factors(sim_df)
        
        # 存入缓存
        self.sim_data_cache[code] = sim_df
        print(f"已生成模拟数据: {code}, 长度 {len(sim_df)}")
    
    def get_random_stocks(self, date: str = None, n: int = 10, prefixes: List[str] = None) -> List[str]:
        """
        Get random n stocks alive on date, optionally filtered by prefixes.
        prefixes example: ['00', '60', '300']
        """
        # 如果 date 为 None 或者是模拟日期，就随机选一天真实日期来查代码
        if date is None or "Sim" in date:
            date = "2023-06-01" # 使用较新的日期以确保包含科创板等

        # 基础 SQL
        sql = "SELECT DISTINCT code FROM stock_data WHERE strftime(date, '%Y-%m-%d') = ?"
        params = [date]

        # --- 新增：构建前缀筛选条件 ---
        if prefixes:
            # 构造类似: AND (code LIKE '00%' OR code LIKE '60%' OR ...)
            # DuckDB 支持 LIKE 'prefix%' 语法
            conditions = [f"code LIKE '{p}%'" for p in prefixes]
            if conditions:
                sql += " AND (" + " OR ".join(conditions) + ")"
        # ---------------------------

        # 执行查询拿到所有符合条件的代码
        try:
            all_codes_df = self.con.execute(sql, params).df()
            all_codes = all_codes_df['code'].tolist()
        except Exception as e:
            print(f"Error getting stock list: {e}")
            return []
        
        # 随机抽取 n 个
        if not all_codes:
            return []
            
        if len(all_codes) <= n:
            return all_codes
            
        return random.sample(all_codes, n)
    
    def close(self):
        """Close connection"""
        self.con.close()