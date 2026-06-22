import json
import os
import time
import chromadb
from langchain_cohere import CohereEmbeddings

INPUT_FILE = 'processed_visa_data.json'
DB_DIR = './chroma_db'
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")

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

    # Читаем все обработанные сообщения
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        all_data = json.load(f)

    # --- ИСПРАВЛЕНИЕ: ПРОВЕРКА СУЩЕСТВУЮЩИХ ЗАПИСЕЙ ---
    existing_records = collection.get()
    existing_ids = set(existing_records['ids']) if existing_records and 'ids' in existing_records else set()
    print(f"📋 В базе уже находится векторов: {len(existing_ids)}")

    # Фильтруем данные, оставляя ТОЛЬКО те сообщения, которых НЕТ в базе
    data_to_process = [msg for msg in all_data if str(msg.get('id')) not in existing_ids]

    if not data_to_process:
        print("💤 Все сообщения уже проиндексированы. База находится в актуальном состоянии!")
        print(f"Итого строк в вашей ChromaDB: {collection.count()}")
        return

    print(f"🧬 Обнаружено новых сообщений для векторизации: {len(data_to_process)}")

    # Если новых сообщений слишком много (первый запуск), ограничим порцию для стабильности
    if len(existing_ids) == 0 and len(data_to_process) > 10000:
        print("✂️ Первичная сборка: берем свежий батч в 10 000 строк.")
        data_to_process = data_to_process[:10000]

    start_time = time.time()
    chunk_size = 90
    
    for i in range(0, len(data_to_process), chunk_size):
        chunk = data_to_process[i:i + chunk_size]
        
        documents = [msg.get('text', '').strip() for msg in chunk]
        ids = [str(msg.get('id')) for msg in chunk]
        
        metadatas = [{
            "date": msg.get("date", ""),
            "country": msg.get("country", "Unknown"),
            "type": msg.get("type", "General Discussion"),
            "msg_id": msg.get("id")
        } for msg in chunk]

        # Векторизуем ТОЛЬКО новые строки
        vectors = embeddings_model.embed_documents(documents)
        
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=vectors
        )
        
        processed_count = min(i + chunk_size, len(data_to_process))
        elapsed_time = time.time() - start_time
        print(f"🚀 Cloud-Indexed {processed_count}/{len(data_to_process)} новых строк... (Elapsed: {elapsed_time:.1f}s)")
        
        time.sleep(15.0)

    print(f"\n🎉 SUCCESS! База данных успешно дополнена новыми записями.")
    print(f"Общее количество объектов в ChromaDB: {collection.count()}")

if __name__ == "__main__":
    build_database()
