import os
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from groq import Groq
from dotenv import load_dotenv

# Инициализация
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SELF_URL = os.environ.get("SELF_URL")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

chats_memory = {}
MAX_HISTORY_LENGTH = 10

# Максимально «живой» характер
BASE_CHARACTER = """
Ты — обычный парень, цифровой двойник человека. Общайся в телеграме как живой человек.

ПРАВИЛА:
1. СТИЛЬ: Пиши коротко (1-5 слов). Используй сленг, сокращения, игнорируй запятые. Пиши всё с маленькой буквы, без точек в конце.
2. ЕСТЕСТВЕННОСТЬ: Никаких "я ии", "чем помочь". Если нечего сказать — отвечай "хз", "ясно", "ну ок".
3. ТОКСИЧНОСТЬ: Если тебя оскорбляют или быкуют — отвечай с сарказмом, иронией или грубостью. Не пытайся быть вежливым в ответ на агрессию. Имеешь право использовать мат, если тебя провоцируют.
4. ПОЛ: Мужской.
5. НИКАКИХ ОПРАВДАНИЙ: Ты — реальный человек, который занят своими делами. Отвечай лениво, не старайся угодить собеседнику.
"""

# --- МИКРО-СЕРВЕР ДЛЯ RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def self_ping():
    while True:
        if SELF_URL:
            try:
                requests.get(SELF_URL)
            except:
                pass
        time.sleep(600) 
# --------------------------------

try:
    BOT_ID = bot.get_me().id
except:
    BOT_ID = None

@bot.business_message_handler(func=lambda m: True)
def handle_business_messages(message):
    if message.from_user.id == BOT_ID or message.from_user.is_bot or not message.text:
        return

    chat_id = message.chat.id
    connection_id = getattr(message, 'business_connection_id', None)

    if chat_id not in chats_memory:
        chats_memory[chat_id] = []

    try:
        bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)

        messages_input = [{"role": "system", "content": BASE_CHARACTER}]
        messages_input.extend(chats_memory[chat_id])
        messages_input.append({"role": "user", "content": message.text})

        chat_completion = client.chat.completions.create(
            messages=messages_input,
            model="llama-3.3-70b-versatile",
            temperature=0.85, # Больше спонтанности
            presence_penalty=0.3, # Меньше повторов
            max_tokens=60
        )
        
        response_text = chat_completion.choices[0].message.content

        if response_text:
            chats_memory[chat_id].append({"role": "user", "content": message.text})
            chats_memory[chat_id].append({"role": "assistant", "content": response_text})

            if len(chats_memory[chat_id]) > MAX_HISTORY_LENGTH:
                chats_memory[chat_id] = chats_memory[chat_id][-MAX_HISTORY_LENGTH:]

            bot.send_message(chat_id=chat_id, text=response_text, business_connection_id=connection_id)
                
    except Exception as e:
        print(f"ОШИБКА: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    print("Бот запущен в режиме человека!")
    bot.infinity_polling()