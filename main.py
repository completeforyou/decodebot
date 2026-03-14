from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from core.config import BOT_TOKEN, DATABASE_URL, CHANNEL_IDS, logger
from database import Database
from handlers.base_handlers import profile_command, start_command, handle_user_message
from handlers.admin_handlers import (
    handle_channel_post, add_premium_command, handle_admin_forward, 
    edit_tags_command, delete_file_command)
from handlers.search_handlers import (
    search_command, cancel_command, perform_search, 
    handle_search_callbacks, WAITING_FOR_KEYWORD, random_command
)

db = Database(DATABASE_URL)

async def post_init(application: Application):
    logger.info("Connecting to Database...")
    await db.connect()
    application.bot_data['db'] = db

async def post_stop(application: Application):
    logger.info("Closing Database...")
    await db.close()

def main():
    if not BOT_TOKEN or not DATABASE_URL or not CHANNEL_IDS:
        logger.error("CRITICAL ERROR: Missing environment variables.")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).post_stop(post_stop).build()

    search_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("search", search_command)],
        states={
            WAITING_FOR_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, perform_search)]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )

    # Register Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("addp", add_premium_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("edittags", edit_tags_command))
    app.add_handler(CommandHandler("deletefile", delete_file_command))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    app.add_handler(search_conv_handler)
    app.add_handler(CallbackQueryHandler(handle_search_callbacks, pattern="^search_"))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.FORWARDED, handle_admin_forward))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_user_message))

    app.run_polling()

if __name__ == '__main__':
    main()