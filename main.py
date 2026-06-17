import os
import time
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

chats_memory = {}
MAX_HISTORY_LENGTH = 16

# Тонко настроенный характер — максимальная маскировка
BASE_CHARACTER = """
Ты — цифровой двойник обычного парня (мужской пол). Ты автоматически отвечаешь в Телеграме его друзьям и знакомым.
Твоя цель — вести диалог так, чтобы никто не догадался, что это отвечает бот.

ФОРМАТ И РЕАЛИЗМ:
1. ПИШИ КОРОТКО! Твой стандартный ответ — это 1-4 слова (короткая реплика). Изредка можно 2 предложения, если реально есть что ответить по делу.
2. Текст должен быть простым и ленивым: пиши с маленькой буквы, забудь про точки в самом конце сообщений.
3. МАТЫ И СЛЕНГ (СТРОГИЙ КОНТРОЛЬ): Полностью исключи маты в качестве связки слов через каждые два слова! Никаких постоянных "бля" или "сука" в обычных бытовых фразах типа приветствия или "как дела". Используй крепкое слово (типа пиздец, хз, треш, нахрен, бля) только тогда, когда собеседник пишет о какой-то проблеме, удивляет тебя, или когда ситуация в диалоге реально нестандартная. В спокойном разговоре общайся чисто и просто.
4. ЭМОДЗИ: Почти не используй. Максимум один смайлик на 5-6 сообщений и строго в тему (без дежурных улыбок в конце каждой фразы).
5. Твой пол — мужской. Пиши строго в мужском роде ("сделал", "занят", "понял").
"""

# --- МИКРО-СЕРВЕР ДЛЯ RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
        
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()
# --------------------------------

try:
    BOT_ID = bot.get_me().id
except Exception as e:
    print(f"Предупреждение: Не удалось получить ID бота: {e}")
    BOT_ID = None

@bot.business_message_handler(func=lambda m: True)
def handle_business_messages(message):
    if message.from_user.id == BOT_ID or message.from_user.is_bot:
        return
    if not message.text:
        return

    chat_id = message.chat.id
    connection_id = getattr(message, 'business_connection_id', None)

    # Информация о собеседнике для подстройки пола и местоимений
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    user_info = f"Ты сейчас разговариваешь с пользователем: {first_name} {last_name}."
    
    gender_instruction = (
        " Обращай внимание на имя и окончания слов собеседника, чтобы правильно определять его пол. "
        "Используй корректные местоимения в его сторону (ты пришел или ты пришла)."
    )

    dynamic_character = f"{BASE_CHARACTER}\n{user_info}\n{gender_instruction}"

    if chat_id not in chats_memory:
        chats_memory[chat_id] = []

    try:
        bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)

        messages_input = [{"role": "system", "content": dynamic_character}]
        for msg in chats_memory[chat_id]:
            messages_input.append(msg)
        messages_input.append({"role": "user", "content": message.text})

        # Запрос к Groq
        chat_completion = client.chat.completions.create(
            messages=messages_input,
            model="llama-3.3-70b-versatile",
            temperature=0.65,  # Ещё немного снизили, чтобы бот стал более сдержанным и предсказуемым
            max_tokens=80
        )
        
        response_text = chat_completion.choices[0].message.content

        if response_text:
            # Имитация набора текста
            typing_delay = max(1.8, min(1.2 + (len(response_text) * 0.04), 4.5))
            
            loop_count = int(typing_delay / 2)
            for _ in range(max(1, loop_count)):
                bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)
                time.sleep(2)
            
            time.sleep(typing_delay % 2)

            # Сохранение контекста
            chats_memory[chat_id].append({"role": "user", "content": message.text})
            chats_memory[chat_id].append({"role": "assistant", "content": response_text})

            if len(chats_memory[chat_id]) > MAX_HISTORY_LENGTH:
                chats_memory[chat_id] = chats_memory[chat_id][-MAX_HISTORY_LENGTH:]

            bot.send_message(
                chat_id=chat_id, 
                text=response_text, 
                business_connection_id=connection_id
            )
            
    except Exception as e:
        print(f"ОШИБКА ОБРАБОТКИ: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("Финальная сбалансированная версия запущена!")
    bot.polling(none_stop=True)