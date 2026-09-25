# 🦅 Technical Documentation & Context: GdG-Help-Bot

## 📌 Project Overview
**GdG-Help-Bot** is an asynchronous Telegram Bot written in Python for **Gilda del Grifone**, an Italian board game and role-playing game association.

The bot serves two core functions:
1. **Community Welcoming (Group Chat):**
   - Automatically greets new members using their Telegram display name (`member.full_name`, not raw username).
   - Sends a customizable welcome message from a template (`templates/greeting.md`) supporting both HTML and Markdown.
   - **Anti-Flood Lifecycle:** Automatically deletes the previous welcome message whenever a new member joins, ensuring the chat history is never cluttered with obsolete greeting messages.
   - **Simultaneous Join Grouping:** If multiple members join in a single event, their names are concatenated into a single greeting.
   - **Persistent State:** Tracks the last greeting message ID in an SQLite `settings` table so the anti-flood cleanup works seamlessly across bot reboots.
   - Invites newcomers to direct-message the bot (`BOT_USERNAME`) for FAQs, tickets, and membership details.
2. **Helpdesk & Support (Private Chat):**
   - **Dynamic FAQs:** Directly served from Markdown files hosted in the bot's GitHub repository or local fallback.
   - **Rich Media Answers:** Parses and delivers images included in markdown files.
   - **Interactive Navigation & Search:** Offers both hierarchical inline button navigation and intelligent fuzzy text search.
   - **Ticket Management System:** Allows users to open support tickets that are forwarded to a dedicated staff chat (`TICKET_CHAT_ID`), tracked via SQLite, claimed/closed/reopened by admins, and answered directly via `/r`.
   - **Association Contacts:** Serves an admin list template (`admins.md`) with rich HTML links and role badges.

---

## 🏗️ Architectural Overview & Components

```text
                      +------------------------------+
                      |      Telegram Cloud API      |
                      +--------------+---------------+
                                     |
                     +---------------+---------------+
                     |                               |
              (Group Chat)                    (Private Chat)
                     |                               |
             [New Chat Member]               [Commands / Queries]
                     |                               |
                     v                               v
          +----------------------------------------------------+
          |                     main.py                        |
          |  - Dispatcher & Handlers (PTB v20+ async)          |
          |  - Group Greeting Handler (Anti-flood & grouping)  |
          |  - format_telegram_html() converter (HTML mode)    |
          |  - Inline Callback Router                          |
          |  - Text Message Handler (Tickets & Search)         |
          |  - Admin Action & Reply Handler (/r)               |
          +---------+------------------+------------------+----+
                    |                  |                  |
                    v                  v                  v
           +-----------------+ +---------------+ +------------------+
           |    config.py    | |  database.py  | |  faq_manager.py  |
           | - Env settings  | | - SQLite DB   | | - GitHub HTTP raw|
           | - Validation    | | - Tickets     | | - Image parser   |
           | - URL generator | | - Responses   | | - Fuzzy search   |
           |                 | | - Settings    | |                  |
           +-----------------+ +---------------+ +------------------+
                                                          |
                                            +-------------+-------------+
                                            |                           |
                                            v                           v
                                   [faq_index.json]                 [FAQ/**.md]
                                            ^
                                            | (Generated on push)
                              +----------------------------+
                              | scripts/generate_index.py  |
                              | GitHub Actions Workflow    |
                              +----------------------------+
```


---

## ⚙️ Module Responsibilities

### 1. `config.py`
- Loads `.env` configuration using `python-dotenv`.
- Computes `GITHUB_RAW_BASE_URL` based on `GITHUB_REPO` and `GITHUB_BRANCH`.
- Handles `BOT_USERNAME` normalization (ensures `@` prefix).
- Provides sanity checks via `validate_config()`.

### 2. `database.py`
- Manages connection lifecycle to `tickets.db` using a context manager `get_db()`.
- Tables:
  - `tickets`: stores `user_id`, `user_full_name`, `username`, `question`, `status` (`open`, `accepted`, `closed`), `admin_message_id`, `accepted_by_id`, `accepted_by_name`, `closed_by_id`, `closed_by_name`, `created_at`, `updated_at`.
  - `ticket_responses`: stores response text, admin ID/name, timestamp, and ticket foreign key.
  - `settings`: key-value table (`key`, `value`, `updated_at`) for persistent configuration and state (e.g., `last_welcome_message_id_{chat_id}`).
