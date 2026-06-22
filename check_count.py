import chromadb

DB_DIR = './chroma_db'

def check_database_count():
    # Подключаемся к вашей локальной папке с базой
    chroma_client = chromadb.PersistentClient(path=DB_DIR)
    
    try:
        # Открываем вашу коллекцию
        collection = chroma_client.get_collection(name="visa_assistant")
        
        # Получаем количество записей
        total_records = collection.count()
        
        print("\n📊 Статистика вашей базы данных ChromaDB:")
        print("=" * 45)
        print(f"Имя коллекции:  visa_assistant")
        print(f"Всего строк (векторов) в базе: {total_records}")
        print("=" * 45)
        
    except Exception as e:
        print(f"❌ Ошибка: Не удалось прочитать коллекцию. Возможно, база пуста или папка повреждена. {e}")

if __name__ == "__main__":
    check_database_count()
