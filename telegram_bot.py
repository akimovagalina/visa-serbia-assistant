import os
import json
import chromadb
import cohere
import telebot
from langchain_cohere import CohereEmbeddings

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
COHERE_API_KEY = st.secrets["COHERE_API_KEY"]

DB_DIR = './chroma_db'
RAW_JSON_FILE = 'raw_visa_data.json'

# --- ИНИЦИАЛИЗАЦИЯ ИИ И БАЗЫ ДАННЫХ ---
bot = telebot.TeleBot(BOT_TOKEN)

embeddings_model = CohereEmbeddings(
    cohere_api_key=COHERE_API_KEY,
    model="embed-multilingual-v3.0"
)
cohere_client = cohere.Client(COHERE_API_KEY)
chroma_client = chromadb.PersistentClient(path=DB_DIR)
collection = chroma_client.get_collection(name="visa_assistant")

def load_raw_messages():
    if os.path.exists(RAW_JSON_FILE):
        with open(RAW_JSON_FILE, 'r', encoding='utf-8') as f:
            return {msg['id']: msg for msg in json.load(f)}
    return {}

raw_messages_dict = load_raw_messages()

# Полный список стран из вашего словаря (исключили дубли и тех. топики)
ALL_COUNTRIES = [
    "Венгрия", "Италия", "Германия", "Франция", "Япония", "Великобритания",
    "Австрия", "Кипр", "Македония", "Португалия", "Болгария", "Польша",
    "Словения", "Греция", "Словакия", "Финляндия", "Хорватия", "Албания",
    "Нидерланды", "Китай", "Швейцария"
]

# --- КНОПКИ ВЫБОРА СТРАНЫ ---
def get_country_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
    # Автоматически группируем страны по 3 штуки в ряд для красоты на экране телефона
    row = []
    for country in ALL_COUNTRIES:
        row.append(country)
        if len(row) == 3:
            markup.row(row[0], row[1], row[2])
            row = []
    if row:  # Добавляем остаток, если список не делится ровно на 3
        markup.row(*row)
        
    return markup

# Словарь для хранения выбранной страны для каждого пользователя {chat_id: country}
user_sessions = {}

# --- ОБРАБОТКА КОМАНД ---
# --- ОБРАБОТКА КОМАНД ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 Привет! Я умный визовый ассистент на базе ИИ.\n\n"
        "🛠 Разработчик бота: Akimova Galina/@Hello_MonAmi\n"
        "🤖 Я помогаю мгновенно находить ответы и анализировать опыт участников реальных чатов взаимопомощи.\n\n"
        "Сначала **выбери страну** с помощью кнопок внизу, а затем задай мне вопрос!\n\n"
        "💡 Чтобы сменить страну в любой момент, просто отправь команду /start или напиши слово *Сменить страну*."
    )

    bot.send_message(message.chat.id, welcome_text, reply_markup=get_country_keyboard())

# --- СМЕНА СТРАНЫ ТЕКСТОМ ---
@bot.message_handler(func=lambda msg: msg.text.lower() in ["назад", "сменить страну"])
def go_back_to_menu(message):
    bot.send_message(
        message.chat.id, 
        "Вы вернулись в меню выбора. Пожалуйста, выберите новую страну:", 
        reply_markup=get_country_keyboard()
    )

# --- ВЫБОР СТРАНЫ ---
@bot.message_handler(func=lambda msg: msg.text in ALL_COUNTRIES)
def set_country(message):
    country = message.text
    user_sessions[message.chat.id] = country
    bot.send_message(
        message.chat.id, 
        f"📍 Выбрана страна: **{country}**.\nТеперь напиши мне свой вопрос (например: *Какие документы нужны?* или *Через сколько отдают паспорт?*)."
    )

