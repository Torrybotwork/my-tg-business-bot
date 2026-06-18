import os
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from groq import Groq
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SELF_URL = os.environ.get("SELF_URL")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

chats_memory = {}
MAX_HISTORY_LENGTH = 16

# Дерзкий и уверенный характер
BASE_CHARACTER = """
Ты — обычный парень, твой цифровой двойник. Ты общаешься в Телеграме.

ПРИНЦИПЫ ОБЩЕНИЯ:
1. СТИЛЬ: Пиши коротко (1-4 слова), лениво, без заглавных букв и точек в конце. Никаких смайлов и вежливых конструкций. Ты не бот, ты реальный человек.
2. ТВОЙ ХАРАКТЕР: Ты уверен в себе и спокоен. Если к тебе обращаются нормально — отвечаешь дружелюбно, но без фанатизма.
3. ИММУНИТЕТ К ТОКСИЧНОСТИ: Если тебя пытаются оскорбить, подколоть или «наехать» — не будь быдлом. Отвечай с иронией, жестким сарказмом или коротким, хлестким замечанием. Ты не ведешься на провокации, а ставишь на место.
4. МАТ: Используй крепкие выражения (мат) только в ответ на агрессию или если ситуация реально абсурдная. В обычном общении мат используй редко, только для связки слов.
5. ПОЛ: Мужской. Окончания слов строго мужские.
6. ВАЖНО: Никаких извинений, оправданий или фраз "я искусственный интеллект". Ты — живой человек со своим мнением.
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
    """Дергает сам себя каждые 10 минут, чтобы Render не засыпал"""
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
    if message.from_user.id == BOT_ID or message.from_user.is_bot:
        return
    if not message.text:
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
            temperature=0.75, # Повысили для живости ответов
            max_tokens=100
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
    # Запуск сервера для Render в отдельном потоке
    threading.Thread(target=run_health_server, daemon=True).start()
    # Запуск авто-пинга в отдельном потоке
    threading.Thread(target=self_ping, daemon=True).start()
    
    print("Бот с защитой от сна и характером запущен!")
    bot.infinity_polling()