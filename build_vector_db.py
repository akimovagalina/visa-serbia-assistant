import json
import os
import time
import chromadb
from langchain_cohere import CohereEmbeddings

INPUT_FILE = 'processed_visa_data.json'
DB_DIR = './chroma_db'

# Токен Cohere API
COHERE_API_KEY = "cohere_hdaOdzgf4yMM36LbMlYq6RfQZpN1EHFox4rBeGiM2LSg5R"  # Ваш ключ

# Ограничение для стабильности работы на бесплатном тарифе (0 — без ограничений)
MAX_RECORDS_FOR_NOW = 10000 

def build_database():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: File {INPUT_FILE} not found. Run process_data.py first.")
        return

    print("🌐 Connecting to Cohere Multilingual Cloud Engine...")
    embeddings_model = CohereEmbeddings(
        cohere_api_key=COHERE_API_KEY,
        model="embed-multilingual-v3.0"
    )

    print("📦 Connecting to local ChromaDB database...")
    chroma_client = chromadb.PersistentClient(path=DB_DIR)
    collection = chroma_client.get_or_create_collection(name="visa_assistant")

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if MAX_RECORDS_FOR_NOW:
        print(f"✂️ Slicing the freshest {MAX_RECORDS_FOR_NOW} rows for fast cloud processing.")
        data = data[:MAX_RECORDS_FOR_NOW]

    print(f"🧬 Starting cloud vectorization for {len(data)} items...")
    start_time = time.time()

    chunk_size = 90
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        
        # Подготовка текстов и ID документов
        documents = [msg.get('text', '').strip() for msg in chunk]
        ids = [str(msg.get('id', int(time.time() + idx))) for idx, msg in enumerate(chunk)]
        
        # Формирование метаданных с сохранением оригинального msg_id
        metadatas = [{
            "date": msg.get("date", ""),
            "country": msg.get("country", "Unknown"),
            "type": msg.get("type", "General Discussion"),
            "msg_id": msg.get("id")  # <-- СВЯЗУЮЩИЙ ЭЛЕМЕНТ ДЛЯ ПОИСКА ВОПРОСОВ
        } for msg in chunk]

        # Получение векторных эмбеддингов от облачного движка Cohere
        vectors = embeddings_model.embed_documents(documents)
        
        # Запись порции данных в локальную ChromaDB
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=vectors
        )
        
        processed_count = min(i + chunk_size, len(data))
        elapsed_time = time.time() - start_time
        print(f"🚀 Cloud-Indexed {processed_count}/{len(data)} rows... (Elapsed: {elapsed_time:.1f}s)")
        
        # Пауза для обхода лимитов бесплатного тарифа Cohere (Trial Rate Limits)
        time.sleep(3.0)

    print(f"\n🎉 SUCCESS! Cloud-managed vector database fully prepared with robust metadata extraction.")
    print(f"Total objects securely stored in your local ChromaDB: {collection.count()}")

if __name__ == "__main__":
    build_database()
