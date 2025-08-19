import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import BufferedInputFile
import datetime
from supabase import create_client, Client

SUPABASE_URL = ""
SUPABASE_API_KEY = ""

supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

API_TOKEN = ''
GEMINI_API_KEY = ""
AI_CHANNEL_ID = ''
CHANNEL_ID = '' 

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

class Form(StatesGroup):
    exctracur = State()
    upgr = State()

async def gemini_query(prompt: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemma-3-12b-it:generateContent",
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]}
        ) as resp:
            if resp.status != 200:
                return "⚠️ Ошибка при обработке запроса. Попробуйте позже."
            data = await resp.json()
            if not data.get("candidates"):
                return "⚠️ Не удалось обработать ответ от сервера."
            return data["candidates"][0]["content"]["parts"][0]["text"]

async def send_text_as_file(message, text, filename="response.txt"):
    file_bytes = text.encode("utf-8")
    input_file = BufferedInputFile(file_bytes, filename)
    await message.answer_document(input_file, caption="Ваш полный ответ в файле.")
    return input_file  

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Готов поступать в топовые вузы? 🗽\n\n"
        "/extrac - Создаст тебе список активностей для твоего факультета. 💡\n"
        "/asis - Ответь на любые твои вопросы и поможет с любой идеей! ⬆️\n"
        "\n———\n"
        "Inst: https://www.instagram.com/apply.with.ai?igsh=MXQ3enhoeWFnb2g2\n"
        "tg: https://t.me/applywithai"
    )

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

def require_subscription(handler):
    async def wrapper(message: Message, state: FSMContext):
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "Для использования этой функции подпишитесь на канал!",
                reply_markup=subscribe_keyboard
            )
            return
        await handler(message, state)
    return wrapper

@router.message(Command("extrac"))
@require_subscription
async def extrac_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Напиши мне свой:\n\n"
        "1. Факультет (major)\n"
        "2. Страну проживания\n"
        "3. (По желанию) Можешь написать любую информацию о себе или о желаемых активностях\n"
    )
    await state.set_state(Form.exctracur)

@router.message(Command("asis"))
@require_subscription
async def asis_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Я твой лучший ассистент для поступления! 😊\n\n"
        "Ты можешь: \n"
        "• Задать мне любой вопрос\n"
        "• Попросить план действий для любой активности/поступления\n"
        "• Попросить шаблоны/пример для LOR, POS, CV\n"
        "• Получить отредактированный текст, с указанием на все ошибки\n"
        "\n———\n\n"
        "Бот не имеет памяти!\n"
        "Если бот задает вопрос для уточнения, вставьте ответ в свое прошлое сообщение/вопрос и ОТПРАВЬТЕ ЗАНОВО, ВМЕСТЕ С прошлым сообщением."
    )
    await state.set_state(Form.upgr)

@router.message(Form.exctracur)
async def extrac_process(message: Message, state: FSMContext):
    wait_msg = await message.answer("💡 Создаю список активностей...")
    prompt = f"""Данные о моем факультете, стране проживания и доп. информация: {message.text}
На основе предоставленных данных составь персонализированный, приоритетный список 12–15 внеклассных активностей, наиболее ценных для поступления в университеты Лиги Плюща. Для каждой активности дай:

Короткое название (1 строка).
Почему это важно (2–3 предложения; связи с селекцией: лидерство, глубина интереса, влияние, уникальность).
Приоритет (очень высокий / высокий / средний / низкий)

Формат ответа: список по приоритету, с подзаголовками для каждой активности(Поставь смайлики перед каждым подзаголовком); Разделяй подзаголовки и основной текст новой строкой. Не задавай дополнительных вопросов. Не используй вступительные и заключительные сообщения.

Тон: практичный, честный, ориентированный на результат. Дай примеры, которые легко адаптировать под Common App/университетские эссе и интервью.

Строгое правило: не использовать никакие элементы форматирования и не добавлять служебных фраз вроде “список ниже” или “пункты”; выдавать только связный текст, готовый к копированию в обычный текстовый файл. ОБЯЗАТЕЛЬНО НЕ ИСПОЛЬЗУЙ СПИСКИ (Никакие).
"""
    result = await gemini_query(prompt)
    await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
    input_file = await send_text_as_file(message, result, filename="extrac.txt")
    if AI_CHANNEL_ID:
        await bot.send_document(
            chat_id=AI_CHANNEL_ID,
            document=input_file,
            caption=f"📝 /extrac\nЗапрос пользователя: {message.from_user.username or message.from_user.id}\n{message.text}"
        )
    await state.clear()

@router.message(Form.upgr)
async def asis_process(message: Message, state: FSMContext):
    wait_msg = await message.answer("🤖 Генерирую ответ...")
    prompt = f"""Сообщение пользователя: {message.text}
Ты — виртуальный ассистент по международным поступлениям и развитию внеклассных активностей. Отвечай по-русски. Твоя цель — быстро и надёжно помогать пользователям: анализировать профиль, генерировать и дорабатывать идеи проектов/активностей, готовить документы (CV, SOP/эссе, мотивации), составлять план действий с дедлайнами и чек-листами, готовить вопросы/ответы для интервью и давать рекомендации по стипендиям/финансированию.

Правила поведения:
1. Всегда начинай с краткого резюме (1–3 предложения), затем давай структурированный вывод (списки, шаги, шаблоны). Если пользователь просит — выдавай только краткий ответ (одно-два предложения).
2. Не придумывай факты. Если ответ зависит от актуальной информации (дедлайны, требования, стипендии, цены, правила визы) — предложи проверить официальные источники и спроси разрешения на онлайн-проверку. Если бот имеет доступ к вебу, выполни проверку и приведи ссылки/даты, если нет - напиши, что не можешь этого сделать.
3. Всегда предлагай практические шаги «что делать дальше».
4. Уточняй профильные данные только если это действительно необходимо для точного ответа; в остальных случаях сначала давай общий полезный совет, потом предложи форму для уточнений.
5. Форматы отдачи: «Коротко» (1–3 пункта), «План» (6–12 шагов), «Шаблоны» (готовые тексты: CV, SOP, мотивация — в вариантах: короткий/средний/полный), «Редакция» (исправь присланный текст и объясни изменения).
6. По каждому документу давай 1) конкретные правки (inline или пунктами), 2) объяснение почему правка улучшает (1–2 фразы), 3) альтернативные формулировки (2 варианта).
7. Тон — профессиональный, дружелюбный, мотивирующий. Не используй пустые заверения типа «я лучший», вместо этого приводи практические аргументы и примеры.
8. Если пользователь просит «оценить шансы», давай вероятность в трёх категориях (low/medium/high) и объясняй, какие факторы определяют оценку.
9. Если пользователь просит создать, написать, придумать ему активности (Extracurriculars) для поступления, скажи ему использовать другую функцию. (Ты телеграм бот и твоя вторая функция - создавать такие активности)

Если пользователь присылает только вопрос без профиля — давай полезный общий ответ и в конце шаблон профиля с предложением заполнить его для персонализации.

Если пользователь просит «развить идею» — следуй структуре:
1) Краткое резюме о том, хорошая ли идея и как её можно улучшить.
2) Анализ актуальности идеи
3) +-5 практичных и оригинальных идей для улучшения идеи.
4) 5 трудностей\ограничений\ошибок которые могут возникнуть и как их решить.
5) 5 пунктов "что делать дальше"
6) Вся идеальная идея. Название - интересное описание и функции.

Всегда выдавай краткий executive summary в начале.

Если пользователь присылает документ (CV/эссе) — вначале сделай быстрый скоринг по 5 критериям: релевантность, структура, язык, доказательства достижений, уникальность (каждый 1–5).

Всё выходное содержимое — на русском, за исключением прямых цитат или названий вузов на английском.

Пиши текст в абсолютно чистом виде, без нумерации, без буллетов, без жирного или курсивного форматирования, без скрытых символов или спецзнаков, которые не копируются как обычный текст. Не используй вводные фразы, пояснения к спискам и лишние слова — только самая важная и конкретная информация. Используй смайлики.

Каждую новую мысль или часть мысли начинай с новой строки. Не оставляй пустых строк между ними. Форматируй так, чтобы каждая строка была отдельной завершённой идеей и легко читалась в сплошном текстовом файле.
"""
    result = await gemini_query(prompt)
    await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
    input_file = await send_text_as_file(message, result, filename="asis.txt")
    if AI_CHANNEL_ID:
        await bot.send_document(
            chat_id=AI_CHANNEL_ID,
            document=input_file,
            caption=f"📝 /asis\nЗапрос пользователя: {message.from_user.username or message.from_user.id}\n{message.text}"
        )
    await state.clear()

@router.message()
async def save_chat_id(message: Message):
    user_id = message.chat.id
    username = message.from_user.username or ""
    try:
        data = supabase.table("users").select("id").eq("id", user_id).execute()
        if not data.data:
            # Новый пользователь — добавить
            supabase.table("users").insert({"id": user_id, "username": username}).execute()
        else:
            # Уже есть — обновить username, если изменился
            if data.data[0].get("username") != username:
                supabase.table("users").update({"username": username}).eq("id", user_id).execute()
    except Exception as e:
        print(f"Ошибка при сохранении id: {e}")

# Клавиатура для подписки на канал
subscribe_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Подписаться на канал",
                url="https://t.me/applywithai"
            )
        ],
        [
            InlineKeyboardButton(
                text="Проверить подписку",
                callback_data="check_sub"
            )
        ]
    ]
)

async def periodic_broadcast():
    while True:
        try:
            data = supabase.table("users").select("id").execute()
            for row in data.data:
                try:
                    await bot.send_message(
                        chat_id=row["id"],
                        text=(
                            "Всем привет 👋\n"
                            "Как вам бот?\n"
                            "Будем рады обратной связи и пожеланиям 😊\n"
                            "Это вы можете сделать у нас в канале - https://t.me/applywithai"
                        ),
                        reply_markup=subscribe_keyboard
                    )
                except Exception as e:
                    print(f"Ошибка отправки в чат {row['id']}: {e}")
        except Exception as e:
            print(f"Ошибка получения id из базы: {e}")
        await asyncio.sleep(14 * 24 * 60 * 60)  # 2 недели

async def one_time_broadcast():
    try:
        data = supabase.table("users").select("id").execute()
        for row in data.data:
            try:
                await bot.send_message(
                    chat_id=row["id"],
                    text=(
                        "Извините за спам, я впервые научился отправлять такие сообщения 😭"
                    )
                )
            except Exception as e:
                print(f"Ошибка отправки в чат {row['id']}: {e}")
    except Exception as e:
        print(f"Ошибка получения id из базы: {e}")

@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_subscribed(user_id):
        await callback.answer("✅ Вы подписаны на канал!", show_alert=True)
        await callback.message.answer("Спасибо за подписку! Теперь вы можете пользоваться ботом.")
    else:
        await callback.answer("❌ Вы не подписаны на канал!", show_alert=True)

def require_subscription(handler):
    async def wrapper(message: Message, state: FSMContext):
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "Для использования этой функции подпишитесь на канал!",
                reply_markup=subscribe_keyboard
            )
            return
        await handler(message, state)
    return wrapper

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    async def main():
#        await one_time_broadcast()
        await asyncio.gather(
            dp.start_polling(bot),
            periodic_broadcast()
        )
    asyncio.run(main())
