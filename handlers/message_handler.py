"""
Модуль для обработки команд и сообщений пользователя.
"""
import os
import logging
import pandas as pd

from typing import List, Dict, Any, Optional, Tuple, Union

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import ContextTypes

from config import Config
from utils.database import Database
from utils.search import CarSearchEngine
from utils.user_manager import UserManager
from utils.synonyms import SynonymManager
from utils.logging_utils import log_user_action

logger = logging.getLogger(__name__)
MODELS_PER_PAGE = 50

class MessageHandler:
    """Класс для обработки сообщений пользователя."""
    
    def __init__(self, database: Database, user_manager: UserManager, synonym_manager: SynonymManager):
        """
        Инициализация обработчика сообщений.
        
        Args:
            database: Объект базы данных
            user_manager: Менеджер пользователей
            synonym_manager: Менеджер синонимов
        """
        self.db = database
        self.user_manager = user_manager
        self.synonym_manager = synonym_manager
        self.search_engine = CarSearchEngine(database.cars_df)

    async def show_models_with_pagination(self, update, context, matches, brand_query, page=0, edit=False):
        matches = matches.sort_values(by=["model", "years"], ascending=[True, True])
        total = len(matches)
        start = page * MODELS_PER_PAGE
        end = start + MODELS_PER_PAGE
        current_matches = matches.iloc[start:end]
        buttons = []
        for _, row in current_matches.iterrows():
            callback_id = self.user_manager.store_callback_data({
                "brand": row['brand'],
                "model": row['model'],
                "years": row['years'],
            })
            button_text = f"{row['model'].upper()} ({row['years']})"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"model_{callback_id}")])
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"models_page_{page-1}_{brand_query}"))
        if end < total:
            nav_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data=f"models_page_{page+1}_{brand_query}"))
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")])
        msg_text = (
            f"🔍 По марке <b>\"{brand_query}\"</b> найдено {total} моделей:\n\n"
            f"Показано {start+1}-{min(end, total)} из {total}\n"
            f"Выберите модель из списка:"
        )
        if edit:
            await update.callback_query.edit_message_text(
                msg_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                msg_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='HTML'
            )

    async def handle_brand_search(self, update, context, brand_query):
        user = update.effective_user
        self.user_manager.register_user(user.id)
        log_user_action(user.id, user.username, "BRAND_SEARCH", brand_query)
        await update.message.chat.send_action("typing")
        brand_query_norm = brand_query.strip().lower()

        # 1. Точное совпадение
        matches = self.db.cars_df[self.db.cars_df['brand'].str.lower() == brand_query_norm]
        canonical_for_pagination = brand_query  # по умолчанию

        # 2. Частичное совпадение
        if matches.empty:
            matches = self.db.cars_df[self.db.cars_df['brand'].str.lower().str.contains(brand_query_norm)]
        # 3. Поиск по синонимам
        if matches.empty:
            synonyms = self.synonym_manager.get_synonyms()
            for canon, syns in synonyms.items():
                all_syns = [canon] + (syns if isinstance(syns, list) else [syns])
                if brand_query_norm in [s.lower() for s in all_syns]:
                    matches = self.db.cars_df[self.db.cars_df['brand'].str.lower() == canon.lower()]
                    canonical_for_pagination = canon
                    break

        # 4. Если ничего не найдено — ошибка
        if matches.empty:
            await update.message.reply_text(
                f"По запросу <b>\"{brand_query}\"</b> не найдено ни одной марки автомобиля.",
                parse_mode='HTML'
            )
            return

        # 5. Всегда используем show_models_with_pagination!
        await self.show_models_with_pagination(update, context, matches, canonical_for_pagination, page=0)

    def _create_model_buttons_multirow(self, matches: pd.DataFrame, buttons_per_row: int = 1) -> List[List[InlineKeyboardButton]]:
        """
        Создает кнопки для выбора модели автомобиля с несколькими кнопками в строке.
        
        Args:
            matches: DataFrame с найденными моделями
            buttons_per_row: Количество кнопок в одной строке
            
        Returns:
            List[List[InlineKeyboardButton]]: Список кнопок

        """
        matches = matches.sort_values(by=["model", "years"], ascending=[True, True])
        buttons = []
        current_row = []
        seen = set()
        button_count = 0
        
        for _, row in matches.iterrows():
            key = (row['brand'], row['model'], row['years'])
            if key not in seen:
                callback_id = self.user_manager.store_callback_data({
                    "brand": row['brand'],
                    "model": row['model'],
                    "years": row['years'],
                })
                callback_data = f"model_{callback_id}"
                button_text = f"{row['model'].upper()} ({row['years']})"
                
                current_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
                button_count += 1
                
                # Если достигли нужного количества кнопок в строке или это последняя модель
                if button_count % buttons_per_row == 0:
                    buttons.append(current_row)
                    current_row = []
                
                seen.add(key)
                
                if len(seen) >= Config.MAX_RESULTS:
                    break
        
        # Добавляем оставшиеся кнопки, если есть
        if current_row:
            buttons.append(current_row)
        
        return buttons
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        '''
        Обрабатывает текстовые сообщения пользователя.
        '''
        # --- Патч brand_search_fixes ---
        if context.user_data.get('waiting_for_brand'):
            del context.user_data['waiting_for_brand']
            await self.handle_brand_search(update, context, update.message.text)
            return
            
        # Оригинальный код обработки сообщения
        user = update.effective_user
        self.user_manager.register_user(user.id)
        text = update.message.text.strip()
        context.user_data['user_query_message_id'] = update.message.message_id
        
        # Логирование действия пользователя
        log_user_action(user.id, user.username, "SEARCH", text)
        
        # Отправка индикатора загрузки
        await update.message.chat.send_action("typing")
        
        # Получение синонимов
        synonyms = self.synonym_manager.get_synonyms()
        
        # Функция для логирования отладочной информации
        def log_debug(msg: str) -> None:
            logger.info(f"SEARCH_DEBUG | User: {user.id} | Query: {text!r} | {msg}")
        
        # Проверяем, является ли запрос просто маркой автомобиля (без модели)
        # Это эвристика: если запрос короткий (1-2 слова) и не содержит цифр, 
        # то это, вероятно, только марка
        words = text.split()
        contains_digits = any(char.isdigit() for char in text)
        
        if len(words) <= 2 and not contains_digits:
            # Проверяем, есть ли точное совпадение по марке
            brand_matches = self.db.cars_df[self.db.cars_df['brand'].str.lower() == text.lower()]
            
            # Если есть точное совпадение по марке, обрабатываем как поиск по марке
            if not brand_matches.empty:
                await self.handle_brand_search(update, context, text)
                return
        
        # Поиск автомобилей по обычному запросу
        result = self.search_engine.search(text, synonyms, log_debug=log_debug)
        matches = result['matches']
        similar = result['similar']
        
        # Если нет совпадений, но есть похожие результаты
        if matches.empty and not similar.empty:
            buttons = self._create_model_buttons(similar)
            buttons.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")])
            
            await update.message.reply_text(
                f"🔍 По запросу <b>\"{text}\"</b> точных совпадений не найдено, но есть похожие модели:\n\n"
                f"Выберите модель из списка:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='HTML'
            )
            return
        
        # Если нет совпадений и нет похожих результатов
        if matches.empty:
            await update.message.reply_text(
                f"По запросу <b>\"{text}\"</b> ничего не найдено.\n\n"
                f"Попробуйте другой запрос, например:\n"
                f"• Audi • KIA • Lada\n"
                f"/start",
                parse_mode='HTML'
            )
            return
        
        # Если найдено только одно совпадение
        if len(matches) == 1:
            car = matches.iloc[0]
            car_info = self.db.get_car_info(car)
            
            mount = car['mount']
            driver_size = int(car['driver']) if str(car['driver']).isdigit() else None
            pass_size = int(car['passanger']) if str(car['passanger']).isdigit() else None
            
            # Получение доступных типов корпусов
            available_frames = self.db.get_available_frames(mount, [driver_size, pass_size])
            
            if available_frames.empty:
                await update.message.reply_text(
                    car_info + "\n⚠️ К сожалению, для этого автомобиля нет подходящих щёток в нашем каталоге.",
                    parse_mode='HTML'
                )
                return
            
            # Создание кнопок для выбора типа корпуса
            buttons = []
            for _, rowf in available_frames.iterrows():
                frame = rowf['gy_frame']
                frame_id = self.user_manager.store_callback_data({
                    "brand": car['brand'],
                    "model": car['model'],
                    "years": car['years'],
                    "mount": mount,
                    "driver_size": driver_size,
                    "pass_size": pass_size,
                    "gy_frame": frame
                })
                btn = InlineKeyboardButton(str(frame), callback_data=f"frame_{frame_id}")
                buttons.append([btn])
            

            
            # Добавление кнопки для нового поиска
            buttons.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")])
            
            await update.message.reply_text(
                car_info + "\n<b>Выберите тип щётки:</b>",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='HTML'
            )
            return
        
        # Если найдено несколько совпадений
        buttons = self._create_model_buttons(matches)
        buttons.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")])
        
        await update.message.reply_text(
            f"🔍 По запросу <b>\"{text}\"</b> найдено {len(matches)} моделей:\n\n"
            f"Выберите модель из списка:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'
        )
    
    def _create_model_buttons(self, matches: pd.DataFrame) -> List[List[InlineKeyboardButton]]:
        matches = matches.sort_values(by=["model", "years"], ascending=[True, True]) 
        buttons = []
        seen = set()
        for _, row in matches.iterrows():
            key = (row['brand'], row['model'], row['years'])
            if key not in seen:
                callback_id = self.user_manager.store_callback_data({
                    "brand": row['brand'],
                    "model": row['model'],
                    "years": row['years'],
                })
                callback_data = f"model_{callback_id}"
                button_text = f"{row['model'].upper()} ({row['years']})"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                seen.add(key)
            if len(buttons) >= Config.MAX_RESULTS:
                break
        return buttons