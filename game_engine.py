"""
Game Engine for Stock Trading Game
Handles trading logic, account management, and position tracking
With Serialization Support
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import config
from utils import calculate_commission

@dataclass
class Position:
    """Represents a stock position"""
    code: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    
    @property
    def cost(self) -> float:
        return self.quantity * self.avg_price
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def profit(self) -> float:
        return self.market_value - self.cost
    
    @property
    def profit_pct(self) -> float:
        if self.cost == 0: return 0.0
        return (self.profit / self.cost) * 100
    
    def update_price(self, price: float):
        self.current_price = price
    
    def add_shares(self, quantity: int, price: float):
        total_cost = self.cost + (quantity * price)
        self.quantity += quantity
        self.avg_price = total_cost / self.quantity if self.quantity > 0 else 0.0
    
    def remove_shares(self, quantity: int) -> bool:
        if quantity > self.quantity: return False
        self.quantity -= quantity
        return True

    # --- 序列化方法 ---
    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict) -> 'Position':
        return Position(**data)


@dataclass
class Trade:
    """Represents a trade transaction"""
    date: str
    code: str
    action: str
    quantity: int
    price: float
    commission: float
    total_amount: float
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict) -> 'Trade':
        return Trade(**data)


class TradeLog:
    """Manages trade history"""
    
    def __init__(self):
        self.trades: List[Trade] = []
    
    def add_trade(self, trade: Trade):
        """Add a trade to the log"""
        self.trades.append(trade)
    
    def get_trades(self) -> List[Trade]:
        """Get all trades"""
        return self.trades.copy()
    
    # --- 补回缺失的方法 ---
    def get_trades_for_stock(self, code: str) -> List[Trade]:
        """Get trades for specific stock"""
        return [t for t in self.trades if t.code == code]
    # --------------------
    
    # --- 序列化方法 ---
    def to_list(self) -> List[Dict]:
        return [t.to_dict() for t in self.trades]

    def load_from_list(self, data: List[Dict]):
        self.trades = [Trade.from_dict(item) for item in data]


class Account:
    """Manages trading account"""
    
    def __init__(self, initial_cash: float = None):
        self.initial_cash = initial_cash or config.INITIAL_CASH
        self.cash = self.initial_cash
        self.positions: Dict[str, Position] = {}
        self.trade_log = TradeLog()
        self.equity_history: List[Dict] = []
    
    @property
    def total_market_value(self) -> float:
        return sum(pos.market_value for pos in self.positions.values())
    
    @property
    def total_equity(self) -> float:
        return self.cash + self.total_market_value
    
    @property
    def total_profit(self) -> float:
        return self.total_equity - self.initial_cash
    
    @property
    def total_profit_pct(self) -> float:
        if self.initial_cash == 0: return 0.0
        return (self.total_profit / self.initial_cash) * 100
    
    def update_position_prices(self, prices: Dict[str, float]):
        for code, position in self.positions.items():
            if code in prices:
                position.update_price(prices[code])
    
    def buy(self, date: str, code: str, quantity: int, price: float) -> bool:
        amount = quantity * price
        commission = calculate_commission(amount, config.COMMISSION_RATE, config.MIN_COMMISSION)
        total_cost = amount + commission
        
        if total_cost > self.cash: return False
        
        self.cash -= total_cost
        
        if code in self.positions:
            self.positions[code].add_shares(quantity, price)
            self.positions[code].update_price(price)
        else:
            self.positions[code] = Position(code=code, quantity=quantity, avg_price=price, current_price=price)
        
        trade = Trade(date=date, code=code, action='BUY', quantity=quantity, price=price, commission=commission, total_amount=total_cost)
        self.trade_log.add_trade(trade)
        return True
    
    def sell(self, date: str, code: str, quantity: int, price: float) -> bool:
        if code not in self.positions: return False
        position = self.positions[code]
        if quantity > position.quantity: return False
        
        amount = quantity * price
        commission = calculate_commission(amount, config.COMMISSION_RATE, config.MIN_COMMISSION)
        total_proceeds = amount - commission
        
        self.cash += total_proceeds
        position.remove_shares(quantity)
        
        if position.quantity == 0:
            del self.positions[code]
        else:
            position.update_price(price)
        
        trade = Trade(date=date, code=code, action='SELL', quantity=quantity, price=price, commission=commission, total_amount=total_proceeds)
        self.trade_log.add_trade(trade)
        return True
    
    def record_equity(self, date: str):
        self.equity_history.append({
            'date': date,
            'cash': self.cash,
            'market_value': self.total_market_value,
            'total_equity': self.total_equity,
            'profit': self.total_profit,
            'profit_pct': self.total_profit_pct
        })
    
    def get_equity_curve(self):
        import pandas as pd
        if not self.equity_history:
            return pd.DataFrame(columns=['date', 'cash', 'market_value', 'total_equity', 'profit', 'profit_pct'])
        return pd.DataFrame(self.equity_history)
    
    def get_all_positions(self) -> List[Position]:
        return list(self.positions.values())

    # --- 序列化方法 ---
    def to_dict(self) -> Dict:
        """Serialize account state to dict"""
        return {
            'initial_cash': self.initial_cash,
            'cash': self.cash,
            'positions': {k: v.to_dict() for k, v in self.positions.items()},
            'trades': self.trade_log.to_list(),
            'equity_history': self.equity_history
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Account':
        """Create account from serialized dict"""
        account = cls(initial_cash=data['initial_cash'])
        account.cash = data['cash']
        
        # Restore positions
        for code, pos_data in data['positions'].items():
            account.positions[code] = Position.from_dict(pos_data)
            
        # Restore trade log
        account.trade_log.load_from_list(data['trades'])
        
        # Restore history
        account.equity_history = data['equity_history']
        
        return account