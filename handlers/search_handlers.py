from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from core.config import logger

WAITING_FOR_KEYWORD = 1

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please enter a keyword or tag to search for (e.g., 'action' or '#action').\n\n"
        "Or type /cancel to abort."
    )
    return WAITING_FOR_KEYWORD

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Search cancelled! Send me an extraction code whenever you're ready.")
    return ConversationHandler.END

async def perform_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip().lower()
    if not keyword.startswith('#'):
        keyword = '#' + keyword
        
    db = context.bot_data['db']
    
    try:
        results = await db.files.search_by_tag(keyword)
    except Exception as e:
        logger.error(f"Database search error: {e}")
        await update.message.reply_text("An error occurred while searching. Please try again.")
        return ConversationHandler.END
        
    if not results:
        await update.message.reply_text(f"No videos found for {keyword}.")
        return ConversationHandler.END
        
    context.user_data['search_results'] = results
    context.user_data['search_index'] = 0
    context.user_data['search_keyword'] = keyword
    
    await send_search_page(update, context)
    return ConversationHandler.END 

async def send_search_page(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    results = context.user_data.get('search_results', [])
    index = context.user_data.get('search_index', 0)
    keyword = context.user_data.get('search_keyword', '')
    
    if not results:
        return
        
    total = len(results)
    current_record = results[index]
    
    text = (
        f"🔍 Search results for {keyword}:\n"
        f"📄 Result {index + 1} of {total}\n"
        f"🔑 File Code: {current_record['code']}"
    )
    
    keyboard = []
    nav_row = []
    
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data="search_prev"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data="search_next"))
        
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton("📥 Send Video to Me", callback_data="search_send")])
    keyboard.append([InlineKeyboardButton("❌ Close Search", callback_data="search_close")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)

async def handle_search_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    data = query.data
    
    if data == "search_close":
        context.user_data.pop('search_results', None)
        await query.message.delete()
        return
        
    if data == "search_send":
        results = context.user_data.get('search_results', [])
        index = context.user_data.get('search_index', 0)
        if not results:
            await query.message.reply_text("Session expired. Please start a new /search.")
            return
        record = results[index]
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=record['channel_id'],
                message_id=record['message_id']
            )
        except Exception as e:
            logger.error(f"Copy message error: {e}")
            await query.message.reply_text("Failed to send. The file might be deleted.")
        return

    if data == "search_next":
        context.user_data['search_index'] += 1
    elif data == "search_prev":
        context.user_data['search_index'] -= 1
        
    await send_search_page(update, context, is_callback=True)