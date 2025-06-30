import os
import datetime
import threading
import re
from flask import Flask, request
from telegram import Update
from telegram.ext import (ApplicationBuilder, ContextTypes, MessageHandler,
                          ChatMemberHandler, filters)
from telegram.request import HTTPXRequest

# Variáveis de ambiente
TOKEN = os.getenv("TELEGRAM_TOKEN")
print(f"[DEBUG] TOKEN carregado: {repr(TOKEN)}")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "corvinbotsecret")
PORT = int(os.environ.get("PORT", 10000))  # Porta padrão do Render é 10000

# Configurações
PALAVRAS_CRIMINOSAS = [
    'cp', 'zoofilia', 'gore', 'snuff', 'terrorismo', 'porn infantil'
]
HORARIO_SILENCIO = (23, 7)
MENSAGEM_BOAS_VINDAS = "👋 Olá, seja bem-vinde ao grupo! Por favor, leia as regras fixadas. Respeito é fundamental. PROIBIDO conteúdo de CP, zoofilia, gore, snuff, terrorismo e porn infantil. BANIMENTO IMEDIATO "

PALAVRAS_PROIBIDAS_TROCA_VIDEOS = [
    "trocar video", "troca video", "manda video", "me manda video",
    "me envie video", "video privado", "trocar conteudo"
]

app = Flask(__name__)

# Opcional: configurar request com timeout customizado
# request = HTTPXRequest(connect_timeout=10, read_timeout=20)

# Limita a 5 atualizações concorrentes para evitar PoolTimeout
telegram_app = (
    ApplicationBuilder()
    .token(TOKEN)
    # .request(request)  # Descomente para ativar timeout customizado
    .concurrent_updates(5)
    .build()
)

@app.route("/")
def index():
    return "Bot ativo!"

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
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

@app.post(f"/{WEBHOOK_SECRET}")
async def webhook() -> str:
    payload = request.get_json(force=True)
    print("[DEBUG] Payload recebido do Telegram:", payload)
    update = Update.de_json(payload, telegram_app.bot)
    await telegram_app.process_update(update)
    return "ok"

async def bloquear_horario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.datetime.now().time()
    hora = agora.hour
    inicio, fim = HORARIO_SILENCIO
    if inicio <= hora or hora < fim:
        try:
            await update.message.delete()
        except Exception as e:
            print(f"[WARNING] Falha ao deletar mensagem: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏰ O grupo está silenciado neste horário. Tente novamente mais tarde."
        )

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
    try:
        old_status = update.chat_member.old_chat_member.status
        new_status = update.chat_member.new_chat_member.status
        print(f"[DEBUG] ChatMember update: old_status={old_status}, new_status={new_status}")
        if old_status in ['left', 'kicked'] and new_status == 'member':
            nome = update.chat_member.new_chat_member.user.first_name
            await context.bot.send_message(
                chat_id=update.chat_member.chat.id,
                text=f"👋 Olá, {nome}! {MENSAGEM_BOAS_VINDAS}")
    except Exception as e:
        print(f"[ERRO no boas_vindas] {e}")

telegram_app.add_handler(MessageHandler(filters.ALL, bloquear_horario))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, filtrar_conteudo))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND,
                   banir_pedidos_troca_videos))
telegram_app.add_handler(
    ChatMemberHandler(boas_vindas, ChatMemberHandler.CHAT_MEMBER))

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

