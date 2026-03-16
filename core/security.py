# Future home for paywall decorators, user tracking, and premium checks!# decodebot/core/security.py

from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.config import ADMIN_IDS, logger, FORCE_JOIN_CHANNELS
from services import features as feature_service

def admin_only(func):
    """Decorator to restrict commands to admins only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            logger.warning(f"Unauthorized access attempt to admin command by user {user_id}")
            await update.message.reply_text("❌ You do not have permission to use this command.")
            return # Block execution
            
        # If they are an admin, proceed with the original function
        return await func(update, context, *args, **kwargs)
        
    return wrapper

def require_subscription(func):
    """Decorator to force users to join specific channels before using the bot."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not FORCE_JOIN_CHANNELS:
            return await func(update, context, *args, **kwargs)

        user_id = update.effective_user.id
        not_joined_links = []

        for channel in FORCE_JOIN_CHANNELS:
            try:
                # Check the user's status in the channel
                member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
                
                # 'left' means they haven't joined, 'kicked' means they are banned
                if member.status in ['left', 'kicked']:
                    # Try to get channel details to build an invite button
                    chat = await context.bot.get_chat(channel)
                    invite_link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
                    
                    if invite_link:
                        title = chat.title or "Our Channel"
                        not_joined_links.append((title, invite_link))
            except Exception as e:
                logger.error(f"Failed to check membership for {channel}. Is bot an admin? Error: {e}")

        # If they are missing from any channels, send the prompt and block the function
        if not_joined_links:
            keyboard = [
                [InlineKeyboardButton(f"📢 Join {title}", url=link)] 
                for title, link in not_joined_links
            ]
            keyboard.append([InlineKeyboardButton("🔄 I have joined!", callback_data="check_sub")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = "⚠️ **Access Denied**\n\nYou must join our official channels to use this bot!"
            
            if update.message:
                await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer("Please join the channels first!", show_alert=True)
                
            return # Stop execution here, don't run the actual command

        # If they are in all channels, proceed to the actual handler
        return await func(update, context, *args, **kwargs)
    return wrapper

def require_feature(feature_name: str):
    """Decorator to check if a specific feature switch is turned on."""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Check the status of the feature
            is_active = await feature_service.get_feature_status(feature_name)
            
            if not is_active:
                # If disabled, politely inform the user and stop execution
                message_text = f"🚧 **Maintenance Mode**\n\nThe `{feature_name}` feature is currently disabled by administrators. Please try again later."
                
                if update.callback_query:
                    await update.callback_query.answer(f"The {feature_name} feature is currently disabled.", show_alert=True)
                elif update.message:
                    await update.message.reply_text(message_text, parse_mode="Markdown")
                    
                return # Block the execution of the command
                
            # If enabled, proceed normally
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator