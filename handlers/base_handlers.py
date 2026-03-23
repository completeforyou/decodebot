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
                        text=f"🎉 新邀请！\n有人通过您的链接加入了。您获得了 5个搜索积分!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify referrer {referrer_id}: {e}")

    # 1. Build the default keyboard for all users
    keyboard = [
        [KeyboardButton("🎁 邀请")], #[KeyboardButton("🔍 搜索"), KeyboardButton("🎁 邀请"), KeyboardButton("🎲 随机")]
        [KeyboardButton("📅 签到"), KeyboardButton("👤 个人")]
    ]
    
    # 2. Add an Admin menu conditionally
    if user and user.id in ADMIN_IDS:
        keyboard.append([KeyboardButton("⚙️ 管理:频道"), KeyboardButton("⚙️ 管理:广播")])
        
    # 3. Create the markup (resize_keyboard makes it smaller and neater)
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        is_persistent=True, # Keeps the keyboard open
        input_field_placeholder="选择一个选项或发送提取码..."
    )

    welcome_text = (
        "请输入提取码以获取文件\n\n"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

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
        f"🎁 邀请朋友并赚取积分！\n\n"
        f"与朋友分享您的邀请链接。当他们首次使用您的链接启动机器人时，您将获得 5 个免费积分！\n\n"
        f"🔗 您的链接:\n`{referral_link}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

@require_subscription
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    
    if not user_text.lower().startswith('maoxi_') or user_text.lower().startswith('rad_'):
        await update.message.reply_text("请输入正确的提取码.")
        return

    user_id = update.effective_user.id
    await user_service.add_or_update_user(user_id, update.effective_user.username)

    user_record = await user_service.get_user(user_id)
    if not user_record:
        await update.message.reply_text("Error loading user profile.")
        return

    if not user_record.is_premium and user_record.search_credits <= 0:
        await update.message.reply_text(
            "🔒 积分不足！\n\n"
            "您已用完所有免费次数。请升级到 会员 以获得无限观看，或者继续邀请朋友赚取更多积分！\n\n"
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
                    await update.message.reply_text("您的积分可能已用完")
                    return
        except Forbidden:
            # Specifically catch the block error
            logger.warning(f"User {user_id} blocked the bot. Marking as inactive.")
            await user_service.deactivate_user(user_id)        
        except Exception as e:
            logger.error(f"Copy message error: {e}")
            await update.message.reply_text("发送失败。文件可能已被删除.")
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
        status_text = "🌟 会员 (无限搜索和下载)"
    else:
        status_text = f"🆓 普通会员 (剩余{user_record.search_credits} 个免费积分)"
        
    profile_message = (
        f"👤 个人资料\n"
        f"━━━━━━━━━━━━━━━\n"
        f"ID: `{user_id}`\n"
        f"状态: {status_text}\n\n"
        f"(使用积分进行 /search 搜索或使用提取码下载文件)"
    )
    
    await update.message.reply_text(profile_message, parse_mode="Markdown")