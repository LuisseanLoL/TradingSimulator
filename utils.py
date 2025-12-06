"""
Utility functions for Stock Trading Game
"""
from datetime import datetime
from typing import Union


def format_currency(amount: float) -> str:
    """Format number as currency (CNY)"""
    return f"¥{amount:,.2f}"


def format_percentage(value: float) -> str:
    """Format number as percentage"""
    return f"{value:+.2f}%"


def format_number(value: float, decimals: int = 2) -> str:
    """Format number with thousand separators"""
    return f"{value:,.{decimals}f}"


def format_date(date: Union[str, datetime]) -> str:
    """Format date for display"""
    if isinstance(date, str):
        # Assume format YYYY-MM-DD
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except:
            return date
    elif isinstance(date, datetime):
        return date.strftime("%Y-%m-%d")
    return str(date)


def validate_stock_code(code: str) -> bool:
    """Validate stock code format (6 digits)"""
    return code.isdigit() and len(code) == 6


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with default value for division by zero"""
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except:
        return default


def calculate_commission(amount: float, commission_rate: float, min_commission: float) -> float:
    """Calculate trading commission"""
    commission = amount * commission_rate
    return max(commission, min_commission)
