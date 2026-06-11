import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот работает!")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
print("Test bot started. Send /start to @tg_bot_recruiter_v2_bot")
app.run_polling()
