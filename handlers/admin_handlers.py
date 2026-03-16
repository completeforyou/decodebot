# handlers/admin_handlers.py
import random
import string
import asyncio
from telegram import Update
from telegram.constants import MessageOriginType
from telegram.ext import ContextTypes
from core.config import logger
from core.security import admin_only
from services import users as user_service
from services import files as file_service
from services import features as feature_service
from services import channels as channel_service

def generate_code(length=10):
    # Generates 'rad_' followed by 10 random letters (both upper and lowercase)
    random_letters = ''.join(random.choices(string.ascii_letters, k=length))
    return f"rad_{random_letters}"

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    
    if not msg:
        return
    
    is_approved = await channel_service.is_approved(msg.chat.id)
    if not is_approved:
        return
        
    if not (msg.video or msg.photo or msg.document):
        return

    # Grab the full caption, or use an empty string if there is no text
    caption = msg.caption if msg.caption else ""
    
    final_code = None
    for attempt in range(3):
        new_code = generate_code()
        try:
            # Using the new file_service
            final_code = await file_service.insert_file(new_code, msg.message_id, msg.chat.id, caption)
            break 
        except Exception as e:
            logger.warning(f"Insert attempt {attempt + 1} failed: {e}")
            
    if not final_code:
        logger.error("Failed to insert file after 3 attempts.")
        return

@admin_only
async def add_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grants premium status to a specific user ID."""
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/addp <user_id>`", parse_mode="Markdown")
        return
        
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid numeric user ID.")
        return
        
    try:
        # Using the new user_service
        success = await user_service.make_premium(target_user_id)
        if success:
            await update.message.reply_text(f"✅ Success! User `{target_user_id}` has been upgraded to Premium.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ User not found. They need to start the bot first.")
    except Exception as e:
        logger.error(f"Error upgrading user to premium: {e}")
        await update.message.reply_text("❌ An error occurred while upgrading the user.")

@admin_only
async def handle_admin_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches messages forwarded by admins and returns the file info."""
    msg = update.message
    
    if not msg.forward_origin or msg.forward_origin.type != MessageOriginType.CHANNEL:
        await msg.reply_text("⚠️ Please forward a message directly from the channel.")
        return
        
    original_chat_id = msg.forward_origin.chat.id
    original_message_id = msg.forward_origin.message_id
    
    # Using the new file_service
    record = await file_service.get_file_by_origin(original_message_id, original_chat_id)
    
    if not record:
        await msg.reply_text("❌ This forwarded file is not in the database.")
        return
        
    # Using attribute access (record.caption) instead of dict access (record['caption'])
    caption_text = record.caption
    if not caption_text:
        caption_text = "No caption"
    elif len(caption_text) > 100:
        caption_text = caption_text[:100] + "..."
        
    code = record.code
    
    reply_text = (
        f"📄 **File Found!**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"**Code:** `{code}`\n"
        f"**Caption:** {caption_text}\n\n"
        f"*(You can now use `/editcaption {code} <new text>` or `/deletefile {code}`)*"
    )
    
    await msg.reply_text(reply_text, parse_mode="Markdown")

@admin_only
async def edit_tags_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edits the tags of an existing file."""
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/edittags <code> #tag1 #tag2`", parse_mode="Markdown")
        return

    code = context.args[0]
    
    raw_tags = context.args[1:]
    tags = [tag.lower() if tag.startswith('#') else f"#{tag.lower()}" for tag in raw_tags]

    # Using the new file_service
    success = await file_service.update_tags(code, tags)

    if success:
        tags_str = ", ".join(tags)
        await update.message.reply_text(f"✅ Tags for `{code}` updated to: {tags_str}", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ File `{code}` not found. Please check the code.")

@admin_only
async def edit_caption_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edits the entire caption of an existing file."""
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/editcaption <code> <new caption text>`", parse_mode="Markdown")
        return

    code = context.args[0]
    new_caption = " ".join(context.args[1:])

    # Using the new file_service
    success = await file_service.update_caption(code, new_caption)

    if success:
        await update.message.reply_text(f"✅ Caption for `{code}` has been updated!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ File `{code}` not found. Please check the code.")

@admin_only
async def delete_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes a file from the database."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/deletefile <code>`", parse_mode="Markdown")
        return

    code = context.args[0]
    
    # Using the new file_service
    success = await file_service.delete_file(code)

    if success:
        await update.message.reply_text(f"✅ File `{code}` has been successfully deleted from the database.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ File `{code}` not found. Please check the code.")

