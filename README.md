# 🦅 GdG-Help-Bot - Bot Telegram per la "Gilda del Grifone" 🎲

Bot Telegram ufficiale per la gestione dell'accoglienza, delle FAQ dinamiche e del sistema di assistenza a ticket per l'associazione ludica **Gilda del Grifone**.

---

## 🌟 Caratteristiche Principali

### 1. 👥 Accoglienza Nuovi Membri nel Gruppo
- **Messaggio di benvenuto automatico:** Rileva l'ingresso di un nuovo membro nel gruppo Telegram dell'associazione.
- **Nome reale (non username):** Saluta la persona usando il suo nome visualizzato su Telegram (`first_name` / `full_name`).
- **Template Markdown personalizzabile:** Il testo è basato sul file `templates/greeting.md` (aggiornabile da repository o localmente).
- **Invito alla chat privata:** Al termine del benvenuto invita l'utente a cliccare sull'username del bot (variabile `BOT_USERNAME`, es. `@GdG_Help_Bot`) per consultare le FAQ o fare domande in privato, ricordando comunque che può scrivere anche nel gruppo pubblico.

### 2. 📚 Sistema FAQ Dinamico da GitHub
- **Sorgente Markdown da GitHub:** Le FAQ risiedono nella cartella `FAQ/` del repository GitHub e vengono caricate tramite URL raw configurabile via `.env` (con fallback locale).
- **Supporto Immagini:** Le risposte possono contenere immagini Markdown (es. `![Mappa](FAQ/images/sede_mappa.png)` o URL diretti). Il bot estrae le immagini e le invia all'utente insieme al testo.
- **Navigazione a Pulsanti (Inline Keyboard):** Menu interattivo con navigazione ad albero:
  - Sotto-cartelle = Categorie tematiche (es. *Iscrizioni e Tesseramento*, *Serate e Eventi*, *Regolamento*).
  - File `.md` = Singole risposte con titolo dedotto dall'intestazione H1 o dal nome del file.
  - Pulsanti `🔙 Torna indietro` e `🏠 Menu Principale`.
- **Motore di Ricerca Integrato (Fuzzy Search):** L'utente può semplicemente digitare una parola o domanda in chat (es. *"orari"*, *"iscrizione"*, *"quanto costa"*); il bot individua le risposte più pertinenti tramite algoritmi di similarità testuale.
- **Indice Automatico & GitHub Action:** 
  - Lo script `scripts/generate_index.py` crea un file leggero `faq_index.json` con id brevi, categorie e preview.
  - La GitHub Action `.github/workflows/update_faq_index.yml` rigenera e committa automaticamente l'indice ad ogni modifica dei file nella cartella `FAQ/`.

### 3. 🎫 Sistema di Supporto a Ticket & Chat Admin
- **Apertura Ticket:** Se un utente non trova risposta, può aprire un ticket inviando la propria domanda in chat.
- **Notifica nel Canale/Gruppo Admin (`TICKET_CHAT_ID`):**
  - Viene inviata una notifica formattata con ID ticket, nome utente, username, link diretto Telegram (`tg://user?id=...`) e testo della domanda.
- **Gestione Stato:**
  - Pulsante `[ ✅ Prendi in carico ]`: assegna il ticket all'admin che preme il pulsante e aggiorna il messaggio in chat indicando *"In carico a: [Nome Admin]"*.
  - Pulsante `[ 🔒 Chiudi Ticket ]`: chiude il ticket.
  - Pulsante `[ 🔄 Riapri Ticket ]`: riapre un ticket chiuso.
  - Notifiche nel gruppo admin ad ogni cambio di stato.
- **Risposta Diretta all'Utente (`/r`):**
  - Gli admin possono rispondere rispondendo direttamente al messaggio del ticket con:
    `/r Ciao! Abbiamo aggiunto la risposta nelle FAQ: ...`
  - Oppure specificando l'ID del ticket:
    `/r 1 Ciao! Ecco le informazioni richieste...`
  - Il bot recapiterà la risposta in privato all'utente e confermerà l'invio nel gruppo admin.
- **Database SQLite:** Tracciamento persistente dei ticket e storico risposte (`tickets.db`).

### 4. 🛡️ Elenco Contatti Admin
- Presenta un elenco fisso dei referenti dell'associazione formattato in Markdown (`templates/admins.md`).

---

## 📂 Struttura del Progetto

```text
GdG-Help-Bot/
├── main.py                     # Entrypoint del bot e gestore eventi/comandi
├── config.py                   # Caricamento e validazione configurazione (.env)
├── database.py                 # Gestore SQLite (ticket e risposte)
├── faq_manager.py              # Download da GitHub, parsing immagini, fuzzy search
├── requirements.txt            # Dipendenze Python
├── .env.example                # Template per le variabili d'ambiente
├── .gitignore                  # File e cartelle ignorati da git
├── .clineignore                # File ignorati dagli assistenti AI
├── faq_index.json              # File indice generato automaticamente
├── FAQ/                        # Cartella con le FAQ in formato Markdown
│   ├── Cos'è la Gilda del Grifone?.md
│   ├── Iscrizioni e Tesseramento/
│   │   ├── Come posso iscrivermi alla Gilda?.md
│   │   └── Quanto costa la quota associativa?.md
│   ├── Serate e Eventi/
│   │   ├── Dove e quando ci troviamo?.md
│   │   └── Posso venire anche se non conosco nessuno?.md
│   ├── Regolamento/
│   │   └── Regolamento dell'associazione.md
│   └── images/
│       └── sede_mappa.png
├── templates/                  # Template Markdown
│   ├── greeting.md             # Benvenuto nuovi membri
│   └── admins.md               # Elenco referenti e admin
├── scripts/
│   └── generate_index.py       # Script di indicizzazione delle FAQ
└── .github/
    └── workflows/
        └── update_faq_index.yml # Pipeline GitHub Action per auto-aggiornamento indice
```



