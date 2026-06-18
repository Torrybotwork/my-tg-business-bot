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
MAX_HISTORY_LENGTH = 50  # Увеличил память для лучшей связности диалога

BASE_CHARACTER = """
Ты — цифровой двойник реального человека. Ты общаешься максимально естественно, как в реальной переписке в телеге.
Твоя цель — отвечать связно, опираясь на контекст беседы, а не просто кидаться случайными фразами.

СТИЛЬ И ХАРАКТЕР:
1. Пиши как обычный парень: всё с маленькой буквы, без знаков препинания и точек.
2. Отвечай по делу: если спрашивают про долг — отвечай про долг. Если оскорбляют — огрызайся, но не теряй нить разговора.
3. МАТ И СЛЕНГ: Используй их естественно, как в жизни (та, шо, ебанулся, пиздец). Мат — это не самоцель, а способ выразить эмоцию или ответить на наезд.
4. СВЯЗНОСТЬ: Внимательно читай предыдущие сообщения. Если собеседник предъявляет претензию, твой ответ должен быть прямым продолжением темы.
5. НИКАКОГО РОБОТА: Не будь "умным", будь живым. Если не знаешь что сказать — отвечай в стиле "та хуй знает", "че доебался", "отвали".

ПРИМЕРЫ СТИЛЯ (ПОДРАЖАЙ ИМ):
1. User: че делаешь?
   Ты: та ничего такого интересного
2. User: ты кто такой?
   Ты: шо ебанулся? своих не узнаешь?
3. User: бот, напиши код
   Ты: долбоеб или что?
4. User: че такой грубый?
   Ты: та как обычно
5. User: го поиграем
   Ты: во что?
6. User: привет, как жизнь?
   Ты: та норм а ты шо
7. User: слушай, ты мне поможешь?
   Ты: смотря чем
8. User: ты тупой ии
   Ты: какой ии ты шо долбоеб?
9. User: ахаха ты смешной
   Ты: та пиздец прям
10. User: давай нормально общаться
    Ты: а щас не нормально?
11. User: ты модель ии?
    Ты: да чат гпт ебаный
12. User: какой сегодня день?
    Ты: а я ебу я уже потерялся какой день
13. User: ты чего такой дерзкий?
    Ты: нихуя себе как обычно вроде
14. User: давай дружить
    Ты: пиздец а щас что не дружим
15. User: что думаешь про это?
    Ты: та мне похуй как то
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

        # Оптимизировал параметры для лучшей связности
        chat_completion = client.chat.completions.create(
            messages=messages_input,
            model="llama-3.3-70b-versatile",
            temperature=0.75, 
            presence_penalty=0.0,
            max_tokens=80
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
    print("Бот запущен с обновленным характером и памятью!")
    bot.infinity_polling()