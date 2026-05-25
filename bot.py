import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)

# ─── Configuração ─────────────────────────────────────────────

TOKEN       = os.environ.get("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
ADMIN_ID    = int(os.environ.get("ADMIN_ID", "0"))      # O teu Telegram ID
GROUP_ID    = os.environ.get("GROUP_ID", "0")           # ID do grupo/canal VIP

# ─── Estados da conversa ──────────────────────────────────────

JOGO, MERCADO, ODD, STAKE, HORA, ANALISE, CONFIRMAR = range(7)

# ─── Mercados Bet365 ──────────────────────────────────────────

MERCADOS = [
    ["⚽ BTTS (Ambos Marcam)", "📈 Over 1.5 Gols"],
    ["📈 Over 2.5 Gols", "📉 Under 2.5 Gols"],
    ["📈 Over 3.5 Gols", "📉 Under 3.5 Gols"],
    ["🏠 Vitória Casa", "✈️ Vitória Fora"],
    ["🤝 Empate", "🔰 Dupla Hipótese 1X"],
    ["🔰 Dupla Hipótese X2", "🔰 Dupla Hipótese 12"],
    ["🟡 Mais de 3.5 Cantos", "🟡 Mais de 8.5 Cantos"],
    ["🟡 Mais de 9.5 Cantos", "🟡 Mais de 10.5 Cantos"],
    ["🟨 Mais de 3.5 Cartões", "🟨 Mais de 4.5 Cartões"],
    ["⏱️ Intervalo - Over 0.5", "⏱️ 2ª Parte - Over 0.5"],
    ["🎯 Golo Minuto 1-10", "🎯 Ambas Marcam 2ª Parte"],
    ["🔴 Asian Handicap", "📊 Outro Mercado"],
]

STAKES = [
    ["1️⃣ 1 Unidade", "2️⃣ 2 Unidades"],
    ["3️⃣ 3 Unidades", "4️⃣ 4 Unidades"],
    ["5️⃣ 5 Unidades (Máx)"]
]

sinal_contador = {"n": 0}

# ─── Verificação de admin ─────────────────────────────────────

def is_admin(update: Update) -> bool:
    return update.message.from_user.id == ADMIN_ID

# ─── Handlers ─────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update):
        await update.message.reply_text(
            "👋 *Painel Admin — GolTrader Sinais*\n\n"
            "Comandos disponíveis:\n\n"
            "/sinal — enviar novo sinal\n"
            "/teste — testar formato do sinal\n"
            "/grupo — ver ID do grupo\n"
            "/ajuda — ver comandos",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "👋 Bem-vindo ao *GolTrader Sinais*!\n\n"
            "💡 Para receber os nossos sinais, entra no grupo VIP.\n\n"
            "📩 Fala com o admin para mais informações.",
            parse_mode="Markdown"
        )

async def sinal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Sem permissão.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🚨 *Novo Sinal*\n\n"
        "⚽ Qual é o jogo?\n"
        "_(ex: Arsenal x Chelsea)_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return JOGO

async def get_jogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["jogo"] = update.message.text
    await update.message.reply_text(
        "📊 Qual o mercado?",
        reply_markup=ReplyKeyboardMarkup(MERCADOS, one_time_keyboard=True, resize_keyboard=True)
    )
    return MERCADO

async def get_mercado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mercado"] = update.message.text
    await update.message.reply_text(
        "📈 Qual a odd? _(ex: 1.85)_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return ODD

async def get_odd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        odd = float(update.message.text.replace(",", "."))
        if odd <= 1.0:
            await update.message.reply_text("❌ Odd inválida. Tem que ser maior que 1.0:")
            return ODD
        context.user_data["odd"] = odd
        await update.message.reply_text(
            "💰 Qual o stake recomendado?",
            reply_markup=ReplyKeyboardMarkup(STAKES, one_time_keyboard=True, resize_keyboard=True)
        )
        return STAKE
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Envia só o número (ex: 1.85)")
        return ODD

async def get_stake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["stake"] = update.message.text
    await update.message.reply_text(
        "⏰ A que horas é o jogo?\n_(ex: 16:00 ou 21:45)_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return HORA

async def get_hora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["hora"] = update.message.text
    await update.message.reply_text(
        "📝 Análise / Justificação:\n_(ex: Ambas as equipas marcam nos últimos 5 jogos)_\n\n"
        "Ou envia /pular para não adicionar análise.",
        parse_mode="Markdown"
    )
    return ANALISE

async def get_analise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["analise"] = update.message.text
    return await mostrar_preview(update, context)

async def pular_analise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["analise"] = None
    return await mostrar_preview(update, context)

async def mostrar_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sinal_texto = formatar_sinal(context.user_data, preview=True)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Enviar para o grupo", callback_data="enviar"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")
        ]
    ])

    await update.message.reply_text(
        f"👁️ *Preview do sinal:*\n\n{sinal_texto}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return CONFIRMAR

async def confirmar_sinal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        await query.edit_message_text("❌ Sinal cancelado.")
        return ConversationHandler.END

    sinal_contador["n"] += 1
    context.user_data["numero"] = sinal_contador["n"]
    sinal_texto = formatar_sinal(context.user_data, preview=False)

    try:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=sinal_texto,
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"✅ *Sinal #{sinal_contador['n']} enviado com sucesso!*",
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Erro ao enviar para o grupo:\n`{e}`\n\n"
            "Verifica se o bot é admin do grupo e se o GROUP_ID está correto.",
            parse_mode="Markdown"
        )

    return ConversationHandler.END