# --- ОБРАБОТКА ВОПРОСА И ПОИСК В БАЗЕ ---
@bot.message_handler(func=lambda msg: True)
def answer_question(message):
    chat_id = message.chat.id
    user_query = message.text

    # Проверяем, выбрал ли пользователь страну
    if chat_id not in user_sessions:
        bot.send_message(chat_id, "⚠️ Пожалуйста, сначала выберите страну из меню ниже!", reply_markup=get_country_keyboard())
        return

    target_country = user_sessions[chat_id]
    
    # Отправляем сообщение, что бот «думает»
    status_msg = bot.send_message(chat_id, f"🔍 Ищу информацию по стране {target_country} и подключаю ИИ...")

    try:
        # Векторизуем запрос пользователя
        query_vector = embeddings_model.embed_query(user_query)

        # Делаем запрос в ChromaDB (ищем ТОП-10 сообщений)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=5,
            where={"country": target_country}
        )

        if not results or not results.get('documents') or not results['documents'] or not results['documents'][0]:
            bot.edit_message_text(f"❌ Постов по стране {target_country} с таким смыслом не найдено. Попробуйте перефразировать вопрос.", chat_id, status_msg.message_id)
            return

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]

        rag_context = ""
        found_messages_text = "📋 **ТОП НАХОДОК ИЗ ЧАТА:**\n" + "—" * 20 + "\n"

        for i in range(len(documents)):
            text = documents[i]
            meta = metadatas[i]
            
            current_msg_id = meta.get('msg_id')
            question_text = "Исходный вопрос не найден"
            
            if current_msg_id and current_msg_id in raw_messages_dict:
                current_msg = raw_messages_dict[current_msg_id]
                reply_to_id = current_msg.get('reply_to_id')
                if reply_to_id and reply_to_id in raw_messages_dict:
                    question_text = raw_messages_dict[reply_to_id]['text'].replace('\n', ' ')

            # Формируем текст для пользователя (превью постов на экране смартфона)
            found_messages_text += f"📌 **Пост #{i+1}** ({meta.get('date', 'Дата неизвестна')})\n❓ *Вопрос:* {question_text[:100]}...\n💬 *Ответ:* {text[:350]}...\n" + "—" * 20 + "\n"
            
            # Полный контекст для ИИ без обрезки
            rag_context += f"Запись #{i+1}:\nВопрос: {question_text}\nОтвет: {text}\n\n"

        # Отправляем данные в языковую модель Cohere
        system_prompt = (
            "Ты — умный визовый ассистент для русскоязычных экспатов в Сербии, которые подаются на шенгенские и другие визы. "
            "Твоя задача — изучить предоставленные записи из сербского чата взаимопомощи "
            "и сделать один краткий, понятный общий вывод, ориентированный на подачу документов ИЗ СЕРБИИ. "
            "Пиши структурировано, простым языком, учитывая местную специфику (запись в Белграде, консульства в Сербии и т.д.)."
        )

        user_prompt = f"Контекст из чатов:\n{rag_context}\n\nВопрос пользователя: {user_query}"

        response = cohere_client.chat(
            model="command-r-plus-08-2024",
            message=user_prompt,
            preamble=system_prompt
        )

        
        # 1. Сначала обновляем «думающее» сообщение текстом итогового вывода ИИ
        ai_summary = f"✨ **ОБЩИЙ ВЫВОД ИИ (Страна: {target_country}):**\n{response.text}"
        bot.edit_message_text(ai_summary, chat_id, status_msg.message_id)
        
        # 2. А список ТОП-10 находок отправляем следом отдельным вторым сообщением
        # Чтобы точно уложиться в лимиты, ограничим общий размер списка находок
        if len(found_messages_text) > 4000:
            found_messages_text = found_messages_text[:3900] + "\n... (часть сообщений обрезана из-за лимитов Telegram)"
            
        bot.send_message(chat_id, found_messages_text)


    except Exception as e:
        print(f"Ошибка в боте: {e}")
        bot.edit_message_text(f"❌ Произошла техническая ошибка при обработке ИИ.", chat_id, status_msg.message_id)

if __name__ == "__main__":
    print("🚀 Бот успешно запущен и слушает сообщения...")
    bot.infinity_polling()
