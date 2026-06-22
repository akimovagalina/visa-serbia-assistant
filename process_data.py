import json
import os
import time

INPUT_FILE = 'raw_visa_data.json'
OUTPUT_FILE = 'processed_visa_data.json'

# FULL AND VERIFIED TOPIC MAPPING
TOPIC_MAPPING = {
    14535: "Венгрия",
    14534: "Италия",
    20735: "Германия",
    14530: "Франция",
    60101: "Япония",
    20803: "Великобритания",
    20883: "Австрия",
    22678: "Кипр",
    53826: "Македония",
    20724: "Португалия",
    143189: "Португалия",
    39183: "Болгария",
    104035: "Польша",
    20730: "Словения",
    37109: "Греция",
    20721: "США",
    60078: "Словакия",
    20731: "Финляндия",
    347898: "Общие правила",
    197543: "Оповещения о слотах",
    29756: "Страховки",
    25835: "Хорватия",
    53824: "Албания",
    20743: "Нидерланды",
    128590: "Китай",
    29754: "Швейция",  
    20894: "Швейцария"  
}

def clean_and_tag_visa_data():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: File {INPUT_FILE} not found. Run get_telegram_data.py first.")
        return

    print("⏳ Loading raw records into memory...")
    start_time = time.time()
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        raw_messages = json.load(f)

    print(f"🔄 Transforming {len(raw_messages)} records safely...")
    processed_data = []

    for msg in raw_messages:
        text = msg.get('text', '')
        text_lower = text.lower()
        
        # Поддерживаем оба варианта ключа топика форума для стабильности
        tid = msg.get('forum_topic_id') or msg.get('topic_id', 0)

        # Строгое определение страны по номеру темы
        country = TOPIC_MAPPING.get(tid, f"Other Discussions (ID: {tid})" if tid != 0 else "Main Chat")

        # ---УМНАЯ ФИЛЬТРАЦИЯ СТРАН (БЕЗ СЛЕПОЙ ПЕРЕЗАПИСИ)---
        # Меняем страну ТОЛЬКО если это была общая ветка (Main Chat)
        # Если сообщение уже лежит в ветке "Италия", мы НЕ отнимаем у него эту страну из-за упоминания Германии.
        if country in ["Main Chat", "Общие правила"]:
            if "итали" in text_lower:
                country = "Италия"
            elif "германи" in text_lower:
                country = "Германия"
            elif "франц" in text_lower:
                country = "Франция"

        # Классификация типов сообщений
        msg_type = "General Discussion"
        if "#одобрено" in text_lower or "визу дали" in text_lower or "получил визу" in text_lower:
            msg_type = "Successful Visa Approval Case"
        elif any(word in text_lower for word in ["слот", "запись", "календарь", "поймал", "взял"]):
            msg_type = "Slot Availability Intel"

        # Формируем чистую запись
        clean_entry = {
            "id": msg.get("id", 0),
            "reply_to_id": msg.get("reply_to_id", None),  # <-- ОБЯЗАТЕЛЬНО: передаем связь дальше в базу
            "date": msg.get("date", ""),
            "country": country,
            "type": msg_type,
            "text": text.strip()
        }
        processed_data.append(clean_entry)

    print("💾 Writing structured dataset to disk...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=4, ensure_ascii=False)

    end_time = time.time()
    print(f"\n🎉 SUCCESS! Structured {len(processed_data)} messages in {end_time - start_time:.2f} seconds.")
    print(f"Clean structured data saved to: {os.path.abspath(OUTPUT_FILE)}")

if __name__ == "__main__":
    clean_and_tag_visa_data()