@admin_only
async def toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to toggle features on or off."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: `/toggle <feature_name>`\n"
            "Example: `/toggle search` or `/toggle checkin`", 
            parse_mode="Markdown"
        )
        return

    # Grab the feature name from the command arguments and make it lowercase
    feature_name = context.args[0].lower()
    
    # Flip the switch!
    new_status = await feature_service.toggle_feature(feature_name)

    # Tell the admin the result
    status_text = "✅ ENABLED" if new_status else "❌ DISABLED"
    await update.message.reply_text(f"Feature `{feature_name}` is now **{status_text}**.", parse_mode="Markdown")

@admin_only
async def list_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all approved channels."""
    channels = await channel_service.get_all_channels()
    
    if not channels:
        await update.message.reply_text("No approved channels have been added yet.")
        return
        
    text = "📢 **Approved Channels:**\n\n"
    for cid, name in channels.items():
        text += f"• **{name}** (`{cid}`)\n"
        
    text += "\n*(Use `/addchannel` or `/rmchannel` to manage this list)*"
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adds a new channel."""
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/addchannel <channel_id> <channel_name>`\nExample: `/addchannel -100123456789 Main Channel`", parse_mode="Markdown")
        return
        
    try:
        channel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Channel ID must be a number.")
        return
        
    name = " ".join(context.args[1:])
    success = await channel_service.add_channel(channel_id, name)
    
    if success:
        await update.message.reply_text(f"✅ Successfully added **{name}** (`{channel_id}`) to approved channels.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ This channel is already in the database.")

@admin_only
async def remove_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Removes an existing channel."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/rmchannel <channel_id>`", parse_mode="Markdown")
        return
        
    try:
        channel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Channel ID must be a number.")
        return
        
    success = await channel_service.remove_channel(channel_id)
    
    if success:
        await update.message.reply_text(f"✅ Successfully removed `{channel_id}` from approved channels.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Channel not found in the database.")

import asyncio
# (Make sure to keep your other imports at the top)

@admin_only
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts a message (text, image, or video) to all active users."""
    
    # 1. Check if the admin is replying to a message they want to broadcast
    reply_to_message = update.message.reply_to_message
    
    # 2. If not replying, check if they typed text after /broadcast
    broadcast_text = " ".join(context.args) if context.args else None
    
    # 3. If they did neither, tell them how to use it
    if not reply_to_message and not broadcast_text:
        help_text = (
            "⚠️ **How to use Broadcast:**\n\n"
            "**Option 1 (Text only):**\n"
            "Type `/broadcast Your message here`\n\n"
            "**Option 2 (Images, Videos, Files):**\n"
            "Send the image/video to the bot first. Then, **reply** to that image with the command `/broadcast`."
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
        return

    # Fetch all our saved users
    users = await user_service.get_all_active_users()
    
    if not users:
        await update.message.reply_text("❌ No active users found in the database.")
        return

    await update.message.reply_text(f"🚀 Starting broadcast to {len(users)} users. This might take a moment...")
    
    success_count = 0
    fail_count = 0
    
    # Loop through every user and send the message
    for user in users:
        try:
            if reply_to_message:
                # OPTION 2: If they replied to an image/video, perfectly copy it to the user!
                await context.bot.copy_message(
                    chat_id=user.user_id,
                    from_chat_id=reply_to_message.chat.id,
                    message_id=reply_to_message.message_id
                )
            else:
                # OPTION 1: Otherwise, just send the text they typed
                await context.bot.send_message(
                    chat_id=user.user_id, 
                    text=broadcast_text,
                    parse_mode="Markdown"
                )
                
            success_count += 1
            
            # VERY IMPORTANT: Pause for 0.05 seconds to avoid Telegram rate limits
            await asyncio.sleep(0.05) 
            
        except Exception as e:
            fail_count += 1
            # Optionally deactivate them if they blocked the bot
            await user_service.deactivate_user(user.user_id)
            
    # Send a final report to the admin
    report = (
        f"✅ **Broadcast Complete!**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📨 Successfully delivered: {success_count}\n"
        f"❌ Failed (Blocked bot): {fail_count}"
    )
    await update.message.reply_text(report, parse_mode="Markdown")