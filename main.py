"""
Main Telegram Bot script for Gilda del Grifone.
Handles group greetings, FAQ browsing/search, and admin ticket system.
"""

import html
import logging
import os
import re
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import database
import faq_manager

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def format_telegram_html(text: str) -> str:
    """
    Converts Markdown syntax to Telegram-supported HTML while preserving existing HTML tags.
    Supports:
      # Heading -> <b>Heading</b>
      **bold** -> <b>bold</b>
      [text](url) -> <a href="url">text</a>
      `code` -> <code>code</code>
      - item / * item -> • item
    """
    if not text:
        return ""

    # Convert markdown links [text](url) to <a href="url">text</a>
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'\[([^\]]+)\]\((tg://[^\)]+)\)', r'<a href="\2">\1</a>', text)

    # Convert Markdown bold **text** to <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # Convert single backticks `code` to <code>code</code>
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Convert headers and bullet lists
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            header_text = stripped.lstrip("#").strip()
            lines.append(f"<b>{header_text}</b>")
        elif stripped.startswith(("- ", "* ")) and not stripped.startswith("**"):
            lines.append(f"• {stripped[2:]}")
        else:
            lines.append(line)

    return "\n".join(lines)


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Constructs the main menu inline keyboard."""
    keyboard = [
        [InlineKeyboardButton("📚 Consulta le FAQ", callback_data="menu_browse")],
        [InlineKeyboardButton("🔍 Cerca una Risposta", callback_data="menu_search_prompt")],
        [InlineKeyboardButton("🎫 Apri un Ticket", callback_data="menu_open_ticket")],
        [InlineKeyboardButton("👥 Contatta gli Admin", callback_data="menu_admins")],
    ]
    return InlineKeyboardMarkup(keyboard)



# ===================================================================
# Group Chat Handlers: New Members Greeting
# ===================================================================

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets new members when they join the group chat."""
    message = update.effective_message
    if not message or not message.new_chat_members:
        return

    greeting_template = await faq_manager.get_template("greeting.md")

    for member in message.new_chat_members:
        # Don't greet ourselves or bots
        if member.is_bot:
            continue

        # Use full Telegram name (not username) escaped for HTML
        user_name = html.escape(member.full_name)

        text = greeting_template.replace("{user_name}", user_name)
        text = text.replace("{bot_username}", config.BOT_USERNAME)
        formatted_text = format_telegram_html(text)

        try:
            await message.reply_text(
                text=formatted_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error("Error sending greeting to %s: %s", user_name, e)


# ===================================================================
# Private Chat: Basic Commands
# ===================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the welcome message and main menu."""
    user = update.effective_user
    welcome_text = (
        f"🎲 <b>Benvenuto/a {html.escape(user.first_name)} nel Bot di Supporto della Gilda del Grifone!</b> 🦅\n\n"
        "Cosa desideri fare?\n"
        "• Sfogliare le nostre <b>FAQ</b> con tutte le risposte su tesseramento, orari e giochi.\n"
        "• <b>Cercare</b> una risposta scrivendomi direttamente una parola chiave.\n"
        "• <b>Aprire un ticket</b> per chiedere qualcosa agli organizzatori.\n"
        "• Consultare i contatti degli <b>Admin</b>."
    )
    keyboard = build_main_menu_keyboard()
    await update.message.reply_text(
        text=welcome_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends helpful usage instructions."""
    help_text = (
        "ℹ️ <b>Guida ai comandi del Bot della Gilda:</b>\n\n"
        "/start o /menu - Mostra il menu principale\n"
        "/ticket - Apri un ticket per fare una domanda agli organizzatori\n"
        "/admin - Mostra l'elenco degli amministratori e referenti\n"
        "/annulla - Annulla l'operazione in corso (es. apertura ticket)\n\n"
        "💡 <i>Suggerimento:</i> Puoi scrivermi qualsiasi domanda direttamente in chat e cercherò per te tra le risposte più pertinenti!"
    )
    await update.message.reply_text(
        text=help_text,
        reply_markup=build_main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the admins template."""
    admin_text = await faq_manager.get_template("admins.md")
    formatted_admin = format_telegram_html(admin_text)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎫 Apri un Ticket", callback_data="menu_open_ticket")],
        [InlineKeyboardButton("🏠 Menu Principale", callback_data="menu_main")],
    ])
    await update.message.reply_text(
        text=formatted_admin,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def cmd_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates opening a ticket via command."""
    context.user_data["waiting_for_ticket"] = True
    text = (
        "🎫 <b>Apertura Ticket di Supporto</b>\n\n"
        "Scrivi qui sotto in un unico messaggio la tua domanda o richiesta per lo staff della Gilda del Grifone.\n\n"
        "<i>(Se vuoi annullare, digita /annulla)</i>"
    )
    await update.message.reply_text(text=text, parse_mode=ParseMode.HTML)



async def cmd_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels current pending action."""
    if context.user_data.get("waiting_for_ticket"):
        context.user_data["waiting_for_ticket"] = False
        await update.message.reply_text(
            "❌ Apertura ticket annullata.",
            reply_markup=build_main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "Nessuna operazione in corso da annullare.",
            reply_markup=build_main_menu_keyboard(),
        )

# ===================================================================
# FAQ Navigation Callbacks
# ===================================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Router for all inline keyboard callback queries."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data == "menu_main":
        welcome_text = (
            "🎲 <b>Menu Principale - Gilda del Grifone</b> 🦅\n\n"
            "Come possiamo aiutarti?\n"
            "• Sfoglia o cerca nelle <b>FAQ</b>\n"
            "• <b>Apri un ticket</b> di supporto\n"
            "• Consulta i contatti <b>Admin</b>"
        )
        try:
            await query.edit_message_text(
                text=welcome_text,
                reply_markup=build_main_menu_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await query.message.reply_text(
                text=welcome_text,
                reply_markup=build_main_menu_keyboard(),
                parse_mode=ParseMode.HTML,
            )

    elif data == "menu_browse":
        index = await faq_manager.get_faq_index()
        keyboard = []

        # Categories
        for cat in index.get("categories", []):
            keyboard.append([
                InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"cat:{cat['id']}")
            ])

        # Root files
        for root_file in index.get("root_files", []):
            keyboard.append([
                InlineKeyboardButton(f"📄 {root_file['title']}", callback_data=f"faq:{root_file['id']}")
            ])

        keyboard.append([InlineKeyboardButton("🏠 Menu Principale", callback_data="menu_main")])

        browse_text = "📚 <b>Seleziona una categoria o una domanda:</b>"
        try:
            await query.edit_message_text(
                text=browse_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await query.message.reply_text(
                text=browse_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML,
            )

    elif data == "menu_search_prompt":
        prompt_text = (
            "🔍 <b>Ricerca nelle FAQ:</b>\n\n"
            "Scrivi semplicemente qui in chat una parola o la tua domanda (es. <i>iscrizione</i>, <i>quota</i>, <i>sede</i>, <i>orari</i>) "
            "e cercherò per te le risposte più pertinenti!\n\n"
            "Oppure clicca sotto per tornare al menu."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 Sfoglia tutte le FAQ", callback_data="menu_browse")],
            [InlineKeyboardButton("🏠 Menu Principale", callback_data="menu_main")],
        ])
        await query.message.reply_text(text=prompt_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    elif data == "menu_admins":
        admin_text = await faq_manager.get_template("admins.md")
        formatted_admin = format_telegram_html(admin_text)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎫 Apri un Ticket", callback_data="menu_open_ticket")],
            [InlineKeyboardButton("🏠 Menu Principale", callback_data="menu_main")],
        ])
        await query.message.reply_text(
            text=formatted_admin,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    elif data == "menu_open_ticket":
        context.user_data["waiting_for_ticket"] = True
        prompt = (
            "🎫 <b>Apertura Ticket di Supporto</b>\n\n"
            "Scrivi qui sotto in un messaggio la tua domanda o richiesta per lo staff della Gilda.\n\n"
            "<i>(Invia /annulla per uscire senza inviare il ticket)</i>"
        )
        await query.message.reply_text(text=prompt, parse_mode=ParseMode.HTML)

    elif data.startswith("cat:"):
        cat_id = data.split(":", 1)[1]
        category = await faq_manager.get_category_by_id(cat_id)
        if not category:
            await query.message.reply_text("Categoria non trovata.", reply_markup=build_main_menu_keyboard())
            return

        keyboard = []
        for f in category.get("files", []):
            keyboard.append([
                InlineKeyboardButton(f"📄 {f['title']}", callback_data=f"faq:{f['id']}")
            ])

        keyboard.append([InlineKeyboardButton("🔙 Tutte le Categorie", callback_data="menu_browse")])
        keyboard.append([InlineKeyboardButton("🏠 Menu Principale", callback_data="menu_main")])

        cat_text = f"📁 <b>Categoria: {html.escape(category['name'])}</b>\n\nScegli una domanda da consultare:"
        try:
            await query.edit_message_text(
                text=cat_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await query.message.reply_text(
                text=cat_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML,
            )

    elif data.startswith("faq:"):
        faq_id = data.split(":", 1)[1]
        faq_item = await faq_manager.get_faq_by_id(faq_id)
        if not faq_item:
            await query.message.reply_text("FAQ non trovata.", reply_markup=build_main_menu_keyboard())
            return

        content, images = await faq_manager.load_faq_file(faq_item["path"])

        # Send any associated images first
        for img in images:
            try:
                if img.startswith("http://") or img.startswith("https://"):
                    await query.message.reply_photo(photo=img)
                elif os.path.exists(img):
                    with open(img, "rb") as photo_file:
                        await query.message.reply_photo(photo=photo_file)
            except Exception as e:
                logger.warning("Could not send photo %s: %s", img, e)

        # Build buttons below the answer
        keyboard = [
            [InlineKeyboardButton("📚 Torna alle FAQ", callback_data="menu_browse")],
            [InlineKeyboardButton("🎫 Apri un Ticket", callback_data="menu_open_ticket")],
            [InlineKeyboardButton("🏠 Menu Principale", callback_data="menu_main")],
        ]

        formatted_content = format_telegram_html(content)
        await query.message.reply_text(
            text=formatted_content,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


    elif data.startswith("ticket_"):
        await handle_admin_ticket_callback(update, context)

# ===================================================================
# Support Ticket Formatting & Helpers
# ===================================================================

def format_ticket_message(ticket: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Generates the HTML message and keyboard for a ticket in the admin chat."""
    tid = ticket["id"]
    uid = ticket["user_id"]
    name = html.escape(ticket.get("user_full_name") or "Utente")
    username = ticket.get("username")
    uname = f"@{html.escape(username)}" if username else "Non impostato"
    question = html.escape(ticket.get("question") or "")
    status = ticket.get("status", "open")

    if status == "accepted":
        admin_info = html.escape(ticket.get("accepted_by_name") or "Admin")
        status_line = f"🔵 <b>In carico a:</b> {admin_info}"
        buttons = [
            [
                InlineKeyboardButton("🔒 Chiudi Ticket", callback_data=f"ticket_close:{tid}"),
                InlineKeyboardButton("🔄 Riapri Ticket", callback_data=f"ticket_reopen:{tid}"),
            ]
        ]
    elif status == "closed":
        admin_info = html.escape(ticket.get("closed_by_name") or "Admin")
        status_line = f"🔴 <b>Chiuso da:</b> {admin_info}"
        buttons = [
            [InlineKeyboardButton("🔄 Riapri Ticket", callback_data=f"ticket_reopen:{tid}")]
        ]
    else:  # open
        status_line = "🟡 <b>Aperto</b>"
        buttons = [
            [
                InlineKeyboardButton("✅ Prendi in carico", callback_data=f"ticket_accept:{tid}"),
                InlineKeyboardButton("🔒 Chiudi Ticket", callback_data=f"ticket_close:{tid}"),
            ]
        ]

    # User link for direct contact
    user_link = f'<a href="tg://user?id={uid}">{name}</a>'

    text = (
        f"🎫 <b>TICKET #{tid}</b>\n\n"
        f"👤 <b>Utente:</b> {user_link}\n"
        f"🏷 <b>Username:</b> {uname}\n"
        f"🆔 <b>Telegram ID:</b> <code>{uid}</code>\n\n"
        f"❓ <b>Domanda:</b>\n{question}\n\n"
        f"📊 <b>Stato:</b> {status_line}\n\n"
        f"💡 <i>Per rispondere, rispondi a questo messaggio con:</i>\n"
        f"<code>/r &lt;testo risposta&gt;</code>"
    )

    return text, InlineKeyboardMarkup(buttons)

# ===================================================================
# Private Chat: Text Message Handler (Ticket creation & Fuzzy Search)
# ===================================================================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming text messages in private chats."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not message.text or not chat:
        return

    # Ignore group messages for search/ticket flows
    if chat.type != "private":
        return

    text = message.text.strip()

    # 1. Check if user is opening a ticket
    if context.user_data.get("waiting_for_ticket"):
        context.user_data["waiting_for_ticket"] = False

        # Create ticket in database
        ticket_id = database.create_ticket(
            user_id=user.id,
            user_full_name=user.full_name,
            username=user.username,
            question=text,
        )

        # Notify user
        confirmation = (
            f"✅ <b>Ticket #{ticket_id} inviato con successo!</b>\n\n"
            "I nostri amministratori hanno ricevuto la tua richiesta.\n"
            "Ti risponderemo direttamente qui appena possibile. Grazie per la pazienza! 🎲"
        )
        await message.reply_text(
            text=confirmation,
            reply_markup=build_main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )

        # Send ticket to admin chat
        if config.TICKET_CHAT_ID:
            ticket = database.get_ticket(ticket_id)
            if ticket:
                admin_text, admin_keyboard = format_ticket_message(ticket)
                try:
                    admin_msg = await context.bot.send_message(
                        chat_id=config.TICKET_CHAT_ID,
                        text=admin_text,
                        reply_markup=admin_keyboard,
                        parse_mode=ParseMode.HTML,
                    )
                    database.set_ticket_admin_message_id(ticket_id, admin_msg.message_id)
                except Exception as e:
                    logger.error("Failed to forward ticket #%s to admin chat %s: %s", ticket_id, config.TICKET_CHAT_ID, e)
        else:
            logger.warning("TICKET_CHAT_ID is not configured. Ticket #%s saved to DB only.", ticket_id)
        return

    # 2. Otherwise, treat text as an FAQ search query
    results = await faq_manager.search_faqs(text, limit=4)
    if results:
        keyboard = []
        for r in results:
            keyboard.append([
                InlineKeyboardButton(f"📄 {r['title']}", callback_data=f"faq:{r['id']}")
            ])
        keyboard.append([InlineKeyboardButton("🎫 Nessuna di queste? Apri un Ticket", callback_data="menu_open_ticket")])
        keyboard.append([InlineKeyboardButton("🏠 Menu Principale", callback_data="menu_main")])

        reply_text = (
            f"🔍 <b>Ho trovato queste risposte per:</b> <i>{html.escape(text)}</i>\n\n"
            "Clicca sulla domanda che ti interessa per leggere i dettagli:"
        )
        await message.reply_text(
            text=reply_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🎫 Apri un Ticket di Supporto", callback_data="menu_open_ticket")],
            [InlineKeyboardButton("📚 Sfoglia tutte le Categorie", callback_data="menu_browse")],
            [InlineKeyboardButton("🏠 Menu Principale", callback_data="menu_main")],
        ]
        no_res_text = (
            f"🤔 Non ho trovato risposte specifiche per: <i>{html.escape(text)}</i>\n\n"
            "Vuoi aprire un ticket di supporto per chiedere direttamente al nostro staff?"
        )
        await message.reply_text(
            text=no_res_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
        )


# ===================================================================
# Admin Chat: Ticket Actions & Responses
# ===================================================================

async def handle_admin_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles admin actions on tickets (Accept, Close, Reopen)."""
    query = update.callback_query
    admin = update.effective_user
    data = query.data or ""

    if ":" not in data:
        return

    action, tid_str = data.split(":", 1)
    try:
        ticket_id = int(tid_str)
    except ValueError:
        return

    ticket = database.get_ticket(ticket_id)
    if not ticket:
        await query.answer("Ticket non trovato.", show_alert=True)
        return

    admin_name = admin.full_name
    admin_id = admin.id
    admin_mention = f'<a href="tg://user?id={admin_id}">{html.escape(admin_name)}</a>'

    if action == "ticket_accept":
        database.update_ticket_status(ticket_id, "accepted", admin_id, admin_name)
        updated_ticket = database.get_ticket(ticket_id)
        new_text, new_kb = format_ticket_message(updated_ticket)
        try:
            await query.edit_message_text(text=new_text, reply_markup=new_kb, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"ℹ️ L'admin {admin_mention} ha preso in carico il <b>Ticket #{ticket_id}</b>.",
            parse_mode=ParseMode.HTML,
        )
        await query.answer("Ticket preso in carico.")

    elif action == "ticket_close":
        database.update_ticket_status(ticket_id, "closed", admin_id, admin_name)
        updated_ticket = database.get_ticket(ticket_id)
        new_text, new_kb = format_ticket_message(updated_ticket)
        try:
            await query.edit_message_text(text=new_text, reply_markup=new_kb, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🔒 Il <b>Ticket #{ticket_id}</b> è stato chiuso da {admin_mention}.",
            parse_mode=ParseMode.HTML,
        )
        await query.answer("Ticket chiuso.")

    elif action == "ticket_reopen":
        database.update_ticket_status(ticket_id, "open")
        updated_ticket = database.get_ticket(ticket_id)
        new_text, new_kb = format_ticket_message(updated_ticket)
        try:
            await query.edit_message_text(text=new_text, reply_markup=new_kb, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🔄 Il <b>Ticket #{ticket_id}</b> è stato riaperto da {admin_mention}.",
            parse_mode=ParseMode.HTML,
        )
        await query.answer("Ticket riaperto.")

async def cmd_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /r command in the admin chat to send an answer directly to the user.
    Usage:
      - Reply to a ticket message: /r <risposta>
      - Or specify ticket ID: /r <ticket_id> <risposta>
    """
    message = update.effective_message
    admin = update.effective_user
    if not message or not admin:
        return

    raw_args = message.text.split(maxsplit=1)
    if len(raw_args) < 2:
        await message.reply_text(
            "⚠️ <b>Uso del comando /r:</b>\n"
            "1. Rispondi al messaggio del ticket con: <code>/r &lt;risposta per l'utente&gt;</code>\n"
            "2. Oppure scrivi: <code>/r &lt;id_ticket&gt; &lt;risposta per l'utente&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    payload = raw_args[1].strip()
    ticket = None
    response_text = ""

    # Check if replied to ticket message
    if message.reply_to_message:
        reply_msg_id = message.reply_to_message.message_id
        ticket = database.get_ticket_by_admin_message_id(reply_msg_id)
        response_text = payload

    # If not a reply, try extracting ticket ID from first word
    if not ticket:
        parts = payload.split(maxsplit=1)
        if len(parts) >= 2 and parts[0].isdigit():
            tid = int(parts[0])
            ticket = database.get_ticket(tid)
            response_text = parts[1].strip()

    if not ticket or not response_text:
        await message.reply_text(
            "⚠️ Impossibile individuare il ticket di riferimento.\n"
            "Assicurati di rispondere al messaggio del ticket oppure specifica l'ID (es. <code>/r 1 risposta</code>).",
            parse_mode=ParseMode.HTML,
        )
        return

    user_id = ticket["user_id"]
    ticket_id = ticket["id"]

    # Send message to the user
    user_msg = (
        f"📬 <b>Risposta al tuo Ticket #{ticket_id} - Gilda del Grifone</b>\n\n"
        f"Gentile {html.escape(ticket['user_full_name'])},\n"
        "i nostri amministratori hanno risposto alla tua richiesta:\n\n"
        f"💬 <i>{html.escape(response_text)}</i>\n\n"
        "---\n"
        "💡 Puoi consultare le nostre FAQ in qualsiasi momento usando il menu principale!\n"
        "Se hai altre domande, siamo sempre a tua disposizione! 🎲"
    )

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=user_msg,
            reply_markup=build_main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )

        # Record in DB
        database.add_ticket_response(ticket_id, admin.id, admin.full_name, response_text)

        await message.reply_text(
            f"✅ Risposta inviata con successo all'utente per il <b>Ticket #{ticket_id}</b>!",
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.error("Failed to send reply to user %s for ticket #%s: %s", user_id, ticket_id, e)
        await message.reply_text(
            f"❌ Errore nell'invio della risposta all'utente: {e}\n"
            "L'utente potrebbe aver bloccato il bot o non aver mai avviato una chat privata.",
            parse_mode=ParseMode.HTML,
        )


# ===================================================================
# Main Bot Initialization
# ===================================================================

def main():
    """Initializes database, sets up handlers, and starts polling."""
    # Initialize SQLite DB
    database.init_db()
    logger.info("SQLite Database initialized at %s", config.DATABASE_PATH)

    # Check configuration
    warnings = config.validate_config()
    for w in warnings:
        logger.warning("CONFIG WARNING: %s", w)

    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n" + "=" * 60)
        print("❌ ERRORE: TELEGRAM_BOT_TOKEN non è configurato nel file .env!")
        print("Copia .env.example in .env e inserisci il token ottenuto da @BotFather.")
        print("=" * 60 + "\n")
        return

    # Build Telegram Bot application
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Register Command Handlers
    app.add_handler(CommandHandler(["start", "menu"], cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler(["admin", "admins"], cmd_admin))
    app.add_handler(CommandHandler("ticket", cmd_ticket))
    app.add_handler(CommandHandler("annulla", cmd_annulla))
    app.add_handler(CommandHandler("r", cmd_admin_reply))

    # Register Callback Query Handlers
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Register Message Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("Bot starting with polling... Username configured: %s", config.BOT_USERNAME)
    app.run_polling()


if __name__ == "__main__":
    main()

