import random
import string
from telegram import Update
from telegram.ext import ContextTypes
from core.config import CHANNEL_IDS, logger
from core.security import admin_only

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
    
    final_code = None
    for attempt in range(3):
        new_code = generate_code()
        try:
            final_code = await db.files.insert_file(new_code, msg.message_id, msg.chat.id, tags)
            break # Success! Break out of the loop
        except Exception as e:
            logger.warning(f"Insert attempt {attempt + 1} failed (possible code collision): {e}")
            
    if not final_code:
        logger.error("Failed to insert file after 3 attempts.")
        return

    tags_str = ", ".join(tags) if tags else "None"
    await context.bot.send_message(
        chat_id=msg.chat.id,
        text=f"Stored successfully.\nCode: {final_code}\nTags detected: {tags_str}",
        reply_to_message_id=msg.message_id
    )
@admin_only
async def add_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grants premium status to a specific user ID."""
    
    # context.args contains a list of words typed after the command
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/addp <user_id>`", parse_mode="Markdown")
        return
        
    try:
        # Convert the typed ID into an integer
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid numeric user ID.")
        return
        
    db = context.bot_data['db']
    
    try:
        await db.users.make_premium(target_user_id)
        await update.message.reply_text(f"✅ Success! User `{target_user_id}` has been upgraded to Premium.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error upgrading user to premium: {e}")
        await update.message.reply_text("❌ An error occurred. Make sure that user ID exists in the database.")  