- Helper functions: `set_setting()`, `get_setting()`, `set_last_welcome_message_id()`, `get_last_welcome_message_id()`.

### 3. `faq_manager.py`
- Fetches remote `faq_index.json`, Markdown files, and templates from GitHub raw URLs asynchronously via `aiohttp`.
- Implements TTL caching (`FAQ_CACHE_TTL`) to avoid rate-limiting and maximize responsiveness.
- Seamless fallback to local repository files if GitHub is unreachable or in local development mode (`USE_LOCAL_FALLBACK=true` / `USE_LOCAL_FILES=true`).
- **Markdown Image Parser:** Regex-based extraction of `![alt](path)`. Resolves relative paths against the GitHub raw URL or local filesystem, allowing Telegram to send photos via `send_photo`. Automatically strips hidden `Keywords:` / `Tags:` lines from user-facing text.
- **Enhanced Search Engine:** Multi-tiered matching algorithm combining:
  1. Keywords / Tags exact & fuzzy matching (boost up to 100/100).
  2. Substring & word-level Levenshtein similarity against title words (e.g. "costo" matches "costa" at 80%+).
  3. Token set ratio across title, preview, and category names.

### 4. `scripts/generate_index.py` & GitHub Actions
- Scans `FAQ/` recursively.
- Subdirectories are treated as FAQ categories; root `.md` files are treated as general FAQs.
- Extracts metadata: titles, clean previews, and comma-separated `Keywords:` or `Tags:` lines.
- Calculates an 8-byte hex hash (`MD5`) for every item to serve as a compact ID.
- **Why?** Telegram limits `callback_data` on `InlineKeyboardButton` to **64 bytes**. Long file paths fail Telegram's API checks; short IDs (`cat:48c89781`, `faq:c5aa1004`) remain strictly under 15 bytes.
- `.github/workflows/update_faq_index.yml` runs the script upon every push touching `FAQ/**` and commits changes back to the repository.

### 5. `main.py`
- Registers handlers using `python-telegram-bot` v20+ async architecture.
- **Universal HTML Rendering:** Standardized on `ParseMode.HTML` across all messages and callbacks. Uses `format_telegram_html(text)` to safely translate Markdown syntax (`#`, `**`, `[text](url)`, `` `code` ``) to Telegram-supported HTML, preventing crashes caused by underscores in usernames or invite links.
- **Group Greeting Lifecycle:** Handles `handle_new_chat_members`, deletes the preceding welcome message via ID stored in SQLite `settings`, concatenates names for simultaneous joins, and stores the new message ID.
- Formats admin ticket notifications in HTML.
- Links user identities in admin notifications via `<a href="tg://user?id={uid}">{name}</a>` allowing admins to open a direct private chat.
- Provides `/r` command handling supporting both reply-to-message and explicit ticket ID arguments (`/r <id> <text>`).

---

## 🔒 Key Design Decisions & Best Practices

1. **Telegram Display Name vs Username:**
   - Group greetings strictly use `member.full_name` (First name + Last name) as requested, never raw usernames, which may be missing or unreadable.
2. **HTML Formatting & Fallback Translation (`ParseMode.HTML`):**
   - Telegram's legacy Markdown parser has severe drawbacks: single asterisk for bold (`*text*`), parse crashes when handles/links contain underscores (`_`), and non-support for raw HTML tags (`<b>`, `<a>`). Standardizing on `ParseMode.HTML` coupled with `format_telegram_html()` allows templates and FAQ files to use both native HTML tags and standard Markdown formatting reliably.
3. **Anti-Flood Group Welcomes with SQLite Persistence:**
   - Instead of flooding group chat history with endless greeting messages, the bot tracks `last_welcome_message_id_{chat_id}` in SQLite. When a new join event occurs, the previous greeting is cleanly deleted, keeping the chat uncluttered while preserving state across bot restarts.
4. **No External Search Engine Dependencies:**
   - Instead of spinning up Elasticsearch or Meilisearch, the bot uses Python's `thefuzz` (powered by `rapidfuzz` and C-Levenshtein). It is lightweight, executes in milliseconds over hundreds of FAQs, and runs completely in-memory.
5. **Resilience & Local Fallbacks:**
   - When deploying in airgapped, CI test, or local development environments, setting `USE_LOCAL_FALLBACK=true` or `USE_LOCAL_FILES=true` allows the bot to operate without network requests to GitHub.


