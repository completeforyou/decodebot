from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden
from telegram.ext import ContextTypes, ConversationHandler
from core.config import logger
from services import users as user_service
from services import files as file_service
from core.security import require_subscription

WAITING_FOR_KEYWORD = 1

@require_subscription
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await user_service.add_or_update_user(user_id, update.effective_user.username)
    user_record = await user_service.get_user(user_id)
    
    if not user_record:
        await update.message.reply_text("Error loading user profile.")
        return ConversationHandler.END

    is_premium = user_record.is_premium
    credits_left = user_record.search_credits

    # Block if out of credits
    if not is_premium and credits_left <= 0:
        await update.message.reply_text(
            "🔒 搜索次数已用完！\n\n"
            "您已用完所有免费次数。请升级为高级会员以继续搜索。"
        )
        return ConversationHandler.END

    credit_msg = f"\n(您还有 {credits_left} 次免费使用次数)" if not is_premium else "\n您已经是高级会员,享受无限搜索和解码"

    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ 取消搜索", callback_data="search_cancel")
    ]])

    await update.message.reply_text(
       f"请输入要搜索的关键词。{credit_msg}\n\n"
        "或点击下方按钮取消",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return WAITING_FOR_KEYWORD

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches random videos and uses the search pagination to display them."""
    user_id = update.effective_user.id
    await user_service.add_or_update_user(user_id, update.effective_user.username)
    
    # Check credits
    user_record = await user_service.get_user(user_id)
    if not user_record:
        await update.message.reply_text("Error loading user profile.")
        return 

    is_premium = user_record.is_premium
    credits_left = user_record.search_credits

    # Block if out of credits
    if not is_premium and credits_left <= 0:
        await update.message.reply_text(
            "🔒 搜索次数已用完！\n\n"
            "您已用完所有免费搜索次数,请升级为高级会员以继续搜索"
        )
        return 

    try:
        results = await file_service.get_random_files(limit=20) # Fetches 20 random videos
    except Exception as e:
        logger.error(f"Database random fetch error: {e}")
        await update.message.reply_text("发生错误，请稍后再试")
        return 
        
    if not results:
        await update.message.reply_text("数据库中暂无可用视频")
        return 
    
    if not is_premium:
        await user_service.use_search_credit(user_id)

    lightweight_results = [
        {'code': r.code, 'channel_id': r.channel_id, 'message_id': r.message_id} 
        for r in results
    ]
        
    # Reuse the search state variables to magically enable your pagination!
    context.user_data['search_results'] = lightweight_results
    context.user_data['search_index'] = 0
    context.user_data['search_keyword'] = "🎲 Random Discovery"
    
    await send_search_page(update, context)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.pop('search_results', None)
    context.user_data.pop('search_index', None)
    context.user_data.pop('search_keyword', None)

    await update.message.reply_text("搜索已取消")
    return ConversationHandler.END

async def perform_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Keep the raw text. We don't force it to lowercase because ILIKE in Postgres handles that automatically!
    keyword = update.message.text.strip()
    user_id = update.effective_user.id
    
    try:
        # Call the new fuzzy search method
        results = await file_service.search_by_keyword(keyword)
    except Exception as e:
        logger.error(f"Database search error: {e}")
        await update.message.reply_text("An error occurred while searching. Please try again.")
        return ConversationHandler.END
        
    if not results:
        await update.message.reply_text(f"未找到包含 '{keyword}' 的视频")
        return ConversationHandler.END
    
    user_record = await user_service.get_user(user_id)
    if user_record and not user_record.is_premium:
        await user_service.use_search_credit(user_id)

    lightweight_results = [
        {'code': r.code, 'channel_id': r.channel_id, 'message_id': r.message_id} 
        for r in results
    ]
        
    context.user_data['search_results'] = lightweight_results
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
        f"🔍 关键词 {keyword}:\n"
        f"📄 结果: {index + 1}/{total}个视频\n"
        f"🔑 提取码: {current_record['code']}"
    )
    
    keyboard = []
    nav_row = []
    
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data="search_prev"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data="search_next"))
        
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton("📥 发送视频", callback_data="search_send")])
    keyboard.append([InlineKeyboardButton("❌ 关闭搜索", callback_data="search_close")])
    
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
            await query.message.reply_text("搜索会话已过期。请重新开始 /search")
            return
        record = results[index]
        user_id = update.effective_user.id
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=record['channel_id'],
                message_id=record['message_id'],
                protect_content=True
            )

        except Forbidden:
            # Specifically catch the block error
            logger.warning(f"User {user_id} blocked the bot. Marking as inactive.")
            await user_service.deactivate_user(user_id)
            await query.answer("Delivery failed: Please unblock the bot.", show_alert=True)
        except Exception as e:
            logger.error(f"Copy message error: {e}")
            await query.message.reply_text("发送视频时发生错误,视频可能已被删除")
        return

    if data == "search_next":
        context.user_data['search_index'] += 1
    elif data == "search_prev":
        context.user_data['search_index'] -= 1
        
    await send_search_page(update, context, is_callback=True)

async def cancel_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理内联取消按钮的点击事件"""
    query = update.callback_query
    await query.answer() 
    
    # remove search state from user_data to effectively cancel the search session
    context.user_data.pop('search_results', None)
    context.user_data.pop('search_index', None)
    context.user_data.pop('search_keyword', None)

    # refresh the message to remove the inline buttons and show cancellation
    await query.edit_message_text("搜索已取消 ✅")
    return ConversationHandler.END