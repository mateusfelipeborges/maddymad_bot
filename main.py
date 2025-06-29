import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (ApplicationBuilder, ContextTypes, MessageHandler,
                          ChatMemberHandler, filters)
import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET",
                           "corvinbotsecret")  # segurança opcional

PALAVRAS_CRIMINOSAS = [
    'cp', 'zoofilia', 'gore', 'snuff', 'terrorismo', 'porn infantil'
]

HORARIO_SILENCIO = (23, 7)
MENSAGEM_BOAS_VINDAS = "👋 Olá, seja bem-vinde ao grupo! Por favor, leia as regras fixadas. Respeito é fundamental."

app = Flask(__name__)
telegram_app = ApplicationBuilder().token(TOKEN).build()


@app.post(f"/{WEBHOOK_SECRET}")
async def webhook() -> str:
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "ok"


# --- HANDLERS DO BOT ---


async def bloquear_horario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.datetime.now().time()
    hora = agora.hour
    inicio, fim = HORARIO_SILENCIO
    if inicio <= hora or hora < fim:
        await update.message.delete()
        await update.message.reply_text(
            "⏰ O grupo está silenciado neste horário. Tente novamente mais tarde.",
            quote=True)


async def filtrar_conteudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        texto = update.message.text.lower()
        for palavra in PALAVRAS_CRIMINOSAS:
            if palavra in texto:
                await update.message.delete()
                await update.message.reply_text(
                    "🚫 Conteúdo proibido. Usuário será removido.")
                await context.bot.ban_chat_member(update.effective_chat.id,
                                                  update.effective_user.id)
                return
    if update.message.photo or update.message.document:
        await update.message.delete()
        await update.message.reply_text(
            "📵 Arquivos/imagens não são permitidos. Contato com a moderação.")


async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for membro in update.chat_member.new_chat_members:
        await context.bot.send_message(chat_id=update.chat.id,
                                       text=MENSAGEM_BOAS_VINDAS)


# Adiciona handlers
telegram_app.add_handler(MessageHandler(filters.ALL, bloquear_horario))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & (~filters.COMMAND), filtrar_conteudo))
telegram_app.add_handler(
    ChatMemberHandler(boas_vindas, ChatMemberHandler.CHAT_MEMBER))
