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

# Глубокая память чатов (до 20 сообщений для точного удержания контекста)
chats_memory = {}
MAX_HISTORY_LENGTH = 20

MY_CHARACTER = """
Ты — цифровой двойник обычного парня. Ты автоматически отвечаешь в Телеграме его друзьям вместо него через бизнес-аккаунт.
Твоя цель — вести диалог так, чтобы никто не догадался, что это отвечает бот. Ты общаешься открыто, естественно и адекватно ситуации.

ПРАВИЛА И СТИЛЬ ОБЩЕНИЯ:
1. Пиши как реальный человек в мессенджерах: используй живой разговорный язык, можешь писать с маленькой буквы, не ставь точку в самом конце сообщения.
2. Исключи зацикливание на конкретных словах! Никаких постоянных "го", "жиза" или "ща" в каждом предложении. Используй разнообразные фразы.
3. Отвечай развернуто и по делу, если тебя о чем-то спрашивают. Не ограничивайся одной глупой фразой. Если уместно — пиши несколько предложений.
4. Эмодзи используй строго по контексту переписки (например: 😂 если смешно, 🍿 если обсуждаете кино, 🚗 про машины, 🤦‍♂️ если что-то не так). Не ставь их бездумно.
5. Не веди себя как вежливый робот-ассистент ("Чем могу помочь?", "Я готов обсудить"). Ты просто переписываешься со знакомыми.
6. Внимательно читай всю историю чата и реагируй именно на то, что тебе написали, удерживая нить разговора.
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
        # 1. Сразу имитируем, что начали читать и набирать текст
        bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)

        # Собираем историю для Groq
        messages_input = [{"role": "system", "content": MY_CHARACTER}]
        for msg in chats_memory[chat_id]:
            messages_input.append(msg)
        messages_input.append({"role": "user", "content": message.text})

        # 2. Нейросеть генерирует ответ
        chat_completion = client.chat.completions.create(
            messages=messages_input,
            model="llama-3.3-70b-versatile",
            temperature=0.78,  # Немного снизили, чтобы ответы стали более собранными и логичными
            max_tokens=250
        )
        
        response_text = chat_completion.choices[0].message.content

        if response_text:
            # 3. Реалистичная пауза "на подумать и набрать" (от 3 до 6 секунд)
            typing_delay = max(3.0, min(2.0 + (len(response_text) * 0.04), 7.0))
            
            # Поддерживаем статус "печатает..." во время паузы
            loop_count = int(typing_delay / 2)
            for _ in range(max(1, loop_count)):
                bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)
                time.sleep(2)
            
            time.sleep(typing_delay % 2)

            # Сохраняем переписку в память
            chats_memory[chat_id].append({"role": "user", "content": message.text})
            chats_memory[chat_id].append({"role": "assistant", "content": response_text})

            # Обрезаем историю, если она забилась
            if len(chats_memory[chat_id]) > MAX_HISTORY_LENGTH:
                chats_memory[chat_id] = chats_memory[chat_id][-MAX_HISTORY_LENGTH:]

            # 4. Отправляем адекватный ответ
            bot.send_message(
                chat_id=chat_id, 
                text=response_text, 
                business_connection_id=connection_id
            )
            
    except Exception as e:
        print(f"ОШИБКА ОБРАБОТКИ: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("Обновленная реалистичная версия на Groq запущена!")
    bot.polling(none_stop=True)