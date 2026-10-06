# recipes_handler.py
import asyncio
import aiohttp
from random import choices
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from googletrans import Translator

# Инициализируем переводчик
translator = Translator()

THEMEALDB_API_URL = "https://www.themealdb.com/api/json/v1/1"


class RecipeStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_show_recipes = State()


async def translate_async(text: str, dest='ru') -> str:
    if not text:
        return ""

    # Ограничение Google Translate — 5000 символов.
    # Если рецепт слишком длинный, обрезаем его для перевода.
    text_to_translate = text[:4500]

    try:
        # Создаем новый объект переводчика для каждого запроса (так стабильнее)
        temp_translator = Translator()
        # В версии 4.0.0-rc1 этот вызов работает лучше
        result = temp_translator.translate(text_to_translate, dest=dest)
        return result.text
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        # Если перевод не удался, возвращаем оригинал
        return text


    # === ОБРАБОТЧИК 1 ===


async def fetch_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            return None


async def cmd_category_search_random(message: types.Message, state: FSMContext):
    args = message.get_args()

    try:
        count = int(args) if args else 1
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Пожалуйста, укажите число после команды.\nПример: `/category_search_random 3`",
                             parse_mode="Markdown")
        return

    await state.set_data({"count": count})

    url = f"{THEMEALDB_API_URL}/list.php?c=list"
    data = await fetch_json(url)

    if not data or 'meals' not in data:
        await message.answer("❌ Не удалось получить категории от API.")
        return

    categories = [item['strCategory'] for item in data['meals']] # type: ignore
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cat in categories:
        keyboard.add(KeyboardButton(cat))

    await message.answer("📋 Выберите категорию блюда:", reply_markup=keyboard)
    await RecipeStates.waiting_for_category.set()


# === ОБРАБОТЧИК 2 ===
async def process_category(message: types.Message, state: FSMContext):
    category = message.text.strip()
    state_data = await state.get_data()
    count = state_data.get('count', 1)

    url = f"{THEMEALDB_API_URL}/filter.php?c={category}"
    data = await fetch_json(url)

    if not data or 'meals' not in data or not data['meals']: # type: ignore
        await message.answer("❌ Рецепты не найдены. Выберите другую категорию.")
        return

    meals = data['meals'] # type: ignore
    selected_meals = choices(meals, k=min(count, len(meals)))

    meal_ids = [meal['idMeal'] for meal in selected_meals]
    await state.update_data(meal_ids=meal_ids)

    meal_names_en = [meal['strMeal'] for meal in selected_meals]
    translation_tasks = [translate_async(name) for name in meal_names_en]
    meal_names_ru = await asyncio.gather(*translation_tasks)

    response_text = "📝 Выбранные рецепты:\n"
    for idx, name_ru in enumerate(meal_names_ru, start=1):
        response_text += f"{idx}. {name_ru}\n"

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Показать рецепты"))

    await message.answer(response_text, reply_markup=keyboard)
    await RecipeStates.waiting_for_show_recipes.set()


# === ОБРАБОТЧИК 3 ===
async def process_show_recipes(message: types.Message, state: FSMContext):
    if message.text != "Показать рецепты":
        await message.answer("⚠️ Нажмите на кнопку «Показать рецепты».")
        return

    state_data = await state.get_data()
    meal_ids = state_data.get('meal_ids', [])

    await message.answer("⏳ Загружаю и перевожу рецепты...", reply_markup=ReplyKeyboardRemove())

    async def fetch_recipe_detail(meal_id):
        url = f"{THEMEALDB_API_URL}/lookup.php?i={meal_id}"
        res = await fetch_json(url)
        if res and 'meals' in res and res['meals']: # type: ignore
            return res['meals'][0] # type: ignore
        return None

    fetch_tasks = [fetch_recipe_detail(m_id) for m_id in meal_ids]
    meals_details = await asyncio.gather(*fetch_tasks)

    for meal in meals_details:
        if not meal:
            continue

        ingredients = []
        for i in range(1, 21):
            ing = meal.get(f'strIngredient{i}')
            meas = meal.get(f'strMeasure{i}')
            if ing and ing.strip():
                ingredients.append(f"{ing} ({meas})" if meas else ing)

        name_ru = await translate_async(meal.get('strMeal', ''))
        inst_ru = await translate_async(meal.get('strInstructions', ''))
        ing_ru = await translate_async(", ".join(ingredients))

        formatted_msg = f"“{name_ru}\n\nРецепт:\n{inst_ru}\n\nИнгредиенты: {ing_ru}”"

        if len(formatted_msg) > 4000:
            formatted_msg = formatted_msg[:3990] + "...”"

        await message.answer(formatted_msg)

    await state.finish()


def register_recipe_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_category_search_random, commands=['category_search_random'], state="*")
    dp.register_message_handler(process_category, state=RecipeStates.waiting_for_category)
    dp.register_message_handler(process_show_recipes, state=RecipeStates.waiting_for_show_recipes)