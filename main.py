import os
import random
import string
import logging
import asyncpg
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Setup basic logging to help monitor the bot and debug issues
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fetch configuration from Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
# Railway automatically provides DATABASE_URL when you attach a Postgres plugin
DATABASE_URL = os.environ.get("DATABASE_URL")

class Database:
    """Handles PostgreSQL connections and queries asynchronously."""
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None

    async def connect(self):
        """Creates a connection pool and initializes the database table."""
        self.pool = await asyncpg.create_pool(self.db_url)
        async with self.pool.acquire() as conn:
            # Create the files table if it doesn't exist
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    code TEXT PRIMARY KEY, 
                    message_id INTEGER
                )
            ''')

    async def insert_file(self, code, message_id):
        """Inserts a new extraction code and message ID into the database."""
        async with self.pool.acquire() as conn:
            # Using $1, $2 prevents SQL injection attacks
            await conn.execute(
                "INSERT INTO files (code, message_id) VALUES ($1, $2)", 
                code, message_id
            )

    async def get_message_id(self, code):
        """Retrieves the message ID associated with a specific code."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT message_id FROM files WHERE code = $1", 
                code
            )
    
    async def close(self):
        """Closes the connection pool."""
        if self.pool:
            await self.pool.close()

# Instantiate the database manager
db = Database(DATABASE_URL)

def generate_code(length=6):
    """Generates a random uppercase alphanumeric code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    await update.message.reply_text("Send the extraction code to get the file.")

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listens to channel posts, generates a code, and saves it to the database."""
    msg = update.channel_post
    
    # Filter out irrelevant messages or messages from unmonitored channels
    if not msg or msg.chat.id != CHANNEL_ID:
        return
        
    # Process only messages containing videos, photos, or documents
    if not (msg.video or msg.photo or msg.document):
        return

    code = generate_code()
    
    # Write the data to the PostgreSQL database
    try:
        await db.insert_file(code, msg.message_id)
    except Exception as e:
        logger.error(f"Failed to insert into database: {e}")
        return

    # Reply in the channel with the generated code (Visible to admins)
    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"Successfully stored in database.\nExtraction Code: {code}",
        reply_to_message_id=msg.message_id
    )

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles private messages from users attempting to fetch files."""
    user_text = update.message.text.strip().upper()
    
    # Query the database for the matching code
    try:
        message_id = await db.get_message_id(user_text)
    except Exception as e:
        logger.error(f"Database query error: {e}")
        await update.message.reply_text("An error occurred while fetching the file. Please try again later.")
        return

    if message_id:
        try:
            # Core mechanism: Forward message without showing the original sender (Stealth extraction)
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=message_id
            )
        except Exception as e:
            logger.error(f"Telegram copy_message error: {e}")
            await update.message.reply_text("Failed to send. The file might have been deleted from the channel.")
    else:
        await update.message.reply_text("Invalid extraction code.")

async def post_init(application: Application):
    """Runs after the bot initializes but before it starts polling."""
    logger.info("Connecting to PostgreSQL database...")
    await db.connect()
    logger.info("Database connected and initialized.")

async def post_stop(application: Application):
    """Runs when the bot is shutting down."""
    logger.info("Closing database connection...")
    await db.close()

def main():
    """Main execution function to build and run the bot."""
    if not BOT_TOKEN or not DATABASE_URL or CHANNEL_ID == 0:
        logger.error("CRITICAL ERROR: BOT_TOKEN, DATABASE_URL, or CHANNEL_ID is missing.")
        return

    # Build the application and register startup/shutdown hooks
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_stop(post_stop)
        .build()
    )

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_user_message))

    # Start the bot
    logger.info("Bot is polling...")
    app.run_polling()

if __name__ == '__main__':
    main()