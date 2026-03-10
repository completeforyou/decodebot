from telegram import Update
from telegram.ext import ContextTypes
from core.config import logger

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = context.bot_data['db']
    
    # Save the user to the database
    if user:
        await db.users.add_or_update_user(user.id, user.username)
        
    await update.message.reply_text("请输入提取码以获取文件，或使用 /search 关键词 来搜索相关文件")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles private messages (users entering extraction codes)."""
    user_text = update.message.text.strip().upper()
    db = context.bot_data['db']
    
    try:
        # Notice we call db.files.get_file now!
        record = await db.files.get_file(user_text) 
    except Exception as e:
        logger.error(f"Database query error: {e}")
        await update.message.reply_text("发生错误，请重试")
        return

    if record:
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=record['channel_id'],
                message_id=record['message_id']
            )
        except Exception as e:
            logger.error(f"Copy message error: {e}")
            await update.message.reply_text("F提取失败，请稍后再试")
    else:
        await update.message.reply_text("无效的提取码，请检查后重试")