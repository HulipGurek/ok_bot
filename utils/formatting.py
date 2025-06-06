"""
Утилиты для форматирования данных.
"""
from typing import Any, Optional

def format_wiper_info(wiper_value: Any) -> str:
    """
    Форматирует информацию о щетке для отображения.
    
    Args:
        wiper_value: Значение размера щетки
        
    Returns:
        str: Отформатированная информация о щетке
    """
    import pandas as pd
    
    if pd.isna(wiper_value) or wiper_value in ['нет', 'Не указано']:
        return 'не установлена'
    return f"{wiper_value} мм"
