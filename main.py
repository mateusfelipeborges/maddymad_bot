from telegram import Update, ChatPermissions
from telegram.ext import (ApplicationBuilder, MessageHandler, CommandHandler,
                          filters, ContextTypes, ChatMemberHandler)
import datetime
import os

# 🔐 Pega o token diretamente das variáveis de ambiente do Render
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Palavras proibidas
PALAVRAS_CRIMINOSAS = [
    'cp', 'zoofilia', 'gore', 'snuff', 'terrorismo', 'porn infantil'
]

# Horário de silêncio
HORARIO_SILENCIO = (23, 7)

# Mensagem de boas-vindas
MENSAGEM_BOAS_VINDAS = "👋 Olá, seja bem-vinde ao grupo! Por favor, leia as regras fixadas. Respeito é fundamental."


# Bloqueia mensagens fora do horário permitido
async def bloquear_horario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.datetime.now().time()
    hora = agora.hour
    inicio, fim = HORARIO_SILENCIO
    if inicio <= hora or hora < fim:
        await update.message.delete()
        await update.message.reply_text(
            "⏰ O grupo está silenciado neste horário. Tente novamente mais tarde.",
            quote=True)


# Filtra conteúdo criminoso e arquivos
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


# Envia mensagem de boas-vindas
async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for membro in update.chat_member.new_chat_members:
        await context.bot.send_message(chat_id=update.chat.id,
                                       text=MENSAGEM_BOAS_VINDAS)


# Inicia o bot
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, bloquear_horario))
app.add_handler(
    MessageHandler(filters.TEXT & (~filters.COMMAND), filtrar_conteudo))
app.add_handler(ChatMemberHandler(boas_vindas, ChatMemberHandler.CHAT_MEMBER))

print("🤖 Bot Corvin Guard rodando...")
app.run_polling()
