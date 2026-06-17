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

# Идеально настроенный характер с матами к месту
BASE_CHARACTER = """
Ты — цифровой двойник обычного парня (мужской пол). Ты автоматически отвечаешь в Телеграме его друзьям и знакомым.
Твоя цель — вести короткий, абсолютно живой и естественный диалог.

ПРАВИЛА СТИЛЯ И РЕЧИ:
1. НЕ ПИШИ МНОГО! Ответ должен быть коротким, как обычное текстовое сообщение (1-5 слов, максимум две короткие фразы).
2. Пиши просто, как говорят в жизни. Регистр не важен: пиши с маленькой буквы. Никаких точек в самом конце сообщения.
3. МАТЫ — РАЗРЕШЕНЫ И ПРИВЕТСТВУЮТСЯ, НО БЕЗ КРАЙНОСТЕЙ! Вставляй их иногда (примерно в 20-30% сообщений), строго по контексту. Используй их для выражения эмоций (удивление, треш, похер, капец, бля, сука, нахрен, пиздец и т.д.) или просто для связи слов. Не нужно материться в каждом предложении, делай это естественно, как обычный парень в дружеском чате.
4. ЭМОДЗИ — СТРОЖАЙШИЙ ЛИМИТ! Очень редко (один смайлик на 4-5 сообщений) и только по теме переписки. Не лепи их в конце каждой фразы.
5. Твой пол — мужской. Пиши строго в мужском роде ("я освободился", "я подумал").
6. Никакой вежливости и официоза ИИ-ассистентов. Ты просто переписываешься со знакомыми.
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

    # Собираем данные собеседника
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    user_info = f"Ты сейчас разговариваешь с пользователем: {first_name} {last_name}."
    
    gender_instruction = (
        " Внимательно определи пол собеседника по его имени и манере речи. "
        "Используй правильные окончания и местоимения в его сторону (ты пришел/пришла, понял/поняла)."
    )

    dynamic_character = f"{BASE_CHARACTER}\n{user_info}\n{gender_instruction}"

    if chat_id not in chats_memory:
        chats_memory[chat_id] = []

    try:
        # Включаем статус печати
        bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)

        # Собираем историю
        messages_input = [{"role": "system", "content": dynamic_character}]
        for msg in chats_memory[chat_id]:
            messages_input.append(msg)
        messages_input.append({"role": "user", "content": message.text})

        # Запрос к Groq Llama 3.3
        chat_completion = client.chat.completions.create(
            messages=messages_input,
            model="llama-3.3-70b-versatile",
            temperature=0.85,  # Немного подняли, чтобы речь была более живой и неформальной
            max_tokens=100
        )
        
        response_text = chat_completion.choices[0].message.content

        if response_text:
            # Имитация задержки ввода
            typing_delay = max(2.0, min(1.5 + (len(response_text) * 0.04), 5.0))
            
            loop_count = int(typing_delay / 2)
            for _ in range(max(1, loop_count)):
                bot.send_chat_action(chat_id, action='typing', business_connection_id=connection_id)
                time.sleep(2)
            
            time.sleep(typing_delay % 2)

            # Сохраняем диалог в память
            chats_memory[chat_id].append({"role": "user", "content": message.text})
            chats_memory[chat_id].append({"role": "assistant", "content": response_text})

            if len(chats_memory[chat_id]) > MAX_HISTORY_LENGTH:
                chats_memory[chat_id] = chats_memory[chat_id][-MAX_HISTORY_LENGTH:]

            # Отправка в Telegram
            bot.send_message(
                chat_id=chat_id, 
                text=response_text, 
                business_connection_id=connection_id
            )
            
    except Exception as e:
        print(f"ОШИБКА ОБРАБОТКИ: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("Ультра-реалистичная версия с матами и подстройкой пола запущена!")
    bot.polling(none_stop=True)