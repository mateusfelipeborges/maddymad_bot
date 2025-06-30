import os
import datetime
import threading
import re
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (ApplicationBuilder, ContextTypes, MessageHandler,
                          ChatMemberHandler, filters)

# Variáveis de ambiente
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "corvinbotsecret")
PORT = int(os.environ.get("PORT", 10000))  # Porta padrão do Render é 10000

# Configurações
PALAVRAS_CRIMINOSAS = [
    'cp', 'zoofilia', 'gore', 'snuff', 'terrorismo', 'porn infantil'
]
HORARIO_SILENCIO = (23, 7)
MENSAGEM_BOAS_VINDAS = "👋 Olá, seja bem-vinde ao grupo! Por favor, leia as regras fixadas. Respeito é fundamental. PROIBIDO conteúdo de CP, zoofilia, gore, snuff, terrorismo e porn infantil. BANIMENTO IMEDIATO "

# Frases proibidas para troca de vídeos/fotos (normalizadas)
PALAVRAS_PROIBIDAS_TROCA_VIDEOS = [
    "trocar video", "troca video", "manda video", "me manda video",
    "me envie video", "video privado", "trocar conteudo", "trocar fotos",
    "me manda fotos"
]

# Flask app
app = Flask(__name__)

# Telegram Application
telegram_app = ApplicationBuilder().token(TOKEN).build()


# Rota raiz só para teste (evita 404)
@app.route("/")
def index():
    return "Bot ativo!"


# --- Função para normalizar texto ---
def normalizar_texto(texto: str) -> str:
    texto = texto.lower()
    substituicoes = {
        '4': 'a',
        '3': 'e',
        '1': 'i',
        '0': 'o',
        '5': 's',
        '7': 't',
        '8': 'b'
    }
    for numero, letra in substituicoes.items():
        texto = texto.replace(numero, letra)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)  # Remove caracteres especiais
    texto = re.sub(r'\s+', ' ', texto).strip()  # Remove espaços extras
    return texto


# --- WEBHOOK ENDPOINT ---
@app.route(f"/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
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


async def banir_pedidos_troca_videos(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        texto = normalizar_texto(update.message.text)
        for frase in PALAVRAS_PROIBIDAS_TROCA_VIDEOS:
            if frase in texto:
                await update.message.delete()
                await update.message.reply_text(
                    "🚫 Pedido de troca de vídeos/fotos não é permitido. Você será removido do grupo."
                )
                await context.bot.ban_chat_member(update.effective_chat.id,
                                                  update.effective_user.id)
                return


async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    old_status = update.chat_member.old_chat_member.status
    new_status = update.chat_member.new_chat_member.status
    # DEBUG
    print(
        f"[DEBUG] ChatMember update: old_status={old_status}, new_status={new_status}"
    )
    if old_status in ['left', 'kicked'] and new_status == 'member':
        await context.bot.send_message(chat_id=update.chat_member.chat.id,
                                       text=MENSAGEM_BOAS_VINDAS)


# Adiciona handlers
telegram_app.add_handler(MessageHandler(filters.ALL, bloquear_horario))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, filtrar_conteudo))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND,
                   banir_pedidos_troca_videos))
telegram_app.add_handler(
    ChatMemberHandler(boas_vindas, ChatMemberHandler.CHAT_MEMBER))


# --- INICIALIZA O BOT EM BACKGROUND ---
def start_bot():
    import asyncio

    async def runner():
        await telegram_app.initialize()
        await telegram_app.start()
        print("🤖 Bot Telegram iniciado com Webhook!")

    asyncio.run(runner())


if __name__ == "__main__":
    threading.Thread(target=start_bot).start()
    app.run(host="0.0.0.0", port=PORT)
