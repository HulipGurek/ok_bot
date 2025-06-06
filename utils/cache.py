"""
Модуль для кэширования результатов поиска.
"""
import time
import logging
from typing import Dict, Any, Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)

class SearchCache:
    """Класс для кэширования результатов поиска."""
    
    def __init__(self, expiry_time: int = Config.CACHE_EXPIRY):
        """
        Инициализация кэша поиска.
        
        Args:
            expiry_time: Время жизни кэша в секундах
        """
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._expiry_time = expiry_time
    
    def get(self, query: str) -> Optional[Any]:
        """
        Получает результат из кэша по запросу.
        
        Args:
            query: Строка запроса
            
        Returns:
            Optional[Any]: Результат из кэша или None, если результат не найден или устарел
        """
        if query in self._cache:
            timestamp, result = self._cache[query]
            if time.time() - timestamp < self._expiry_time:
                logger.info(f"Найден кэшированный результат для запроса: {query}")
                return result
            else:
                # Удаляем устаревший результат
                del self._cache[query]
                logger.info(f"Удален устаревший кэшированный результат для запроса: {query}")
        return None
    
    def set(self, query: str, result: Any) -> None:
        """
        Сохраняет результат в кэш.
        
        Args:
            query: Строка запроса
            result: Результат для сохранения
        """
        self._cache[query] = (time.time(), result)
        logger.info(f"Сохранен результат в кэш для запроса: {query}")
    
    def clear(self) -> None:
        """Очищает весь кэш."""
        self._cache.clear()
        logger.info("Кэш очищен")
    
    def clear_expired(self) -> int:
        """
        Очищает устаревшие записи в кэше.
        
        Returns:
            int: Количество удаленных записей
        """
        current_time = time.time()
        expired_keys = [
            key for key, (timestamp, _) in self._cache.items()
            if current_time - timestamp >= self._expiry_time
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"Удалено {len(expired_keys)} устаревших записей из кэша")
        
        return len(expired_keys)
