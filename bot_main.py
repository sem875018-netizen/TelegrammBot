# bot_main.py
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from token_data import BOT_TOKEN
from recipes_handler import register_recipe_handlers

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализируем бота и диспетчер с хранилищем состояний в ОЗУ
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# Обработчик стартовой команды
@dp.message_handler(commands=['start', 'help'], state="*")
async def cmd_start(message: types.Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Я кулинарный бот для работы с базой данных рецептов TheMealDB. 🍲\n\n"
        f"👉 **Как запустить поиск:**\n"
        f"Используйте команду `/category_search_random` с указанием числа желаемых случайных рецептов.\n\n"
        f"Пример:\n"
        f"`/category_search_random 2`",
        parse_mode="Markdown"
    )


# Регистрируем импортированные обработчики
register_recipe_handlers(dp)

if __name__ == '__main__':
    print("Бот успешно запущен!")
    executor.start_polling(dp, skip_updates=True)