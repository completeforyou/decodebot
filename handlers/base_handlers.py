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
    # Keep the original case for strict matching, or convert to lowercase for easy checking
    user_text = update.message.text.strip()
    
    # Check if the code starts with 'rad_' (case-insensitive check)
    if not user_text.lower().startswith('rad_'):
        await update.message.reply_text("Please enter a correct code.")
        return

    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    # 1. Ensure user is registered
    await db.users.add_or_update_user(user_id, update.effective_user.username)

    # 2. Check credits
    user_record = await db.users.get_user(user_id)
    if not user_record:
        await update.message.reply_text("Error loading user profile.")
        return

    is_premium = user_record['is_premium']
    credits_left = user_record['search_credits']

    # 3. Block if out of credits
    if not is_premium and credits_left <= 0:
        await update.message.reply_text(
            "🔒 **Out of Credits!**\n\n"
            "You have used all your free requests. Please upgrade to Premium to continue downloading files."
        )
        return

    # 4. Fetch the file
    try:
        # Pass the exact text the user typed
        record = await db.files.get_file(user_text) 
    except Exception as e:
        logger.error(f"Database query error: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")
        return

    # 5. Send file and deduct credit
    if record:
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=record['channel_id'],
                message_id=record['message_id'],
                protect_content=True
            )
            # Deduct credit ONLY after successful delivery!
            if not is_premium:
                await db.users.use_search_credit(user_id)
                
        except Exception as e:
            logger.error(f"Copy message error: {e}")
            await update.message.reply_text("Failed to send. The file might be deleted.")
    else:
        # Changed from "Invalid extraction code." to "File not found."
        await update.message.reply_text("File not found.")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the user their current status and credits."""
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    # Make sure they exist in the DB
    await db.users.add_or_update_user(user_id, update.effective_user.username)
    
    user_record = await db.users.get_user(user_id)
    if not user_record:
        await update.message.reply_text("Error loading profile.")
        return
        
    is_premium = user_record['is_premium']
    credits_left = user_record['search_credits']
    
    if is_premium:
        status_text = "🌟 **Premium Member** (Unlimited Searches & Downloads)"
    else:
        status_text = f"🆓 **Basic Member** ({credits_left} free credits remaining)"
        
    profile_message = (
        f"👤 **Your Profile**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"**ID:** `{user_id}`\n"
        f"**Status:** {status_text}\n\n"
        f"*(Use credits to /search or download files using codes)*"
    )
    
    await update.message.reply_text(profile_message, parse_mode="Markdown")