import asyncio
import json
import os
from datetime import datetime, timedelta
from telethon import TelegramClient, types
from telethon.network import ConnectionTcpFull

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ И ПОДКЛЮЧЕНИЯ ---
API_ID = 30357945  # Ваш api_id (без кавычек)
API_HASH = '961e31729ed16cb961df6e9632a47fe2'  # Ваш api_hash в кавычках
# Ссылка или юзернейм группы-форума (например, 'visa_forum')
CHANNEL_USERNAME = 'https://t.me/+fIZUn78R5SUzYjhi' 
OUTPUT_FILE = 'raw_visa_data.json'

# НАСТРОЙКА ВРЕМЕННОЙ ГРАНИЦЫ (полгода от сегодняшнего дня)
_AGO = datetime.now() - timedelta(days=0.5 * 365)

async def main():
    client = TelegramClient('visa_session', API_ID, API_HASH, connection=ConnectionTcpFull)
    
    print("Подключаемся к Telegram...")
    await client.start()
    print("Успешно авторизовано!")

    print(f"📅 Ищем сообщения строго до: {_AGO.strftime('%Y-%m-%d')}")
    cleaned_data = []
    offset_id = 0
    batch_count = 1
    stop_download = False

    try:
        channel_entity = await client.get_entity(CHANNEL_USERNAME)
        print("Начинаем умное скачивание архива за полгода..")

        while not stop_download:
            print(f"📥 Скачиваем батч #{batch_count} (Уже собрано: {len(cleaned_data)})...")
            
            posts = await client.get_messages(channel_entity, limit=100, offset_id=offset_id)
            
            if not posts:
                print("🏁 Достигли самого начала канала раньше, чем прошли 6 месяцев.")
                break

            for post in posts:
                if not post.text:
                    continue
                
                # ПРОВЕРКА ДАТЫ: если сообщение старее, чем полгода назад — останавливаемся!
                # Убираем временную зону у даты поста для корректного сравнения
                post_date_naive = post.date.replace(tzinfo=None)
                if post_date_naive < _AGO:
                    print(f"🛑 Наткнулись на сообщение от {post_date_naive.strftime('%Y-%m-%d')}. Граница в 6 месяцев пройдена!")
                    stop_download = True
                    break # Выходим из цикла обработки сообщений

                # По умолчанию считаем, что связей нет
                reply_to_id = None
                forum_topic_id = None

                if post.reply_to and isinstance(post.reply_to, types.MessageReplyHeader):
                    # reply_to_msg_id — это всегда ID конкретного сообщения-ответа
                    reply_to_id = post.reply_to.reply_to_msg_id
                    # reply_to_top_id — присутствует только если это форум с темами
                    forum_topic_id = post.reply_to.reply_to_top_id

                post_info = {
                    "id": post.id,
                    "reply_to_id": reply_to_id,  # Теперь мы точно знаем ID вопроса!
                    "forum_topic_id": forum_topic_id, # А тут будет ID топика, если он есть
                    "date": post.date.strftime("%Y-%m-%d %H:%M:%S"),
                    "text": post.text,
                    "views": post.views if post.views else 0
                }

                cleaned_data.append(post_info)

            # Переходим к следующей порции данных
            offset_id = posts[-1].id
            batch_count += 1
            
            # Небольшая пауза, чтобы Telegram не ругался
            await asyncio.sleep(0.5)

        # ОДНОКРАТНОЕ СОХРАНЕНИЕ: записываем весь массив на диск только в самом конце
        print("💾 Записываем финальный массив данных на жесткий диск...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

        print(f"\n🎉 УСПЕХ! Скачивание за 2 года завершено.")
        print(f"Всего актуальных сообщений сохранено: {len(cleaned_data)}")

    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
