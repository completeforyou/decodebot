import random
import string
from telegram import Update
from telegram.ext import ContextTypes
from core.config import CHANNEL_IDS, logger

def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def extract_tags(message):
    tags = []
    if message.caption and message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == 'hashtag':
                tag = message.caption[entity.offset : entity.offset + entity.length]
                tags.append(tag.lower())
    return tags

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    db = context.bot_data['db']
    
    if not msg or msg.chat.id not in CHANNEL_IDS:
        return
        
    if not (msg.video or msg.photo or msg.document):
        return

    tags = extract_tags(msg)
    new_code = generate_code()
    
    try:
        final_code = await db.files.insert_file(new_code, msg.message_id, msg.chat.id, tags)
    except Exception as e:
        logger.error(f"Database insert error: {e}")
        return

    tags_str = ", ".join(tags) if tags else "None"
    await context.bot.send_message(
        chat_id=msg.chat.id,
        text=f"Stored successfully.\nCode: {final_code}\nTags detected: {tags_str}",
        reply_to_message_id=msg.message_id
    )