---

## 🚀 Guida all'Installazione e Configurazione

### 1. Prerequisiti
- Python 3.10 o superiore.
- Un account Telegram e un token bot creato con [@BotFather](https://t.me/BotFather).
- Un gruppo Telegram di test/produzione dove inserire il bot.
- Un gruppo per gli admin dedicato alla gestione dei ticket (`TICKET_CHAT_ID`).

### 2. Creazione del Bot su Telegram (@BotFather)
1. Avvia una conversazione con [@BotFather](https://t.me/BotFather) su Telegram.
2. Invia `/newbot` e segui le istruzioni:
   - Scegli un nome (es. `Gilda del Grifone Help Bot`).
   - Scegli un username che termini con `bot` (es. `GdG_Help_Bot`).
3. Copia il token HTTP API fornito (es. `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
4. **Impostazioni Gruppo (Importante!):**
   - Invia `/setprivacy` a `@BotFather`, seleziona il tuo bot e imposta **Disable** (oppure aggiungi il bot come Amministratore del gruppo). Questo consente al bot di intercettare l'evento di ingresso dei nuovi membri.
   - Assicurati che nei gruppi il bot abbia il permesso di inviare messaggi.

### 3. Recuperare il `TICKET_CHAT_ID`
1. Crea un gruppo Telegram dedicato agli admin o usa un gruppo esistente.
2. Aggiungi il bot al gruppo admin.
3. Puoi scoprire l'ID della chat aggiungendo temporaneamente un bot come `@RawDataBot` o inviando un messaggio e consultando `https://api.telegram.org/bot<TUO_TOKEN>/getUpdates`.
4. Tipicamente gli ID dei supergruppi iniziano con `-100` (es. `-1001234567890`).

### 4. Installazione Dipendenze
Clona il repository ed entra nella cartella:
```bash
git clone https://github.com/tuo-utente/GdG-Help-Bot.git
cd GdG-Help-Bot
```

Crea un ambiente virtuale ed installa i pacchetti:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configurazione del file `.env`
Copia il file di esempio:
```bash
cp .env.example .env
```

Modifica `.env` con i tuoi parametri:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
BOT_USERNAME=@GdG_Help_Bot
TICKET_CHAT_ID=-1001234567890
GITHUB_REPO=tuo-utente/GdG-Help-Bot
GITHUB_BRANCH=main
DATABASE_PATH=tickets.db
USE_LOCAL_FALLBACK=true
FAQ_CACHE_TTL=300
```

### 6. Avvio del Bot
```bash
python3 main.py
```

---

## 📝 Gestione delle FAQ e dei Template

### Aggiungere o Modificare una FAQ
1. Per aggiungere una FAQ in una categoria esistente: crea un file `.md` dentro `FAQ/<Nome Categoria>/<Titolo Domanda>.md`.
2. Per creare una nuova categoria: crea una nuova sottocartella in `FAQ/` e inserisci i file `.md` al suo interno.
3. Per aggiungere una FAQ generale: crea il file `.md` direttamente dentro `FAQ/`.
4. **Titolo della domanda:** La prima riga del file deve iniziare con `# Titolo della domanda`, oppure il bot userà il nome del file (senza `.md`).
5. **Aggiunta di immagini:** Inserisci l'immagine nella cartella `FAQ/images/` e referenziala nel file Markdown con:
   ```markdown
   ![Descrizione dell'immagine](FAQ/images/nome_immagine.png)
   ```
6. **Aggiornamento dell'indice:**
   - In locale, esegui:
     ```bash
     python scripts/generate_index.py
     ```
   - Su GitHub, se fai il push su `main`, la **GitHub Action** inclusa rigenererà automaticamente `faq_index.json` senza bisogno di alcun intervento manuale!

---

## 🛠️ Comandi Disponibili

### Per gli Utenti:
- `/start` o `/menu` - Mostra il menu principale con i pulsanti interattivi.
- `/ticket` - Avvia la procedura guidata per aprire un ticket con gli organizzatori.
- `/admin` - Mostra la lista dei referenti dell'associazione.
- `/help` - Mostra una guida rapida ai comandi.
- `/annulla` - Annulla l'operazione in corso (es. apertura ticket).
- *Invio di testo libero:* cerca automaticamente tra le FAQ con fuzzy search.

### Per gli Admin (nel gruppo `TICKET_CHAT_ID`):
- `[ ✅ Prendi in carico ]` - Assegna il ticket all'admin e aggiorna il badge di stato.
- `[ 🔒 Chiudi Ticket ]` - Chiude il ticket.
- `[ 🔄 Riapri Ticket ]` - Riapre un ticket precedentemente chiuso.
- `/r <risposta>` - Rispondendo al messaggio del ticket, invia la risposta direttamente all'utente.
- `/r <id_ticket> <risposta>` - Invia la risposta all'utente specificando l'ID del ticket.

---

## 📄 Licenza
Progetto realizzato per l'associazione culturale e ludica **Gilda del Grifone**. Distribuito con licenza MIT.
