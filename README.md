# 🛡️ TrustHold_EscrowBot

A fully-featured Telegram escrow bot built with Python (aiogram 3).

## ✅ Features Implemented

| Feature | Status |
|---|---|
| Welcome message + menu | ✅ |
| User registration (auto on /start) | ✅ |
| Create escrow deal (5-step flow) | ✅ |
| Payment proof upload | ✅ |
| Funds secured status | ✅ |
| Seller completion submission (proof + wallet) | ✅ |
| Admin fund release | ✅ |
| Dispute system + evidence upload | ✅ |
| Admin panel (/admin) | ✅ |
| Ban/unban users | ✅ |
| Freeze deals | ✅ |
| Dispute resolution (buyer/seller wins) | ✅ |
| Broadcast messages | ✅ |
| Transaction history | ✅ |
| User stats + referral codes | ✅ |
| Admin logs | ✅ |
| Transaction statuses (8 states) | ✅ |
| Notifications to both parties | ✅ |
| Anti-scam (ban system) | ✅ |
| Escrow fee calculation | ✅ |

## 🚀 Setup

### 1. Clone / copy the files
```bash
cd escrow_bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your values
```

**Required values in `.env`:**
- `BOT_TOKEN` — Get from [@BotFather](https://t.me/BotFather)
- `ADMIN_IDS` — Your Telegram user ID (get from [@userinfobot](https://t.me/userinfobot))

### 4. Configure PostgreSQL
```bash
createdb trusthold_escrow
```

Set `DATABASE_URL` in `.env`:
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/trusthold_escrow
```

### 5. Initialize database
```bash
python database.py
```

### 6. Run the bot
```bash
python bot.py
```

## 🗂️ Project Structure

```
escrow_bot/
├── bot.py              # Entry point
├── config.py           # Configuration
├── database.py         # SQLAlchemy models
├── keyboards.py        # Telegram keyboards
├── handlers/
│   ├── common.py       # /start, terms, support
│   ├── deals.py        # Deal creation & listing
│   ├── payments.py     # Payment proof & fund release
│   ├── disputes.py     # Dispute system
│   └── admin.py        # Admin panel
├── requirements.txt
└── .env.example
```

## 🛠️ Admin Commands

| Command | Description |
|---|---|
| `/admin` | View stats dashboard |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/lookup <txn_id>` | View deal details |
| `/freeze <txn_id>` | Freeze a deal |
| `/disputes` | List open disputes |
| `/broadcast` | Send message to all users |

## 📌 Deal Status Flow

```
waiting_payment → payment_submitted → funds_secured → in_progress → completed
                                                           ↘ disputed
                      ↘ cancelled
```

## 🌐 Hosting

- **Free tier:** [Railway.app](https://railway.app) or [Render.com](https://render.com)
- **VPS:** Any Linux server (Ubuntu recommended)
- **Database:** PostgreSQL
