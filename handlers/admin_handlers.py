import random
import string
from telegram import Update
from telegram.constants import MessageOriginType
from telegram.ext import ContextTypes
from core.config import CHANNEL_IDS, logger
from core.security import admin_only

def generate_code(length=10):
    # Generates 'rad_' followed by 10 random letters (both upper and lowercase)
    random_letters = ''.join(random.choices(string.ascii_letters, k=length))
    return f"rad_{random_letters}"

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

    # The feedback message block has been removed here to prevent rate-limiting!

@admin_only
async def add_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grants premium status to a specific user ID."""
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/addp <user_id>`", parse_mode="Markdown")
        return
        
    try:
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

@admin_only
async def handle_admin_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches messages forwarded by admins and returns the file info."""
    msg = update.message
    
    # Check if the message is forwarded specifically from a channel
    if not msg.forward_origin or msg.forward_origin.type != MessageOriginType.CHANNEL:
        await msg.reply_text("⚠️ Please forward a message directly from the channel.")
        return
        
    original_chat_id = msg.forward_origin.chat.id
    original_message_id = msg.forward_origin.message_id
    
    db = context.bot_data['db']
    
    # Look up the file using the original IDs
    record = await db.files.get_file_by_origin(original_message_id, original_chat_id)
    
    if not record:
        await msg.reply_text("❌ This forwarded file is not in the database. It may have been deleted or never registered.")
        return
        
    tags_str = ", ".join(record['tags']) if record['tags'] else "No tags"
    code = record['code']
    
    reply_text = (
        f"📄 **File Found!**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"**Code:** `{code}`\n"
        f"**Tags:** {tags_str}\n\n"
        f"*(You can now use `/edittags {code} #newtag` or `/deletefile {code}`)*"
    )
    
    await msg.reply_text(reply_text, parse_mode="Markdown")