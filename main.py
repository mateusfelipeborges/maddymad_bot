import os
import datetime
import threading
import re
import asyncio
import httpx
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)
from telegram.request import HTTPXRequest

# ✅ Carregar variáveis do arquivo .env
from dotenv import load_dotenv
load_dotenv()

# Variáveis de ambiente
TOKEN = os.getenv("TELEGRAM_TOKEN")
print(f"[DEBUG] TOKEN carregado: {repr(TOKEN)}")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "corvinbotsecret")
PORT = int(os.environ.get("PORT", 10000))

# Configurações
PALAVRAS_CRIMINOSAS = [
    "cp", "zoofilia", "gore", "snuff", "terrorismo", "porn infantil",
]
HORARIO_SILENCIO = (23, 7)
MENSAGEM_BOAS_VINDAS = (
    "👋 Olá, seja bem-vinde ao grupo! Por favor, leia as regras fixadas. Respeito é fundamental. "
    "PROIBIDO conteúdo de CP, zoofilia, gore, snuff, terrorismo e porn infantil. BANIMENTO IMEDIATO! "
)
PALAVRAS_PROIBIDAS_TROCA_VIDEOS = [
    "trocar video", "troca video", "manda video", "me manda video",
    "me envie video", "video privado", "trocar conteudo",
]

app = Flask(__name__)

# ✅ Correção aqui: renomeando para não sobrescrever o `request` do Flask
telegram_request = HTTPXRequest()

telegram_app = (
    ApplicationBuilder()
    .token(TOKEN)
    .request(telegram_request)
    .concurrent_updates(10)
    .build()
)

@app.route("/")
def index():
    return "Bot ativo!"

def normalizar_texto(texto: str) -> str:
    texto = texto.lower()
    substituicoes = {"4": "a", "3": "e", "1": "i", "0": "o", "5": "s", "7": "t", "8": "b"}
    for numero, letra in substituicoes.items():
        texto = texto.replace(numero, letra)
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

@app.post(f"/{WEBHOOK_SECRET}")
async def webhook() -> str:
    payload = request.get_json()  # <-- agora funciona corretamente
    print("[DEBUG] Payload recebido do Telegram:", payload)
    update = Update.de_json(payload, telegram_app.bot)
    await telegram_app.process_update(update)
    print("[DEBUG] Update processado com sucesso")
    return "ok"

async def apagar_mensagem_apos_delay(context, chat_id, message_id, delay=10):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"[ERRO] Falha ao apagar mensagem: {e}")

async def bloquear_horario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.datetime.now().time()
    hora = agora.hour
    inicio, fim = HORARIO_SILENCIO
    if inicio <= hora or hora < fim:
        try:
            print(f"[DEBUG] Bloqueando mensagem por horário: {hora}h")
            await update.message.delete()
        except Exception as e:
            print(f"[WARNING] Falha ao deletar mensagem: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏰ O grupo está silenciado neste horário. Tente novamente mais tarde.",
        )

async def filtrar_conteudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        texto = update.message.text.lower()
        print(f"[DEBUG] Mensagem recebida para filtro de conteúdo: {texto}")
        for palavra in PALAVRAS_CRIMINOSAS:
            if palavra in texto:
                print(f"[ALERTA] Palavra proibida detectada: {palavra}")
                await update.message.delete()
                msg = await update.message.reply_text("🚫 Conteúdo proibido. Usuário será removido.")
                await context.bot.ban_chat_member(update.effective_chat.id, update.effective_user.id)
                asyncio.create_task(apagar_mensagem_apos_delay(context, msg.chat_id, msg.message_id))
                return

async def banir_pedidos_troca_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        texto = normalizar_texto(update.message.text)
        print(f"[DEBUG] Mensagem recebida para filtro troca vídeos: {texto}")
        for frase in PALAVRAS_PROIBIDAS_TROCA_VIDEOS:
            if frase in texto:
                print(f"[ALERTA] Pedido de troca de vídeo detectado: {frase}")
                await update.message.delete()
                msg = await update.message.reply_text(
                    "🚫 Pedido de troca de vídeos/fotos não é permitido. Você será removido do grupo."
                )
                await context.bot.ban_chat_member(update.effective_chat.id, update.effective_user.id)
                asyncio.create_task(apagar_mensagem_apos_delay(context, msg.chat_id, msg.message_id))
                return

async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        old_status = update.chat_member.old_chat_member.status
        new_status = update.chat_member.new_chat_member.status
        print(f"[DEBUG] ChatMember update: old_status={old_status}, new_status={new_status}")
        if old_status in ["left", "kicked"] and new_status == "member":
            nome = update.chat_member.new_chat_member.user.first_name
            msg = await context.bot.send_message(
                chat_id=update.chat_member.chat.id,
                text=f"👋 Olá, {nome}! {MENSAGEM_BOAS_VINDAS}"
            )
            asyncio.create_task(apagar_mensagem_apos_delay(context, msg.chat_id, msg.message_id, delay=5))
    except Exception as e:
        print(f"[ERRO no boas_vindas] {e}")

async def boas_vindas_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.new_chat_members:
        for membro in update.message.new_chat_members:
            nome = membro.first_name or "novo membro"
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"👋 Olá, {nome}! {MENSAGEM_BOAS_VINDAS}"
            )
            asyncio.create_task(apagar_mensagem_apos_delay(context, msg.chat_id, msg.message_id, delay=5))

telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filtrar_conteudo))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, banir_pedidos_troca_videos))
telegram_app.add_handler(ChatMemberHandler(boas_vindas, ChatMemberHandler.CHAT_MEMBER))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, boas_vindas_message))

def start_bot():
    async def runner():
        await telegram_app.initialize()
        await telegram_app.start()
        print("🤖 Bot Telegram iniciado com Webhook!")
    asyncio.run(runner())

if __name__ == "__main__":
    threading.Thread(target=start_bot).start()
    app.run(host="0.0.0.0", port=PORT)