# ─── Formatação do sinal ──────────────────────────────────────

def formatar_sinal(dados: dict, preview: bool) -> str:
    numero  = dados.get("numero", "??") if not preview else "XX"
    jogo    = dados.get("jogo", "—")
    mercado = dados.get("mercado", "—")
    odd     = dados.get("odd", "—")
    stake   = dados.get("stake", "—")
    hora    = dados.get("hora", "—")
    analise = dados.get("analise")

    texto = (
        f"🚨 *SINAL #{numero}*\n"
        f"{'─' * 25}\n"
        f"⚽ *Jogo:* {jogo}\n"
        f"📊 *Mercado:* {mercado}\n"
        f"📈 *Cotação:* `{odd}`\n"
        f"💰 *Unidades:* {stake}\n"
        f"🏦 *Casa:* Bet365\n"
        f"⏰ *Horário:* {hora}\n"
    )

    if analise:
        texto += f"📌 *Análise:* _{analise}_\n"

    texto += (
        f"{'─' * 25}\n"
        f"⚠️ _Aposte com responsabilidade. Gestão de banca é fundamental._"
    )

    return texto

# ─── Comandos auxiliares ──────────────────────────────────────

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def get_grupo_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    chat_id = update.message.chat_id
    await update.message.reply_text(
        f"📋 *IDs úteis:*\n\n"
        f"O teu ID (admin): `{update.message.from_user.id}`\n"
        f"ID deste chat: `{chat_id}`",
        parse_mode="Markdown"
    )

async def teste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    dados_teste = {
        "numero": 1,
        "jogo": "Arsenal x Chelsea",
        "mercado": "⚽ BTTS (Ambos Marcam)",
        "odd": 1.85,
        "stake": "2️⃣ 2 Unidades",
        "hora": "16:00",
        "analise": "Ambas as equipas marcam nos últimos 5 jogos"
    }
    sinal_texto = formatar_sinal(dados_teste, preview=False)
    await update.message.reply_text(
        f"🧪 *Sinal de teste (só visível para ti):*\n\n{sinal_texto}",
        parse_mode="Markdown"
    )

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "📌 *Comandos Admin*\n\n"
        "/sinal — criar e enviar novo sinal\n"
        "/teste — ver preview do formato\n"
        "/grupo — ver IDs do chat\n"
        "/ajuda — esta mensagem\n\n"
        "⚙️ *Variáveis necessárias no servidor:*\n"
        "`TELEGRAM_TOKEN` — token do BotFather\n"
        "`ADMIN_ID` — o teu ID do Telegram\n"
        "`GROUP_ID` — ID do grupo VIP",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("sinal", sinal_start)],
        states={
            JOGO:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_jogo)],
            MERCADO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mercado)],
            ODD:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_odd)],
            STAKE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stake)],
            HORA:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hora)],
            ANALISE:   [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_analise),
                CommandHandler("pular", pular_analise)
            ],
            CONFIRMAR: [CallbackQueryHandler(confirmar_sinal)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("teste", teste))
    app.add_handler(CommandHandler("grupo", get_grupo_id))
    app.add_handler(CommandHandler("ajuda", ajuda))

    print("🤖 GolTrader Sinais a correr...")
    app.run_polling()

if __name__ == "__main__":
    main()
