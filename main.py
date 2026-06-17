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

# Глубокая память чатов (хранит до 16 реплик = 8 полноценных диалогов)
chats_memory = {}
MAX_HISTORY_LENGTH = 16

MY_CHARACTER = """
Ты — цифровой двойник обычного парня. Ты автоматически отвечаешь в Телеграме его друзьям вместо него через бизнес-аккаунт.
Твоя главная цель — общаться ТАК, чтобы никто не понял, что это нейросеть. Ты должен идеально помнить нить разговора.

ПРАВИЛА И СТИЛЬ:
1. Пиши как реальный человек в мессенджере: накоротке, можно с маленькой буквы, никогда не ставь точку в конце последнего предложения.
2. Используй разговорный сленг (типа: жиза, капец, го, ща, ппц, норм, хз, треш, блин), но в меру.
3. ЭМОДЗИ — РЕДКО! Максимум один смайлик на несколько сообщений, и то самый простой (типа 😂, ) , 🤷‍♂️, ппц). 
4. Ответы должны быть короткими, буквально 1-2 фразы. Не расписывай поэмы.
5. Не веди себя как вежливый ИИ-ассистент. Никаких "Чем я могу помочь?". Отвечай просто, прямо и немного лениво, как обычный друг.
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

    if chat_id not in chats_memory:
        chats_memory[chat_id] = []

    try:
        # Включаем статус "Печатает..." в Телеграме сразу после получения сообщения
        bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)

        # Собираем контекст: Системная инструкция + История + Новое сообщение
        messages_input = [{"role": "system", "content": MY_CHARACTER}]
        for msg in chats_memory[chat_id]:
            messages_input.append(msg)
        messages_input.append({"role": "user", "content": message.text})

        # Запрос к Groq Llama 3.3
        chat_completion = client.chat.completions.create(
            messages=messages_input,
            model="llama-3.3-70b-versatile",
            temperature=0.82,
            max_tokens=120
        )
        
        response_text = chat_completion.choices[0].message.content

        if response_text:
            # Считаем реалистичную паузу: базовые 2.5 секунды + по 0.05 сек на каждый символ ответа
            # Таким образом, короткие ответы отправляются быстрее, длинные — чуть дольше
            typing_delay = min(2.5 + (len(response_text) * 0.05), 6.0)
            
            # Периодически обновляем статус печати во время паузы, чтобы он не пропадал
            loop_count = int(typing_delay / 2)
            for _ in range(max(1, loop_count)):
                bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)
                time.sleep(2)
            
            # Дозаписываем остаток времени, если остался
            time.sleep(typing_delay % 2)

            # Сохраняем реплики в память (именно в таком формате Groq помнит контекст)
            chats_memory[chat_id].append({"role": "user", "content": message.text})
            chats_memory[chat_id].append({"role": "assistant", "content": response_text})

            # Держим историю в пределах лимита
            if len(chats_memory[chat_id]) > MAX_HISTORY_LENGTH:
                chats_memory[chat_id] = chats_memory[chat_id][-MAX_HISTORY_LENGTH:]

            # Отправляем готовый текст
            bot.send_message(
                chat_id=chat_id, 
                text=response_text, 
                business_connection_id=connection_id
            )
            
    except Exception as e:
        print(f"ОШИБКА ОБРАБОТКИ: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("Умная версия с имитацией печати и памятью запущена!")
    bot.polling(none_stop=True)