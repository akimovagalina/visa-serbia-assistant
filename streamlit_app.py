import os
import json
import chromadb
import cohere
import streamlit as st
from langchain_cohere import CohereEmbeddings

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(
    page_title="Визовый ИИ-Ассистент",
    page_icon="🇪🇺",
    layout="centered"
)

DB_DIR = './chroma_db'
RAW_JSON_FILE = 'raw_visa_data.json'
COHERE_API_KEY = st.secrets["COHERE_API_KEY"]

# --- ИНИЦИАЛИЗАЦИЯ ИИ И БАЗЫ (КЭШИРУЕМ, ЧТОБЫ САЙТ НЕ ТОРМОЗИЛ) ---
@st.cache_resource
def init_models():
    embeddings_model = CohereEmbeddings(
        cohere_api_key=COHERE_API_KEY,
        model="embed-multilingual-v3.0"
    )
    cohere_client = cohere.Client(COHERE_API_KEY)
    chroma_client = chromadb.PersistentClient(path=DB_DIR)
    collection = chroma_client.get_collection(name="visa_assistant")
    return embeddings_model, cohere_client, collection

@st.cache_data
def load_raw_messages():
    if os.path.exists(RAW_JSON_FILE):
        with open(RAW_JSON_FILE, 'r', encoding='utf-8') as f:
            return {msg['id']: msg for msg in json.load(f)}
    return {}

try:
    embeddings_model, cohere_client, collection = init_models()
    raw_messages_dict = load_raw_messages()
except Exception as e:
    st.error(f"Ошибка инициализации базы данных: {e}")

# --- СПИСОК СТРАН ---
ALL_COUNTRIES = [
    "Венгрия", "Италия", "Германия", "Франция", "Япония", "Великобритания",
    "Австрия", "Кипр", "Македония", "Португалия", "Болгария", "Польша",
    "Словения", "Греция", "Словакия", "Финляндия", "Хорватия", "Албания",
    "Нидерланды", "Китай", "Швейцария"
]

# --- ИНТЕРФЕЙС САЙТА ---
st.title("🇪🇺 Визовый ИИ-Ассистент")
st.caption(
    "Умный помощник на основе ответов за последние 6 месяцев в чате "
    "'Serbia: visas for other countries (chat)'.\n\n"
    "Разработчик: Акимова Галина / @Hello_MonAmi"
)

# Боковая панель для выбора страны
with st.sidebar:
    st.header("📍 Настройки поиска")
    target_country = st.selectbox("Выбери страну подачи:", ALL_COUNTRIES)
    st.info(f"Бот будет искать сообщения строго по топику: **{target_country}**.")

# Главное поле ввода вопроса
user_query = st.text_input(
    f"Задай свой вопрос по стране {target_country}:", 
    placeholder="Например: Когда появляются слоты?"
)

# Кнопка запуска
if st.button("Спросить ИИ", type="primary"):
    if not user_query.strip():
        st.warning("Пожалуйста, введи текст вопроса!")
    else:
        with st.spinner("🔍 Ищу сообщения в архивах чата и подключаю ИИ..."):
            try:
                # 1. Векторизация и поиск в ChromaDB (ТОП-10)
                query_vector = embeddings_model.embed_query(user_query)
                results = collection.query(
                    query_embeddings=[query_vector],
                    n_results=10,
                    where={"country": target_country}
                )

                if not results or not results.get('documents') or not results['documents'][0]:
                    st.error(f"❌ Постов по стране {target_country} с таким смыслом не найдено.")
                else:
                    documents = results['documents'][0]
                    metadatas = results['metadatas'][0]

                    rag_context = ""
                    chat_logs_html = []

                    # Собираем данные
                    for i in range(len(documents)):
                        text = documents[i]
                        meta = metadatas[i]
                        
                        current_msg_id = meta.get('msg_id')
                        question_text = "Исходный вопрос не найден"
                        
                        if current_msg_id and current_msg_id in raw_messages_dict:
                            current_msg = raw_messages_dict[current_msg_id]
                            reply_to_id = current_msg.get('reply_to_id')
                            if reply_to_id and reply_to_id in raw_messages_dict:
                                question_text = raw_messages_dict[reply_to_id]['text']

                        rag_context += f"Запись #{i+1}:\nВопрос: {question_text}\nОтвет: {text}\n\n"
                        
                        # Сохраняем логи для раскрывающихся вкладок
                        chat_logs_html.append({
                            "title": f"📌 Пост #{i+1} | Дата: {meta.get('date', 'Неизвестна')}",
                            "question": question_text,
                            "answer": text
                        })

                    # 2. Генерация ответа через Cohere LLM
                    system_prompt = (
                        "Ты — умный визовый ассистент для русскоязычных экспатов в Сербии. "
                        "Твоя задача — изучить предоставленные записи из сербского чата взаимопомощи "
                        "и сделать один краткий, понятный общий вывод, ориентированный на подачу документов ИЗ СЕРБИИ. "
                        "Пиши структурировано, простым языком."
                    )
                    user_prompt = f"Контекст из чатов:\n{rag_context}\n\nВопрос пользователя: {user_query}"

                    response = cohere_client.chat(
                        model="command-r-plus-08-2024",
                        message=user_prompt,
                        preamble=system_prompt
                    )

                    # --- ВЫВОД РЕЗУЛЬТАТОВ НА ЭКРАН ---
                    st.success("✨ Ответ сформирован!")
                    
                    st.subheader(f"🤖 Общий вывод ИИ:")
                    st.write(response.text)
                    
                    st.write("---")
                    st.subheader("📋 Найденные исходные сообщения из чата:")
                    
                    # Плюс Streamlit: выводим логи в удобные раскрывающиеся вкладки
                    for log in chat_logs_html:
                        with st.expander(log["title"]):
                            st.markdown(f"**❓ Вопрос:** {log['question']}")
                            st.markdown(f"**💬 Ответ в чате:** {log['answer']}")

            except Exception as e:
                st.error(f"Произошла техническая ошибка: {e}")
