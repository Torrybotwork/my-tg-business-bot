import os
import time
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

# Память чатов (теперь храним в простом текстовом формате, чтобы API не ругалось)
chats_memory = {}
MAX_HISTORY_LENGTH = 14  # Ограничим историю 7 диалогами, чтобы не путать ИИ

MY_CHARACTER = """
Ты — цифровой двойник обычного парня. Ты автоматически отвечаешь в Телеграме его друзьям вместо него через бизнес-аккаунт.
Твоя главная цель — общаться ТАК, чтобы никто не понял, что это нейросеть.

ПРАВИЛА И СТИЛЬ:
1. Пиши как реальный человек в мессенджере: коротко, можно с маленькой буквы, не ставь точку в конце последнего предложения.
2. Используй разговорный сленг (типа: жиза, капец, го, ща, ппц, норм, хз), но в меру.
3. ЭМОДЗИ — РЕДКО! Максимум один смайлик на 3-4 сообщения, и то самый простой (типа 😂, ) , 🤷‍♂️). 
4. Ответы должны быть короткими, буквально 1-2 фразы.
5. Не веди себя как вежливый ИИ-ассистент. Никаких "Чем я могу помочь?". Отвечай просто и прямо, как друг.
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
    # Фильтр от самоответов
    if message.from_user.id == BOT_ID or message.from_user.is_bot:
        return
    if not message.text:
        return

    chat_id = message.chat.id
    if chat_id not in chats_memory:
        chats_memory[chat_id] = []

    # Добавляем сообщение пользователя в историю (в виде структуры API)
    chats_memory[chat_id].append(
        types.Content(role="user", parts=[types.Part.from_text(text=message.text)])
    )

    try:
        # Включаем статус "Печатает..." в Telegram Business
        bot.send_chat_action(
            chat_id, 
            action='typing', 
            business_connection_id=getattr(message, 'business_connection_id', None)
        )

        # Отправляем запрос в Gemini
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=chats_memory[chat_id],
            config=types.GenerateContentConfig(
                system_instruction=MY_CHARACTER,
                temperature=0.85
            )
        )
        
        if response.text:
            # Реалистичная пауза для имитации ввода текста
            fake_delay = random.uniform(3.0, 6.0)
            time.sleep(fake_delay)

            # Добавляем ответ ИИ в историю
            chats_memory[chat_id].append(
                types.Content(role="model", parts=[types.Part.from_text(text=response.text)])
            )

            # Ограничиваем длину истории чата
            if len(chats_memory[chat_id]) > MAX_HISTORY_LENGTH:
                chats_memory[chat_id] = chats_memory[chat_id][-MAX_HISTORY_LENGTH:]

            # Отправляем итоговый ответ
            bot.send_message(
                chat_id=chat_id, 
                text=response.text, 
                business_connection_id=getattr(message, 'business_connection_id', None)
            )
            
    except Exception as e:
        # Если произошла ошибка, выводим её в логи Render, чтобы мы могли её прочитать
        print(f"КРИТИЧЕСКАЯ ОШИБКА GEMINI: {e}")
        # Очищаем последнюю реплику, чтобы история не ломалась при следующем сообщении
        if chats_memory[chat_id] and chats_memory[chat_id][-1].role == "user":
            chats_memory[chat_id].pop()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("Обновленный бесплатный веб-сервис бота запущен!")
    bot.polling(none_stop=True)