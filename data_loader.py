"""
Data Loader for Stock Trading Game
Powered by DuckDB for high-performance zero-copy data access
"""
import os
import pandas as pd
import duckdb
from typing import List, Optional, Dict
import config

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
        return self._available_dates.copy()
    
    def get_daily_snapshot(self, date: str, codes: List[str] = None) -> pd.DataFrame:
        """
        Get a snapshot of stocks for a specific date.
        Optimization: If 'codes' is provided, DuckDB only scans relevant data.
        """
        # 基础查询
        base_query = "SELECT * FROM stock_data WHERE strftime(date, '%Y-%m-%d') = ?"
        params = [date]
        
        # 优化：如果提供了代码列表，直接在 SQL 层过滤
        if codes is not None and len(codes) > 0:
            # DuckDB 的 Python 客户端可以直接处理列表参数，使用 IN (?) 语法
            # 但为了兼容性，我们构建一个占位符字符串
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
        """
        Get historical data for specific stock.
        DuckDB will only read the Row Groups containing this specific code/date range.
        """
        # 确保按日期排序返回
        query = """
            SELECT * 
            FROM stock_data 
            WHERE code = ? 
              AND strftime(date, '%Y-%m-%d') >= ? 
              AND strftime(date, '%Y-%m-%d') <= ?
            ORDER BY date ASC
        """
        df = self.con.execute(query, [code, start_date, end_date]).df()
        
        # DuckDB 返回的 date 是 datetime64[ns]，为了 GUI 显示一致性，
        # 如果需要 string 格式，可以在这里转，或者在 ChartPanel 里处理。
        # ChartPanel 目前的代码兼容 datetime 对象。
        return df
    
    def get_stock_data_on_date(self, code: str, date: str) -> Optional[Dict]:
        """Get stock data for specific code on specific date"""
        query = """
            SELECT * 
            FROM stock_data 
            WHERE code = ? 
              AND strftime(date, '%Y-%m-%d') = ?
            LIMIT 1
        """
        df = self.con.execute(query, [code, date]).df()
        
        if df.empty:
            return None
        
        return df.iloc[0].to_dict()
    
    def get_random_stocks(self, date: str, n: int = 10) -> List[str]:
        """Get n random stock codes (excluding indexes)"""
        # 修改 SQL：排除 sh. 和 sz. 开头的代码
        query = """
            SELECT code 
            FROM stock_data 
            WHERE strftime(date, '%Y-%m-%d') = ? 
              AND code NOT LIKE 'sh.%' 
              AND code NOT LIKE 'sz.%'
            ORDER BY RANDOM() 
            LIMIT ?
        """
        df = self.con.execute(query, [date, n]).df()
        return df['code'].tolist()
    
    def close(self):
        """Close connection"""
        self.con.close()