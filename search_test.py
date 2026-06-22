import json
import os
import chromadb
import cohere
from langchain_cohere import CohereEmbeddings

DB_DIR = './chroma_db'
COHERE_API_KEY = "cohere_hdaOdzgf4yMM36LbMlYq6RfQZpN1EHFox4rBeGiM2LSg5R"  # Ваш ключ
RAW_JSON_FILE = 'raw_visa_data.json'

def load_raw_messages():
    if os.path.exists(RAW_JSON_FILE):
        with open(RAW_JSON_FILE, 'r', encoding='utf-8') as f:
            return {msg['id']: msg for msg in json.load(f)}
    return {}

def test_semantic_search():
    print("🌐 Инициализация поиска с жесткой фильтрацией...")
    
    raw_messages_dict = load_raw_messages()
    if not raw_messages_dict:
        print(f"⚠️ Предупреждение: файл {RAW_JSON_FILE} не найден.")

    embeddings_model = CohereEmbeddings(
        cohere_api_key=COHERE_API_KEY,
        model="embed-multilingual-v3.0"
    )

    cohere_client = cohere.Client(COHERE_API_KEY)

    chroma_client = chromadb.PersistentClient(path=DB_DIR)
    collection = chroma_client.get_collection(name="visa_assistant")

    user_query = "В какие дни выкладывают слоты"
    target_country = "Италия"
    
    print(f"🔍 Запрос: '{user_query}' | 📍 Жесткий фильтр по стране: {target_country}")
    
    query_vector = embeddings_model.embed_query(user_query)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=10,  # Ищем 10 лучших сообщений
        where={"country": target_country}
    )

    # ИСПРАВЛЕНИЕ: Достаем списки напрямую через индекс [0]
    if not results or not results.get('documents') or not results['documents'][0]:
        print("❌ Постов по этой стране с таким смыслом не найдено.")
        return

    documents = results['documents'][0]
    metadatas = results['metadatas'][0]

    rag_context = ""
    
    print(f"\n💡 ТОП-7 СОВПАДЕНИЙ ИЗ ЧАТА ПО СТРАНЕ {target_country.upper()}:")
    print("=" * 60)

    for i in range(len(documents)):
        text = documents[i]
        meta = metadatas[i]
        
        current_msg_id = meta.get('msg_id')
        question_text = "Текст исходного вопроса не найден"
        
        if current_msg_id and current_msg_id in raw_messages_dict:
            current_msg = raw_messages_dict[current_msg_id]
            reply_to_id = current_msg.get('reply_to_id')
            if reply_to_id and reply_to_id in raw_messages_dict:
                question_text = raw_messages_dict[reply_to_id]['text'].replace('\n', ' ')
        
        # Теперь сообщения точно напечатаются в терминале!
        print(f"📌 [Пост #{i+1}] | [Дата: {meta.get('date')}]")
        print(f"❓ ВОПРОС: {question_text}")
        print(f"💬 ОТВЕТ: {text}")
        print("-" * 60)
        
        rag_context += f" Запись #{i+1}:\nВопрос: {question_text}\nОтвет: {text}\n\n"

    print("\n🤖 Отправка данных в языковую модель Cohere...")
    
    system_prompt = (
        "Ты — умный визовый ассистент. Твоя задача — изучить предоставленные записи из чата "
        "и сделать один краткий, понятный общий вывод, который отвечает на вопрос пользователя. "
        "Пиши структурировано, простым языком."
    )
    
    user_prompt = f"Контекст из чатов:\n{rag_context}\n\nВопрос пользователя: {user_query}"

    response = cohere_client.chat(
        model="command-r-plus-08-2024",
        message=user_prompt,
        preamble=system_prompt
    )

    print("\n✨ ИТОГОВЫЙ ОБЩИЙ ВЫВОД ИИ-АССИСТЕНТА:")
    print("=" * 60)
    print(response.text)
    print("=" * 60)

if __name__ == "__main__":
    test_semantic_search()
