import os
import tempfile
import whisper
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from datetime import datetime
from telegraph import Telegraph

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "test_key_123")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Whisper ready.")

user_sessions = {}

# ---------- Telegraph ----------
telegraph = Telegraph()
telegraph.create_account(short_name='HR Absolute')

def publish_to_telegraph(title, content):
    try:
        response = telegraph.create_page(
            title=title,
            html_content=f"<pre>{content}</pre>",
            author_name='HR Absolute Bot',
            author_url='https://t.me/tg_bot_recruiter_v2_bot'
        )
        return response['url']
    except Exception as e:
        print(f"Telegraph error: {e}")
        return None

# ---------- Форматирование ----------
def format_report(report_text: str) -> str:
    report_text = report_text.replace("=== СООТВЕТСТВИЕ", "📌 СООТВЕТСТВИЕ")
    report_text = report_text.replace("=== АНАЛИЗ РЫНКА", "📊 АНАЛИЗ РЫНКА")
    report_text = report_text.replace("=== ЗАРПЛАТНАЯ АНАЛИТИКА", "💰 ЗАРПЛАТНАЯ АНАЛИТИКА")
    report_text = report_text.replace("=== ПРЕДПОЛАГАЕМЫЙ ОТВЕТ КАНДИДАТУ", "✉️ ОТВЕТ КАНДИДАТУ")
    report_text = report_text.replace("===", "")
    report_text = report_text.replace("**", "")
    return report_text

# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📄 Анализ", callback_data="analyze")],
        [InlineKeyboardButton("💼 Вакансии", callback_data="vacancies")],
        [InlineKeyboardButton("📋 Кандидаты", callback_data="candidates")],
        [InlineKeyboardButton("📊 Бенчмаркинг", callback_data="benchmark")],
        [InlineKeyboardButton("🏭 Workforce", callback_data="workforce")],
        [InlineKeyboardButton("🤝 Волонтёрство", callback_data="volunteer")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    await update.message.reply_text(
        "👋 HR Absolute\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions.pop(user_id, None)
    await update.message.reply_text("✅ Сессия очищена")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    audio = update.message.voice or update.message.audio
    if not audio:
        return
    status = await update.message.reply_text("⏳ Скачиваю...")
    suffix = ".ogg" if update.message.voice else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file = await audio.get_file()
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name
    try:
        transcribed = whisper_model.transcribe(tmp_path, language="ru")["text"]
        if not transcribed.strip():
            await status.edit_text("❌ Речь не распознана")
            return
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]["transcribed_text"] = transcribed
        await status.edit_text(f"✅ Аудио сохранено:\n{transcribed[:300]}...")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")
    finally:
        os.unlink(tmp_path)

async def set_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❓ Использование: /vacancy <текст>")
        return
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]["vacancy_text"] = text
    await update.message.reply_text("✅ Вакансия сохранена")

async def set_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❓ Использование: /resume <текст>")
        return
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]["resume_text"] = text
    await update.message.reply_text("✅ Резюме сохранено")

