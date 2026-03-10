# Future home for paywall decorators, user tracking, and premium checks!# decodebot/core/security.py

from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from core.config import ADMIN_IDS, logger

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