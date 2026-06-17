import os
import time
import random
import telebot
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. Загружаем ключи из файла .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

# Память чатов и лимит истории (чтобы бот помнил контекст)
chats_memory = {}
MAX_HISTORY_LENGTH = 20

# Уникальный характер твоего цифрового двойника
MY_CHARACTER = """
Ты — цифровой двойник обычного парня. Ты автоматически отвечаешь в Телеграме его друзьям вместо него через бизнес-аккаунт.
Твоя главная цель — общаться ТАК, чтобы никто не понял, что это нейросеть.

ПРАВИЛА И СТИЛЬ:
1. Пиши как реальный человек в мессенджере: коротко, можно с маленькой буквы, не ставь точку в конце последнего предложения.
2. Используй разговорный сленг (типа: жиза, капец, го, ща, ппц, норм, хз), но не переборщи.
3. ЭМОДЗИ — РЕДКО! Максимум один смайлик на 3-4 сообщения, и то самый простой (типа 😂, ) , 🤷‍♂️). Никаких гирлянд из эмодзи.
4. Ответы должны быть короткими, буквально 1-2 фразы. Люди в чатах не пишут абзацами.
5. Не веди себя как вежливый ИИ-ассистент. Никаких "Чем я могу помочь?". Отвечай просто и прямо, как друг.
"""

# Узнаем ID нашего бота при запуске, чтобы использовать его в фильтре
try:
    BOT_ID = bot.get_me().id
except Exception as e:
    print(f"Предупреждение: Не удалось получить ID бота: {e}. Проверь TELEGRAM_TOKEN.")
    BOT_ID = None

# 2. Обработка бизнес-сообщений
@bot.business_message_handler(func=lambda m: True)
def handle_business_messages(message):
    # КРИТИЧЕСКИЙ БЕСПЛАТНЫЙ ФИЛЬТР: Если сообщение отправлено ТОБОЙ (твоим аккаунтом), 
    # бот его игнорирует. Это предотвращает вечную петлю запросов и сохраняет квоту!
    if message.from_user.id == BOT_ID or message.from_user.is_bot:
        return

    if not message.text:
        return

    chat_id = message.chat.id

    # Если чат новый, создаем историю
    if chat_id not in chats_memory:
        chats_memory[chat_id] = []

    # Добавляем реплику друга в память
    chats_memory[chat_id].append(
        types.Content(role="user", parts=[types.Part.from_text(text=message.text)])
    )

    try:
        # Включаем статус "Печатает..." в Telegram
        bot.send_chat_action(
            chat_id, 
            action='typing', 
            business_connection_id=getattr(message, 'business_connection_id', None)
        )

        # Отправляем историю в бесплатный тариф Gemini 2.5
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=chats_memory[chat_id],
            config=types.GenerateContentConfig(
                system_instruction=MY_CHARACTER,
                temperature=0.85
            )
        )
        
        if response.text:
            # Искусственная задержка (от 4 до 7 секунд), имитирующая реальное чтение и ввод текста
            fake_delay = random.uniform(4.0, 7.0)
            time.sleep(fake_delay)

            # Сохраняем ответ ИИ в память
            chats_memory[chat_id].append(
                types.Content(role="model", parts=[types.Part.from_text(text=response.text)])
            )

            # Обрезаем историю, чтобы она не росла бесконечно
            if len(chats_memory[chat_id]) > MAX_HISTORY_LENGTH:
                chats_memory[chat_id] = chats_memory[chat_id][-MAX_HISTORY_LENGTH:]

            # Отправляем сообщение другу от твоего имени
            bot.send_message(
                chat_id=chat_id, 
                text=response.text, 
                business_connection_id=getattr(message, 'business_connection_id', None)
            )
            
    except Exception as e:
        print(f"Ошибка в бизнес-чате: {e}")
        # Если API выдало ошибку (например, временный лимит), удаляем последний вопрос друга из памяти,
        # чтобы при следующем сообщении история не сломалась
        if chats_memory[chat_id] and chats_memory[chat_id][-1].role == "user":
            chats_memory[chat_id].pop()

# 3. Запуск бота
if __name__ == "__main__":
    print("Безопасный и полностью БЕСПЛАТНЫЙ бизнес-бот запущен!")
    bot.polling(none_stop=True)