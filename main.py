# main.py
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ConversationHandler, CallbackQueryHandler, ContextTypes
    )
from core.config import BOT_TOKEN, DATABASE_URL,logger, PORT, WEBHOOK_URL
from database import init_db
from handlers.base_handlers import (
    profile_command, start_command, handle_user_message, 
    checkin_command, referral_command,
)
from handlers.admin_handlers import (
    handle_channel_post, add_premium_command, handle_admin_forward, 
    edit_tags_command, delete_file_command, edit_caption_command,
    list_channels_command, add_channel_command, remove_channel_command, 
    toggle_command, broadcast_command,
)
from handlers.search_handlers import (
    search_command, cancel_command, perform_search, 
    handle_search_callbacks, WAITING_FOR_KEYWORD, random_command
)

async def post_init(application: Application):
    logger.info("Initializing Database schema...")
    await init_db()
    logger.info("Database ready!")

async def handle_sub_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Please try your command again now!", show_alert=True)
    await query.message.delete() # Cleans up the prompt

def main():
    if not BOT_TOKEN or not DATABASE_URL:
        logger.error("CRITICAL ERROR: Missing environment variables.")
        return

    app = (
    Application.builder()
    .token(BOT_TOKEN)
    .post_init(post_init)
    .build()
)

    search_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("search", search_command),
            MessageHandler(filters.Regex("^🔍 搜索$"), search_command) # Listens for the button
        ],
        states={
            WAITING_FOR_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, perform_search)]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )

    # User Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("checkin", checkin_command))  
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(MessageHandler(filters.Regex("^🎲 随机$"), random_command))
    app.add_handler(MessageHandler(filters.Regex("^📅 签到$"), checkin_command))
    app.add_handler(MessageHandler(filters.Regex("^👤 个人$"), profile_command))
    #admin handlers
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Admin: Channels$"), list_channels_command))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Admin: Broadcast$"), broadcast_command))
    app.add_handler(CommandHandler("addp", add_premium_command))
    app.add_handler(CommandHandler("edittags", edit_tags_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("editcaption", edit_caption_command))
    app.add_handler(CommandHandler("deletefile", delete_file_command))
    app.add_handler(CommandHandler("channels", list_channels_command))
    app.add_handler(CommandHandler("addchannel", add_channel_command))
    app.add_handler(CommandHandler("rmchannel", remove_channel_command))
    app.add_handler(CommandHandler("toggle", toggle_command))

    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    app.add_handler(search_conv_handler)
    app.add_handler(CallbackQueryHandler(handle_search_callbacks, pattern="^search_"))
    app.add_handler(CallbackQueryHandler(handle_sub_check, pattern="^check_sub$"))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.FORWARDED, handle_admin_forward))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_user_message))

    logger.info("Bot started via polling (Local mode)...")
    app.run_polling()
    
if __name__ == '__main__':
    main()