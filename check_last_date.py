import chromadb

DB_DIR = './chroma_db'

def get_last_date():
    print("📦 Подключение к локальной базе ChromaDB...")
    chroma_client = chromadb.PersistentClient(path=DB_DIR)
    collection = chroma_client.get_collection(name="visa_assistant")
    
    # Запрашиваем из базы абсолютно все метаданные
    results = collection.get()
    
    if not results or not results.get('metadatas'):
        print("❌ База данных пуста или не найдена.")
        return
        
    metadatas = results['metadatas']
    
    # Собираем все даты из метаданных постов
    all_dates = [meta.get('date') for meta in metadatas if meta.get('date')]
    
    if not all_dates:
        print("⚠️ Сообщения есть, но даты в метаданных отсутствуют.")
        return
        
    # Находим самую свежую дату в списке
    last_date = max(all_dates)
    
    print("=" * 50)
    print(f"📊 Всего сообщений в векторной базе: {len(metadatas)}")
    print(f"📅 Дата самого свежего сообщения в базе: {last_date}")
    print("=" * 50)

if __name__ == "__main__":
    get_last_date()
