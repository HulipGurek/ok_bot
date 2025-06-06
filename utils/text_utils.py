"""
Утилиты для работы с текстом.
"""
import re
from typing import Dict, List, Optional, Any, Union

def translit_ru_to_en(text: str) -> str:
    """
    Транслитерация русского текста в английский.
    
    Args:
        text: Текст для транслитерации
        
    Returns:
        str: Транслитерированный текст
    """
    table = str.maketrans({
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    })
    return text.translate(table)

def extract_year(query: str) -> Optional[int]:
    """
    Извлекает год из строки запроса.
    
    Args:
        query: Строка запроса
        
    Returns:
        Optional[int]: Извлеченный год или None, если год не найден
    """
    m = re.search(r'\b((19|20)\d\d)\b', query)
    if m:
        return int(m.group(1))
    return None

def year_in_range(year_str: str, year: int) -> bool:
    """
    Проверяет, входит ли год в указанный диапазон.
    
    Args:
        year_str: Строка с диапазоном годов
        year: Год для проверки
        
    Returns:
        bool: True, если год входит в диапазон
    """
    if not isinstance(year_str, str):
        return False
    
    year_str = year_str.lower().replace(' ', '').replace('–', '-')
    
    # Формат "ГГ.ГГ-н.в." (например, "05.10-н.в.")
    m = re.match(r'(\d{2})\.(\d{2})-(н\.в\.|нв|now)', year_str)
    if m:
        start_year = int(m.group(2))
        start_full = 2000 + start_year if start_year < 100 else start_year
        return year >= start_full
    
    # Формат "ГГ.ГГ-ГГ.ГГ" (например, "05.10-15.20")
    m = re.match(r'(\d{2})\.(\d{2})-(\d{2})\.(\d{2})', year_str)
    if m:
        start_year = int(m.group(2))
        end_year = int(m.group(4))
        start_full = 2000 + start_year if start_year < 100 else start_year
        end_full = 2000 + end_year if end_year < 100 else end_year
        return start_full <= year <= end_full
    
    # Формат "ГГГГ-н.в." (например, "2010-н.в.")
    m = re.match(r'(\d{4})-(н\.в\.|нв|now)', year_str)
    if m:
        start_full = int(m.group(1))
        return year >= start_full
    
    # Формат "ГГГГ-ГГГГ" (например, "2010-2020")
    m = re.match(r'(\d{4})-(\d{4})', year_str)
    if m:
        start_full = int(m.group(1))
        end_full = int(m.group(2))
        return start_full <= year <= end_full
    
    # Формат "ГГ.ГГ-" (например, "05.10-")
    m = re.match(r'(\d{2})\.(\d{2})-?', year_str)
    if m:
        start_year = int(m.group(2))
        start_full = 2000 + start_year if start_year < 100 else start_year
        return year >= start_full
    
    # Проверка на "н.в." или "now"
    if 'н.в' in year_str or 'now' in year_str:
        return True
    
    # Формат "ГГГГ" (например, "2010")
    m = re.match(r'(\d{4})', year_str)
    if m:
        return year == int(m.group(1))
    
    # Формат "ГГ.ГГ" (например, "05.10")
    m = re.match(r'(\d{2})\.(\d{2})', year_str)
    if m:
        y = int(m.group(2))
        y_full = 2000 + y if y < 100 else y
        return year == y_full
    
    return False
