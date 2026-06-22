import asyncio
import json
import os
from datetime import datetime, timedelta
from telethon import TelegramClient, types
from telethon.network import ConnectionTcpFull

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ И ПОДКЛЮЧЕНИЯ ---
#TG_API_ID = 30357945  # Ваш api_id (без кавычек)
# TG_API_HASH  = '961e31729ed16cb961df6e9632a47fe2'  # Ваш api_hash в кавычках
# --- НАСТРОЙКИ БЕЗОПАСНОСТИ И ПОДКЛЮЧЕНИЯ ---
# На сервере GitHub переменные считываются из настроек Secrets.
# Для запуска на Mac скрипт подставит дефолтные значения (замените 12345 и 'hash' на свои, если запускаете локально)
TG_API_ID = int(os.environ.get("TG_API_ID"))
TG_API_HASH = os.environ.get("TG_API_HASH")

CHANNEL_USERNAME = 'https://t.me/+fIZUn78R5SUzYjhi' 
OUTPUT_FILE = 'raw_visa_data.json'

async def main():
    # Используем фиксированное имя сессии. Файл 'visa_session.session' должен лежать рядом!
    client = TelegramClient('visa_session', TG_API_ID, TG_API_HASH, connection=ConnectionTcpFull)
    
    print("Подключаемся к Telegram...")
    await client.start()
    print("Успешно авторизовано!")

    cleaned_data = []
    existing_ids = set()
    min_id_filter = 0

    # УМНАЯ ДОЗАПИСЬ: Если файл уже есть, читаем его, чтобы узнать последнее сообщение
    if os.path.exists(OUTPUT_FILE):
        print(f"🔄 Найден существующий файл {OUTPUT_FILE}. Загружаем историю...")
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                cleaned_data = json.load(f)
                existing_ids = {msg['id'] for msg in cleaned_data}
                if cleaned_data:
                    # Находим максимальный ID сообщения, который у нас уже есть
                    min_id_filter = max(existing_ids)
                    print(f"📈 Последний проиндексированный ID сообщения: {min_id_filter}. Ищем только новинки...")
        except Exception as e:
            print(f"⚠️ Не удалось прочитать существующий JSON: {e}. Начинаем чистую выгрузку.")
            cleaned_data = []

    try:
        channel_entity = await client.get_entity(CHANNEL_USERNAME)
        print("Запрашиваем обновления из чата...")

        # Если это дозапись, берем до 300 свежих сообщений. Если чистый запуск — до 3000.
        limit_to_fetch = 300 if min_id_filter > 0 else 3000
        posts = await client.get_messages(channel_entity, limit=limit_to_fetch)
        
        new_records_count = 0

        # Перебираем сообщения от старых к новым
        for post in reversed(posts):
            if not post.text or post.id in existing_ids:
                continue
            
            # Пропускаем всё, что старее нашего сохраненного максимума
            if post.id <= min_id_filter:
                continue

            # При чистом запуске (с нуля) ограничиваем глубину архива 1 годом
            post_date_naive = post.date.replace(tzinfo=None)
            if min_id_filter == 0 and post_date_naive < (datetime.now() - timedelta(days=365)):
                continue

            reply_to_id = None
            forum_topic_id = None

            if post.reply_to and isinstance(post.reply_to, types.MessageReplyHeader):
                reply_to_id = post.reply_to.reply_to_msg_id
                forum_topic_id = post.reply_to.reply_to_top_id

            post_info = {
                "id": post.id,
                "reply_to_id": reply_to_id,
                "forum_topic_id": forum_topic_id,
                "date": post.date.strftime("%Y-%m-%d %H:%M:%S"),
                "text": post.text,
                "views": post.views if post.views else 0
            }
            cleaned_data.append(post_info)
            new_records_count += 1

        if new_records_count > 0:
            print(f"💾 Сохраняем обновленный массив на диск. Добавлено новых сообщений: {new_records_count}")
            # Сортируем весь массив по ID сообщений (от старых к новым)
            cleaned_data.sort(key=lambda x: x['id'])
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
        else:
            print("💤 Новых сообщений в визовом чате не обнаружено.")

        print(f"🎉 Процесс завершен. Всего сообщений в архиве: {len(cleaned_data)}")

    except Exception as e:
        print(f"❌ Произошла ошибка при скачивании данных: {e}")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
