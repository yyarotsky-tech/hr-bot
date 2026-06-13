import os
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "test_key_123")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

print("Bot started (light version, no Whisper).")

user_sessions = {}

def format_report(report_text: str) -> str:
    report_text = report_text.replace("=== СООТВЕТСТВИЕ", "📌 СООТВЕТСТВИЕ")
    report_text = report_text.replace("=== АНАЛИЗ РЫНКА", "📊 АНАЛИЗ РЫНКА")
    report_text = report_text.replace("=== ЗАРПЛАТНАЯ АНАЛИТИКА", "💰 ЗАРПЛАТНАЯ АНАЛИТИКА")
    report_text = report_text.replace("=== ПРЕДПОЛАГАЕМЫЙ ОТВЕТ КАНДИДАТУ", "✉️ ОТВЕТ КАНДИДАТУ")
    report_text = report_text.replace("===", "")
    report_text = report_text.replace("**", "")
    return report_text

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

async def set_vacancy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❓ /vacancy <текст>")
        return
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]["vacancy_text"] = text
    await update.message.reply_text("✅ Вакансия сохранена")

async def set_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❓ /resume <текст>")
        return
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]["resume_text"] = text
    await update.message.reply_text("✅ Резюме сохранено")

async def save_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_sessions.get(user_id, {})
    if not any([data.get("vacancy_text"), data.get("resume_text")]):
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
            await update.message.reply_text(f"✅ Оценка {rating} для {cid}")
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
    if not any([data.get("vacancy_text"), data.get("resume_text")]):
        await update.message.reply_text("❌ Нет данных. Сначала отправьте /vacancy и /resume")
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
            if len(formatted) > 4000:
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

async def add_volunteer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("🤝 /add_volunteer <название>")
        return
    title = args[0]
    desc = " ".join(args[1:]) if len(args) > 1 else ""
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(f"{API_URL}/api/volunteer/add", json={"title": title, "description": desc}, headers=headers, timeout=30)
        if r.status_code == 200:
            await update.message.reply_text(f"✅ Волонтёрская вакансия «{title}» добавлена")
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def list_volunteer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    headers = {"X-API-Key": API_KEY}
    try:
        r = requests.get(f"{API_URL}/api/volunteer", headers=headers, timeout=30)
        if r.status_code == 200:
            vacs = r.json()
            if not vacs:
                await update.message.reply_text("🤝 Волонтёрских вакансий пока нет")
                return
            msg = "🤝 *Волонтёрские вакансии:*\n\n"
            for v in vacs:
                msg += f"🆔 `{v['id']}` — *{v['title']}*\n"
                if v.get('description'):
                    msg += f"   📝 {v['description'][:100]}...\n"
                if v.get('organization'):
                    msg += f"   🏢 {v['organization']}\n"
                msg += "\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def assess_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "🤝 *Оценка сотрудника*\n\n"
            "Использование:\n"
            "/assess_employee <имя> <должность> | <текст>\n\n"
            "Пример:\n"
            "/assess_employee Иван Петров Python разработчик | Иван хорошо работает, но боится ответственности",
            parse_mode="Markdown"
        )
        return
    
    text = " ".join(args)
    if " | " in text:
        name_duty, raw_text = text.split(" | ", 1)
        name_parts = name_duty.split(" ", 1)
        if len(name_parts) == 2:
            employee_name = name_parts[0]
            position = name_parts[1]
        else:
            employee_name = name_parts[0]
            position = "не указана"
    else:
        employee_name = args[0]
        position = "не указана"
        raw_text = " ".join(args[1:])
    
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    payload = {"employee_name": employee_name, "position": position, "raw_text": raw_text}
    
    status_msg = await update.message.reply_text("🧠 Анализирую сотрудника...")
    
    try:
        r = requests.post(f"{API_URL}/api/employee/assess", json=payload, headers=headers, timeout=90)
        if r.status_code == 200:
            data = r.json()
            a = data["assessment"]
            message = f"📊 *Оценка сотрудника: {employee_name}*\n\n"
            message += f"📋 *Должность:* {position}\n\n"
            message += "📈 *Оценки (1-10):*\n"
            message += f"   🦁 Лидерские качества: {a['leadership_score']}/10\n"
            message += f"   🧠 Стрессоустойчивость: {a['stress_resilience_score']}/10\n"
            message += f"   💬 Коммуникабельность: {a['communication_score']}/10\n"
            message += f"   📚 Обучаемость: {a['learnability_score']}/10\n"
            message += f"   🎯 Ответственность: {a['responsibility_score']}/10\n\n"
            message += f"✅ *Сильные стороны:* {a['strengths']}\n\n"
            message += f"📈 *Зоны роста:* {a['growth_points']}\n\n"
            message += f"💡 *Рекомендации:* {a['recommendations']}\n\n"
            message += f"⚠️ *Риск выгорания:* {a['burnout_risk']}"
            await update.message.reply_text(message, parse_mode="Markdown")
            await status_msg.delete()
        else:
            await status_msg.edit_text(f"❌ Ошибка: {r.status_code}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")

async def team_assessment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    headers = {"X-API-Key": API_KEY}
    status_msg = await update.message.reply_text("📊 Загружаю сводку по команде...")
    
    try:
        response = requests.get(f"{API_URL}/api/employee/team", headers=headers, timeout=90)
        if response.status_code == 200:
            data = response.json()
            summary = data.get("summary")
            
            if isinstance(summary, str):
                await update.message.reply_text(f"📊 *Сводка по команде*\n\n{summary}")
                await status_msg.delete()
                return
            
            assessments = data.get("assessments", [])
            
            message = f"📊 *Сводка по команде*\n\n"
            message += f"👥 *Всего сотрудников:* {summary.get('total_employees', 0)}\n\n"
            message += "📈 *Средние оценки (1-10):*\n"
            message += f"   🦁 Лидерские качества: {summary.get('avg_leadership', 0)}/10\n"
            message += f"   🧠 Стрессоустойчивость: {summary.get('avg_stress_resilience', 0)}/10\n"
            message += f"   💬 Коммуникабельность: {summary.get('avg_communication', 0)}/10\n"
            message += f"   📚 Обучаемость: {summary.get('avg_learnability', 0)}/10\n"
            message += f"   🎯 Ответственность: {summary.get('avg_responsibility', 0)}/10\n\n"
            message += "⚠️ *Риск выгорания:*\n"
            burnout = summary.get('burnout_risk_distribution', {})
            message += f"   🔴 Высокий: {burnout.get('высокий', 0)}\n"
            message += f"   🟡 Средний: {burnout.get('средний', 0)}\n"
            message += f"   🟢 Низкий: {burnout.get('низкий', 0)}\n"
            
            if assessments:
                message += "\n📋 *Последние оценки:*\n"
                for a in assessments[:5]:
                    message += f"   • {a.get('employee_name', '?')} — лидерство: {a.get('leadership_score', 0)}/10\n"
            
            await update.message.reply_text(message, parse_mode="Markdown")
            await status_msg.delete()
        else:
            await status_msg.edit_text(f"❌ Ошибка HTTP {response.status_code}: {response.text[:200]}")
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
        await query.edit_message_text("❓ /analyze, /vacancies, /candidates, /add_vacancy, /match_all")

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
    app.add_handler(CommandHandler("add_volunteer", add_volunteer))
    app.add_handler(CommandHandler("volunteer", list_volunteer))
    app.add_handler(CommandHandler("assess_employee", assess_employee))
    app.add_handler(CommandHandler("team_assessment", team_assessment))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()