async def save_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_sessions.get(user_id, {})
    if not any([data.get("transcribed_text"), data.get("vacancy_text"), data.get("resume_text")]):
        await update.message.reply_text("❌ Нет данных для сохранения")
        return
    name = " ".join(context.args) if context.args else "Кандидат без имени"
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(f"{API_URL}/api/candidates/save", json={"name": name, "data": data}, headers=headers, timeout=30)
        if r.status_code == 200:
            await update.message.reply_text(f"✅ {name} сохранён (ID: {r.json()['id']})")
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def list_candidates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    headers = {"X-API-Key": API_KEY}
    try:
        r = requests.get(f"{API_URL}/api/candidates", headers=headers, timeout=30)
        if r.status_code == 200:
            cands = r.json()
            if not cands:
                await update.message.reply_text("📭 Нет кандидатов")
                return
            msg = "📋 Кандидаты:\n"
            for c in cands:
                msg += f"\n🆔 {c['id']} — {c['name']}"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def rate_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❓ /rate <id> <оценка 1-10>")
        return
    try:
        cid = int(args[0])
        rating = int(args[1])
        if rating < 1 or rating > 10:
            await update.message.reply_text("❌ Оценка должна быть от 1 до 10")
            return
        comment = " ".join(args[2:]) if len(args) > 2 else None
        headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
        r = requests.post(f"{API_URL}/api/rate", json={"candidate_id": cid, "rating": rating, "comment": comment}, headers=headers, timeout=30)
        if r.status_code == 200:
            await update.message.reply_text(f"✅ Оценка {rating} для кандидата {cid} сохранена")
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def add_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❓ /add_vacancy <название>")
        return
    title = args[0]
    desc = " ".join(args[1:]) if len(args) > 1 else ""
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(f"{API_URL}/api/vacancies/add", json={"title": title, "description": desc}, headers=headers, timeout=30)
        if r.status_code == 200:
            await update.message.reply_text(f"✅ Вакансия «{title}» добавлена (ID: {r.json()['id']})")
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def list_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    headers = {"X-API-Key": API_KEY}
    try:
        r = requests.get(f"{API_URL}/api/vacancies", headers=headers, timeout=30)
        if r.status_code == 200:
            vacs = r.json()
            if not vacs:
                await update.message.reply_text("📭 Нет вакансий")
                return
            msg = "💼 Вакансии:\n"
            for v in vacs:
                msg += f"\n🆔 {v['id']} — {v['title']}"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def delete_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❓ /delete_vacancy <id>")
        return
    try:
        vid = int(args[0])
        headers = {"X-API-Key": API_KEY}
        r = requests.delete(f"{API_URL}/api/vacancies/{vid}", headers=headers, timeout=30)
        if r.status_code == 200:
            await update.message.reply_text(f"✅ Вакансия {vid} удалена")
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def match_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Матчинг... 1-2 минуты")
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(f"{API_URL}/api/match", json={}, headers=headers, timeout=180)
        if r.status_code == 200:
            matches = r.json()
            if not matches:
                await update.message.reply_text("📭 Нет результатов")
                return
            from collections import defaultdict
            by_name = defaultdict(list)
            for m in matches:
                by_name[m["candidate_name"]].append(m)
            msg = "📊 Результаты матчинга:\n"
            for name, mlist in by_name.items():
                msg += f"\n👤 {name}"
                for m in mlist[:3]:
                    msg += f"\n   • {m['vacancy_title']}: {m['score']}%"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_sessions.get(user_id, {})
    if not any([data.get("transcribed_text"), data.get("vacancy_text"), data.get("resume_text")]):
        await update.message.reply_text("❌ Нет данных. Сначала отправьте аудио и/или /vacancy, /resume")
        return
    status_msg = await update.message.reply_text("🧠 Анализирую...")
    payload = {k: v for k, v in data.items() if v is not None}
    payload["options"] = {"transferable": True, "antifilter": True}
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(f"{API_URL}/api/analyze/candidate", json=payload, headers=headers, timeout=120)
        if r.status_code == 200:
            report = r.json().get("report", {}).get("full_report", "Нет отчёта")
            formatted = format_report(report)
            if len(formatted) > 3000:
                title = f"Анализ кандидата - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                url = publish_to_telegraph(title, formatted)
                if url:
                    await update.message.reply_text(
                                f"📄 *Отчёт слишком длинный для Telegram*\n\n"
                                f"👉 [Читать полный отчёт на Telegraph]({url})\n\n"
                                f"📌 *Краткая выдержка:*\n{formatted[:500]}...",
                                parse_mode="Markdown"
                            )
                else:
                    parts = []
                    rem = formatted
                    while len(rem) > 4000:
                        split = rem.rfind('\n\n', 0, 4000)
                        if split == -1:
                            split = 4000
                        parts.append(rem[:split])
                        rem = rem[split:]
                    parts.append(rem)
                    for i, part in enumerate(parts, 1):
                        await update.message.reply_text(f"📄 Часть {i}/{len(parts)}\n\n{part}")
            else:
                await update.message.reply_text(formatted)
            await status_msg.delete()
        else:
            await status_msg.edit_text(f"❌ Ошибка API: {r.status_code}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Используйте команды из /start")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "analyze":
        await query.edit_message_text("📄 /vacancy и /resume, затем /analyze")
    elif data == "vacancies":
        headers = {"X-API-Key": API_KEY}
        try:
            r = requests.get(f"{API_URL}/api/vacancies", headers=headers, timeout=30)
            if r.status_code == 200:
                vacs = r.json()
                if not vacs:
                    await query.edit_message_text("📭 Нет вакансий")
                    return
                msg = "💼 Вакансии:\n"
                for v in vacs:
                    msg += f"\n🆔 {v['id']} — {v['title']}"
                await query.edit_message_text(msg)
            else:
                await query.edit_message_text(f"❌ Ошибка: {r.status_code}")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")
    elif data == "candidates":
        headers = {"X-API-Key": API_KEY}
        try:
            r = requests.get(f"{API_URL}/api/candidates", headers=headers, timeout=30)
            if r.status_code == 200:
                cands = r.json()
                if not cands:
                    await query.edit_message_text("📭 Нет кандидатов")
                    return
                msg = "📋 Кандидаты:\n"
                for c in cands:
                    msg += f"\n🆔 {c['id']} — {c['name']}"
                await query.edit_message_text(msg)
            else:
                await query.edit_message_text(f"❌ Ошибка: {r.status_code}")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")
    elif data == "benchmark":
        await query.edit_message_text("📊 /benchmark IT 50 15 45 350000")
    elif data == "workforce":
        await query.edit_message_text("🏭 /workforce <задачи> | <штат>")
    elif data == "volunteer":
        await query.edit_message_text("🤝 /volunteer")
    elif data == "help":
        await query.edit_message_text(
            "📋 *Команды*\n"
            "/analyze - анализ\n"
            "/vacancies - вакансии\n"
            "/candidates - кандидаты\n"
            "/add_vacancy - добавить\n"
            "/match_all - матчинг\n"
            "/save - сохранить\n"
            "/rate - оценить\n"
            "/reset - очистить"
        )

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("vacancy", set_vacancy))
    app.add_handler(CommandHandler("resume", set_resume))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("save", save_current))
    app.add_handler(CommandHandler("candidates", list_candidates))
    app.add_handler(CommandHandler("rate", rate_candidate))
    app.add_handler(CommandHandler("add_vacancy", add_vacancy))
    app.add_handler(CommandHandler("vacancies", list_vacancies))
    app.add_handler(CommandHandler("delete_vacancy", delete_vacancy))
    app.add_handler(CommandHandler("match_all", match_all))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()
