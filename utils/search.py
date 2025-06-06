"""
Модуль для поиска автомобилей.
"""
import re
import logging
import pandas as pd
from typing import Dict, List, Optional, Any, Callable, Set, Tuple

from utils.text_utils import extract_year, year_in_range
from utils.synonyms import apply_synonyms
from utils.cache import SearchCache

logger = logging.getLogger(__name__)

class CarSearchEngine:
    """Класс для поиска автомобилей."""
    
    def __init__(self, df: pd.DataFrame):
        """
        Инициализация поискового движка.
        
        Args:
            df: DataFrame с данными автомобилей
        """
        self.df = df
        self.cache = SearchCache()
    
    def search(self, query: str, synonyms: Dict[str, str], log_debug: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        Выполняет поиск автомобилей по запросу.
        
        Args:
            query: Строка запроса
            synonyms: Словарь синонимов
            log_debug: Функция для логирования отладочной информации
            
        Returns:
            Dict[str, Any]: Результаты поиска
        """
        # Проверяем кэш
        cached_result = self.cache.get(query)
        if cached_result is not None:
            return cached_result
        
        debug_log = []
        query_orig = query
        query_norm = self._normalize_text(query)
        debug_log.append(f"Исходный запрос: {query_orig!r} => normalize: {query_norm!r}")
        
        year = extract_year(query_norm)
        query_wo_year = query_norm
        if year:
            query_wo_year = re.sub(r'\b' + str(year) + r'\b', '', query_norm).strip()
        debug_log.append(f"Извлечённый год: {year}. Запрос без года: {query_wo_year!r}")
        
        parts = query_wo_year.split()
        parts_syn = apply_synonyms(parts, synonyms)
        debug_log.append(f"Слова после применения синонимов: {parts_syn}")
        
        matches = pd.DataFrame()
        fallback_tried = []
        similar = pd.DataFrame()
        
        # Поиск по номеру модели ВАЗ
        if len(parts_syn) == 1 and parts_syn[0].isdigit() and len(parts_syn[0]) in [3, 4]:
            matches, similar, fallback = self._search_vaz_model(parts_syn[0], year, debug_log)
            if not matches.empty or not similar.empty:
                fallback_tried.append(fallback)
        
        # Поиск по марке и модели
        elif len(parts_syn) == 2:
            matches, fallback = self._search_brand_model(parts_syn, debug_log)
            if not matches.empty:
                fallback_tried.append(fallback)
        
        # Поиск по нескольким словам
        elif len(parts_syn) >= 3:
            matches, fallback = self._search_multiple_words(parts_syn, debug_log)
            if not matches.empty:
                fallback_tried.append(fallback)
        
        # Поиск по одному слову
        elif len(parts_syn) == 1 and len(parts_syn[0]) > 1:
            matches, fallback = self._search_single_word(parts_syn[0], debug_log)
            if not matches.empty:
                fallback_tried.append(fallback)
        
        # Поиск похожих моделей по году и слову
        if matches.empty and year and len(parts_syn) >= 1:
            similar = self._search_similar_by_year_word(parts_syn[0], debug_log)
        
        # Фильтрация по году
        if not matches.empty and year:
            filtered_by_year = matches[matches['years'].apply(lambda s: year_in_range(str(s), year))]
            debug_log.append(f"Финальный фильтр по году {year}: {len(filtered_by_year)} из {len(matches)}")
            matches = filtered_by_year
        
        # Логирование отладочной информации
        if log_debug is not None:
            for dmsg in debug_log:
                log_debug(dmsg)
        
        result = {
            'matches': matches,
            'similar': similar,
            'log': debug_log,
            'fallbacks': fallback_tried
        }
        
        # Сохраняем результат в кэш
        self.cache.set(query, result)
        
        return result
    
    def _normalize_text(self, s: str) -> str:
        """
        Нормализует текст для поиска.
        
        Args:
            s: Текст для нормализации
            
        Returns:
            str: Нормализованный текст
        """
        from utils.text_utils import translit_ru_to_en
        
        s = str(s).strip().lower().replace('ё', 'е')
        if re.search(r'[а-я]', s):
            s = translit_ru_to_en(s)
        return s
    
    def _search_vaz_model(self, vaz_model: str, year: Optional[int], debug_log: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
        """
        Поиск по номеру модели ВАЗ.
        
        Args:
            vaz_model: Номер модели ВАЗ
            year: Год для фильтрации
            debug_log: Список для отладочных сообщений
            
        Returns:
            Tuple[pd.DataFrame, pd.DataFrame, str]: Найденные совпадения, похожие модели и использованный метод
        """
        debug_log.append(f"ВАЗ поиск по номеру: {vaz_model}")
        
        def vaz_match(model_field: str) -> bool:
            model_field = re.sub(r'\[.*?\]', '', str(model_field))
            model_field = re.sub(r'[\/,]', ' ', model_field)
            models = model_field.lower().split()
            return vaz_model.lower() in models
        
        vaz_matches = self.df[self.df['model'].apply(vaz_match)]
        debug_log.append(f"Найдено строк с ВАЗ {vaz_model}: {len(vaz_matches)}")
        
        if year:
            vaz_matches = vaz_matches[vaz_matches['years'].apply(lambda s: year_in_range(str(s), year))]
            debug_log.append(f"Фильтр по году {year}: осталось {len(vaz_matches)}")
        
        similar = pd.DataFrame()
        if vaz_matches.empty:
            similar = self.df[self.df['model'].apply(lambda m: vaz_model in str(m))]
            if not similar.empty:
                debug_log.append(f"Похожие ВАЗ модели по подстроке '{vaz_model}': {len(similar)}")
        
        return vaz_matches, similar, "vaz model+year"
    
    def _search_brand_model(self, parts_syn: List[str], debug_log: List[str]) -> Tuple[pd.DataFrame, str]:
        """
        Поиск по марке и модели.
        
        Args:
            parts_syn: Список слов с примененными синонимами
            debug_log: Список для отладочных сообщений
            
        Returns:
            Tuple[pd.DataFrame, str]: Найденные совпадения и использованный метод
        """
        brand, model_part = parts_syn
        matches = pd.DataFrame()
        
        # Строгое совпадение по бренду и началу модели
        if model_part.isdigit() or re.match(r"^[ix]?\d+[a-z]*$", model_part):
            m_strict = self.df[
                (self.df['brand_lower'] == brand) &
                (
                    self.df['model_lower'].str.startswith(model_part) |
                    self.df['model_lower'].str.match(rf"^{model_part}\b")
                )
            ]
            debug_log.append(f"Шаг 1a: Строгое совпадение бренд+модель начинается с {model_part}: найдено {len(m_strict)}")
            if not m_strict.empty:
                matches = m_strict
                return matches, "brand+model startswith"
        
        # Поиск по всем словам в полном имени
        def row_match(row: pd.Series) -> bool:
            full = row['brand_lower'] + ' ' + row['model_lower']
            return all(word in full for word in parts_syn)
        
        m1 = self.df[self.df.apply(row_match, axis=1)]
        debug_log.append(f"Шаг 1: Совпадение всех слов ({parts_syn}): найдено {len(m1)}")
        if not m1.empty:
            matches = m1
            return matches, "all words in brand+model"
        
        return matches, ""
    
    def _search_multiple_words(self, parts_syn: List[str], debug_log: List[str]) -> Tuple[pd.DataFrame, str]:
        """
        Поиск по нескольким словам.
        
        Args:
            parts_syn: Список слов с примененными синонимами
            debug_log: Список для отладочных сообщений
            
        Returns:
            Tuple[pd.DataFrame, str]: Найденные совпадения и использованный метод
        """
        def row_match(row: pd.Series) -> bool:
            full = row['brand_lower'] + ' ' + row['model_lower']
            return all(word in full for word in parts_syn)
        
        m1 = self.df[self.df.apply(row_match, axis=1)]
        debug_log.append(f"Шаг 1: Совпадение всех слов ({parts_syn}): найдено {len(m1)}")
        
        if not m1.empty:
            return m1, "all words in brand+model"
        
        return pd.DataFrame(), ""
    
    def _search_single_word(self, word: str, debug_log: List[str]) -> Tuple[pd.DataFrame, str]:
        """
        Поиск по одному слову.
        
        Args:
            word: Слово для поиска
            debug_log: Список для отладочных сообщений
            
        Returns:
            Tuple[pd.DataFrame, str]: Найденные совпадения и использованный метод
        """
        # Поиск по точному совпадению бренда
        m_brand = self.df[self.df['brand_lower'] == word]
        if not m_brand.empty:
            return m_brand, "brand=="
        
        # Поиск по точному совпадению модели или содержанию в модели
        m_model = self.df[self.df['model_lower'] == word]
        m_model_contains = self.df[self.df['model_lower'].str.contains(word, regex=False)]
        m_model_total = pd.concat([m_model, m_model_contains]).drop_duplicates()
        if not m_model_total.empty:
            return m_model_total, "model contains all"
        
        # Поиск по нечеткому совпадению бренда
        m_brand_fuzzy = self.df[self.df['brand_lower'].str.contains(word, regex=False)]
        if not m_brand_fuzzy.empty:
            return m_brand_fuzzy, "brand contains (fallback)"
        
        # Поиск по слову в модели
        m2 = self.df[self.df['model_lower'].apply(lambda v: word in v.split())]
        if not m2.empty:
            return m2, "model word"
        
        # Поиск по содержанию в модели (запасной вариант)
        m_model_contains2 = self.df[self.df['model_lower'].str.contains(word, regex=False)]
        if not m_model_contains2.empty:
            return m_model_contains2, "model contains (fallback)"
        
        return pd.DataFrame(), ""
    
    def _search_similar_by_year_word(self, word: str, debug_log: List[str]) -> pd.DataFrame:
        """
        Поиск похожих моделей по году и слову.
        
        Args:
            word: Слово для поиска
            debug_log: Список для отладочных сообщений
            
        Returns:
            pd.DataFrame: Похожие модели
        """
        sim = self.df[self.df['model'].apply(
            lambda m: word in str(m).replace('/', ' ').replace(',', ' ').split()
        )]
        
        if not sim.empty:
            debug_log.append(f"Похожие модели по слову/номеру '{word}': найдено {len(sim)}")
        
        return sim
