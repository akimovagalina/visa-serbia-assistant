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




import asyncio
import json
import os
from datetime import datetime, timedelta
from telethon import TelegramClient, types
from telethon.network import ConnectionTcpFull

# --- SECURITY & CONNECTION CONFIGURATION ---
# Note: On GitHub Actions, we will load these safely via environment variables
API_ID = 30357945  # Ваш api_id (без кавычек)
API_HASH = '961e31729ed16cb961df6e9632a47fe2'  # Ваш api_hash в кавычках
# Ссылка или юзернейм группы-форума (например, 'visa_forum')
CHANNEL_USERNAME = 'https://t.me/+fIZUn78R5SUzYjhi' 
OUTPUT_FILE = 'raw_visa_data.json'

async def main():
    # We use a fixed session name. The file 'visa_session.session' must be uploaded to GitHub!
    client = TelegramClient('visa_session', API_ID, API_HASH, connection=ConnectionTcpFull)
    
    print("Connecting to Telegram...")
    await client.start()
    print("Successfully authorized!")

    cleaned_data = []
    existing_ids = set()
    min_id_filter = 0

    # INCREMENTAL DETECTION: Load existing database if present
    if os.path.exists(OUTPUT_FILE):
        print(f"🔄 Found existing {OUTPUT_FILE}. Loading historical records...")
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                cleaned_data = json.load(f)
                existing_ids = {msg['id'] for msg in cleaned_data}
                if cleaned_data:
                    # Find the highest ID we have so we only look for newer messages
                    min_id_filter = max(existing_ids)
                    print(f"📈 Highest indexed message ID: {min_id_filter}. Fetching new updates...")
        except Exception as e:
            print(f"⚠️ Failed to parse existing JSON: {e}. Falling back to clean pull.")
            cleaned_data = []

    try:
        channel_entity = await client.get_entity(CHANNEL_USERNAME)
        print("Fetching latest updates from chat...")

        # If it's a clean run, we pull 30 days. If incremental, we pull up to 300 new messages.
        limit_to_fetch = 300 if min_id_filter > 0 else 3000
        posts = await client.get_messages(channel_entity, limit=limit_to_fetch)
        
        new_records_count = 0

        for post in reversed(posts): # Process oldest to newest to maintain correct order
            if not post.text or post.id in existing_ids:
                continue
            
            # Skip messages older than our highest tracked ID
            if post.id <= min_id_filter:
                continue

            # Skip messages older than 1 year on a fresh installation fallback
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
            print(f"💾 Saving database array to disk. Added {new_records_count} new messages.")
            # Sort everything chronologically by message ID
            cleaned_data.sort(key=lambda x: x['id'])
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
        else:
            print("💤 No new visa updates detected in the channel.")

        print(f"🎉 Process completed. Total entries in archive: {len(cleaned_data)}")

    except Exception as e:
        print(f"❌ Error during scrape: {e}")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
