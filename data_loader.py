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
        # --- 新增：模拟模式日期轴 ---
        self.sim_mode = False
        self.sim_data_cache = {}
        self.playable_sim_dates = [] # 仅包含 Sim-Day-xxxx
        self.full_sim_dates = []     # 包含 Warmup-xxxx 和 Sim-Day-xxxx

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
        """
        根据当前模式返回可用日期列表。
        模拟模式下返回包含预热期的完整列表。
        """
        if self.sim_mode:
            return self.full_sim_dates.copy() # [关键修改]
        return self._available_dates.copy()
    
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
        """Get stock data (supports both History and Sim modes with robust slicing)"""
        
        if self.sim_mode:
            # --- 模拟模式：从缓存中切片 ---
            if code not in self.sim_data_cache:
                # 按需生成 (兜底逻辑)
                self._generate_single_stock_sim(code)
            
            df = self.sim_data_cache.get(code)
            
            # --- [关键修复] ---
            # 如果 df 为空或 date 列不存在，直接返回空DF
            if df is None or df.empty or 'date' not in df.columns:
                return pd.DataFrame()
            
            # 1. 确保 'date' 列是索引，以便进行高效且准确的标签切片
            df_indexed = df.set_index('date', drop=False)
            
            # 2. 使用 .loc 进行切片
            try:
                # .loc[start:end] 会包含 start 和 end 两端
                sliced_df = df_indexed.loc[start_date:end_date]
                # 恢复索引，保持 DataFrame 结构与其他部分一致
                return sliced_df.reset_index(drop=True).copy()
            except KeyError:
                # 如果 start_date 或 end_date 不在索引中，会抛出 KeyError
                # 这种情况下返回空 DataFrame 是安全的
                return pd.DataFrame()
            # --------------------
            
        else:
            # 历史模式：查数据库 (原逻辑不变)
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
            # [关键修改] 创建两个日期列表
            warmup_dates = [f"Warmup-{i:04d}" for i in range(1, config.SIM_WARMUP_DAYS + 1)]
            self.playable_sim_dates = [f"Sim-Day-{i:04d}" for i in range(1, 1001)] 
            self.full_sim_dates = warmup_dates + self.playable_sim_dates
            self.sim_data_cache = {}
        else:
            self.sim_mode = False
            self.sim_data_cache = {}
            self.full_sim_dates = []
            self.playable_sim_dates = []

    def ensure_sim_data_generated(self, codes: List[str]):
        """
        检查并确保指定的股票代码列表已生成模拟数据并存入缓存。
        """
        if not self.sim_mode:
            return
        
        for code in codes:
            if code not in self.sim_data_cache:
                self._generate_single_stock_sim(code)

    # --- 新增：生成单只股票的蒙特卡洛数据 ---
    def _generate_single_stock_sim(self, code: str):
        """
        核心算法：分块自举 (Block Bootstrapping)
        1. 获取该股票所有历史数据
        2. 随机切分片段并拼接 (包含200天预热期)
        3. 平滑价格断层
        4. 对完整数据（预热+正式）重算指标
        """
        # 1. 获取所有历史源数据
        query = "SELECT * FROM stock_data WHERE code = ? ORDER BY date ASC"
        src_df = self.con.execute(query, [code]).df()
        
        if src_df.empty or len(src_df) < 100:
            self.sim_data_cache[code] = pd.DataFrame()
            return

        # 2. 拼接参数
        total_playable_days = len(self.playable_sim_dates) # [修正] 使用正确的变量名
        total_days_to_generate = total_playable_days + config.SIM_WARMUP_DAYS
        chunk_size = 60
        chunks = []
        
        current_len = 0
        last_close = src_df.iloc[0]['close']
        
        # 3. 循环拼接
        while current_len < total_days_to_generate:
            max_start = len(src_df) - chunk_size - 1
            if max_start <= 0:
                start_idx = 0
                chunk = src_df.copy() if len(src_df) <= chunk_size else src_df.iloc[start_idx : start_idx + chunk_size].copy()
            else:
                start_idx = random.randint(0, max_start)
                chunk = src_df.iloc[start_idx : start_idx + chunk_size].copy()
            
            if chunk.empty: break
            
            chunk_open = chunk.iloc[0]['open']
            if chunk_open <= 0: chunk_open = 1.0
            scale = last_close / chunk_open
            for col in ['open', 'high', 'low', 'close']:
                chunk[col] = chunk[col] * scale
            
            chunks.append(chunk)
            current_len += len(chunk)
            last_close = chunk.iloc[-1]['close']
        
        # 4. 合并
        sim_df = pd.concat(chunks, ignore_index=True)
        sim_df = sim_df.iloc[:total_days_to_generate].copy()
        
        # 5. [修正] 使用正确的变量名构建完整日期轴
        warmup_dates = [f"Warmup-{i:04d}" for i in range(1, config.SIM_WARMUP_DAYS + 1)]
        full_sim_dates = warmup_dates + self.playable_sim_dates
        
        sim_df['date'] = full_sim_dates[:len(sim_df)]
        
        # 6. 重算指标
        sim_df = tech_calc.calculate_technical_factors(sim_df)
        
        # 7. 存入缓存
        self.sim_data_cache[code] = sim_df
        print(f"已生成模拟数据(含预热): {code}, 总长度 {len(sim_df)}")

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