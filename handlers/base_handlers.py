# handlers/base_handlers.py
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden
from services import users as user_service
from services import files as file_service
from core.config import logger, ADMIN_IDS
from core.security import require_subscription

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    args = context.args
    referrer_id = None
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].split("_")[1])
        except ValueError:
            pass
    
    if user:
        is_new_user = await user_service.add_or_update_user(user.id, user.username)
        
        if is_new_user and referrer_id and referrer_id != user.id:
            success = await user_service.process_referral(user.id, referrer_id)
            if success:
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id, 
                        text=f"🎉 **New Referral!**\nSomeone joined using your link. You've earned **5 search credits**!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify referrer {referrer_id}: {e}")

    # 1. Build the default keyboard for all users
    keyboard = [
        [KeyboardButton("🔍 搜索"), KeyboardButton("🎲 随机")],
        [KeyboardButton("📅 签到"), KeyboardButton("👤 个人")]
    ]
    
    # 2. Add an Admin menu conditionally
    if user and user.id in ADMIN_IDS:
        keyboard.append([KeyboardButton("⚙️ Admin: Channels"), KeyboardButton("⚙️ Admin: Broadcast")])
        
    # 3. Create the markup (resize_keyboard makes it smaller and neater)
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        is_persistent=True, # Keeps the keyboard open
        input_field_placeholder="Select an option or send a code..."
    )

    welcome_text = (
        "请输入提取码以获取文件，或使用 /search 关键词 来搜索相关文件\n\n"
    )
    await update.message.reply_text(welcome_text)

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await user_service.add_or_update_user(user_id, update.effective_user.username)
    
    success, message = await user_service.process_checkin(user_id)
    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"⚠️ {message}")

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    text = (
        f"🎁 **Invite Friends & Earn Credits!**\n\n"
        f"Share your unique referral link with friends. When they start the bot using your link for the first time, you will receive **5 free search credits**!\n\n"
        f"🔗 Your link:\n`{referral_link}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

@require_subscription
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    
    if not user_text.lower().startswith('rad_'):
        await update.message.reply_text("Please enter a correct code.")
        return

    user_id = update.effective_user.id
    await user_service.add_or_update_user(user_id, update.effective_user.username)

    user_record = await user_service.get_user(user_id)
    if not user_record:
        await update.message.reply_text("Error loading user profile.")
        return

    if not user_record.is_premium and user_record.search_credits <= 0:
        await update.message.reply_text(
            "🔒 **Out of Credits!**\n\n"
            "You have used all your free requests. Please upgrade to Premium to continue downloading files."
        )
        return

    try:
        file_record = await file_service.get_file(user_text) 
    except Exception as e:
        logger.error(f"Database query error: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")
        return

    if file_record:
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=file_record.channel_id,
                message_id=file_record.message_id,
                protect_content=True
            )
            if not user_record.is_premium:
                success = await user_service.use_search_credit(user_id)
                if not success:
                    await update.message.reply_text("Failed to deduct credit. You might be out of credits.")
                    return
        except Forbidden:
            # Specifically catch the block error
            logger.warning(f"User {user_id} blocked the bot. Marking as inactive.")
            await user_service.deactivate_user(user_id)        
        except Exception as e:
            logger.error(f"Copy message error: {e}")
            await update.message.reply_text("Failed to send. The file might be deleted.")
    else:
        await update.message.reply_text("File not found.")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await user_service.add_or_update_user(user_id, update.effective_user.username)
    
    user_record = await user_service.get_user(user_id)
    if not user_record:
        await update.message.reply_text("Error loading profile.")
        return
        
    if user_record.is_premium:
        status_text = "🌟 **Premium Member** (Unlimited Searches & Downloads)"
    else:
        status_text = f"🆓 **Basic Member** ({user_record.search_credits} free credits remaining)"
        
    profile_message = (
        f"👤 **Your Profile**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"**ID:** `{user_id}`\n"
        f"**Status:** {status_text}\n\n"
        f"*(Use credits to /search or download files using codes)*"
    )
    
    await update.message.reply_text(profile_message, parse_mode="Markdown")