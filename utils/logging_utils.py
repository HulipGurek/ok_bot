"""
Модуль для логирования действий пользователей и системы.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from config import Config

# Настройка основного логгера
def setup_logging() -> None:
    """Настраивает логирование для приложения."""
    # Создаем директорию для логов, если она не существует
    os.makedirs(Config.LOGS_DIR, exist_ok=True)
    
    # Настройка основного логгера
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        filename=Config.LOG_FILE
    )
    
    # Настройка логгера действий пользователей
    user_logger = logging.getLogger('user_actions')
    user_logger.setLevel(logging.INFO)
    user_handler = logging.FileHandler(Config.USER_LOG_FILE, encoding='utf-8')
    user_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    user_logger.addHandler(user_handler)
    
    # Настройка логгера ошибок
    error_logger = logging.getLogger('errors')
    error_logger.setLevel(logging.ERROR)
    error_handler = logging.FileHandler(Config.ERROR_LOG_FILE, encoding='utf-8')
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    error_logger.addHandler(error_handler)

def get_current_utc() -> str:
    """
    Получает текущее время в UTC.
    
    Returns:
        str: Текущее время в формате YYYY-MM-DD HH:MM:SS
    """
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def log_user_action(user_id: int, username: str, action: str, input_text: Optional[str] = None, result: Optional[str] = None) -> None:
    """
    Логирует действие пользователя.
    
    Args:
        user_id: ID пользователя
        username: Имя пользователя
        action: Действие пользователя
        input_text: Входной текст (опционально)
        result: Результат действия (опционально)
    """
    user_logger = logging.getLogger('user_actions')
    
    current_time = get_current_utc()
    log_message = f"UTC: {current_time} | User ID: {user_id} | Username: {username} | Action: {action}"
    
    if input_text:
        log_message += f" | Input: {input_text}"
    
    if result:
        log_message += f" | Result: {result}"
    
    user_logger.info(log_message)

def log_error(error_type: str, error_message: str, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Логирует ошибку.
    
    Args:
        error_type: Тип ошибки
        error_message: Сообщение об ошибке
        context: Контекст ошибки (опционально)
    """
    error_logger = logging.getLogger('errors')
    
    log_message = f"Type: {error_type} | Message: {error_message}"
    
    if context:
        log_message += f" | Context: {context}"
    
    error_logger.error(log_message)
