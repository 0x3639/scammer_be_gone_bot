# Telegram Impersonator Detection Bot

A Telegram bot that detects and warns against impersonator accounts in real-time. Scammers create usernames that visually mimic trusted community members (e.g., `@sug0ibtc` to impersonate `@sugoibtc`) and copy display names exactly, then DM users to steal funds. This bot catches them.

## How It Works

The bot uses a **4-layer detection engine** to identify impersonators:

1. **Canonical Normalization** — Strips leet-speak (`0`->`o`, `1`->`i`), accents, underscores, and Unicode tricks. If `sug0i_btc` normalizes to the same form as `sugoibtc`, it's a match.

2. **Homoglyph Detection** — Catches mixed-script attacks using the Unicode Consortium's confusables database. Detects Cyrillic `а` swapped for Latin `a`, Greek omicron for `o`, etc.

3. **Fuzzy String Matching** — Levenshtein distance, Jaro-Winkler similarity, and partial ratio matching catch close misspellings and appended strings like `sugoibtc_support`.

4. **Display Name Matching** — Flags users who copy a protected member's display name exactly but use a different username/account.

Any single layer exceeding its threshold triggers an alert. A weighted composite score provides an overall confidence level.

### Detection in Action

| Impersonator | Real Member | Score | Detected By |
|---|---|---|---|
| `@sug0ibtc` | `@sugoibtc` | 91% | Canonical match (0->o) |
| `@sugoi_btc` | `@sugoibtc` | 93% | Canonical match (underscore stripped) |
| `@sugοibtc` (Cyrillic o) | `@sugoibtc` | 93% | Homoglyph detection |
| `@ge0rgezge0rgez` | `@georgezgeorgez` | 100% | Canonical + homoglyph + fuzzy |
| `@totallyDifferent` with display name "Sugoi" | `@sugoibtc` "Sugoi" | flagged | Display name match |

### Alert Message

When an impersonator is detected, the bot posts a public warning:

```
⚠️ IMPERSONATOR ALERT ⚠️

User may be impersonating a known community member.

Suspect: @sug0ibtc ("Sugoi")
Real Member: @sugoibtc ("Sugoi")

Similarity: 91% | Detected: canonical match, homoglyph match

🔴 Do NOT send this user funds, keys, or personal info.
🔴 Trusted members will NEVER DM you first asking for money.

Admins — please review this account.
```

### Dual Detection Strategy

- **Real-time:** Every message and member-join event is checked instantly.
- **Periodic audit (every 5 min):** Re-scans all observed members against the protected list. Catches profile changes between messages or late additions to the protected list.

The bot builds its member database incrementally by observing messages and join events (the Telegram Bot API has no endpoint to list all group members).

## Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. `/newbot` — follow the prompts to get your **bot token**
3. `/setprivacy` — select your bot, then choose **Disable** (so the bot can see all group messages)
4. Add the bot to your group and **promote it to admin** with at minimum "Delete messages" permission

### 2. Get Your Group's Chat ID

After adding the bot to your group, send a message in the group, then run:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
```

Look for `"chat":{"id":-100XXXXXXXXXX}` in the response. That negative number is your chat ID.

### 3. Get User IDs for Protected Members

Forward a message from each protected member to [@userinfobot](https://t.me/userinfobot) on Telegram. It will reply with their user ID.

### 4. Configure

Copy the environment template and set your bot token:

```bash
cp .env.example .env
```

Edit `.env`:
```
BOT_TOKEN=your-bot-token-here
LOG_LEVEL=INFO
```

Edit `config.yaml` with your group and protected members:

```yaml
monitored_groups:
  - chat_id: -1001234567890
    name: "My Group"
    admins:
      - user_id: 123456789
        username: "admin_username"
        display_name: "Admin Display Name"
      - user_id: 987654321
        username: "trusted_member"
        display_name: "Trusted Member"
```

The `admins` list is not limited to actual Telegram admins — add any community member you want to protect from impersonation.

## Running with Docker

```bash
docker-compose up --build -d
```

Check logs:
```bash
docker-compose logs -f bot
```

Stop:
```bash
docker-compose down
```

## Running Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

## Admin Commands

These commands work in the group chat for Telegram admins:

| Command | Description |
|---|---|
| `/protect @user DisplayName` | Add a user to the protected list |
| `/unprotect @user` | Remove from protected list |
| `/whitelist @user reason` | Exempt a user from detection (reply to their message) |
| `/status` | Show bot stats: observed members, alerts sent, protected list |
| `/check @user` | Manually run a similarity check with full score breakdown |

## Configuration Reference

### Detection Thresholds

All thresholds in `config.yaml` can be tuned:

| Setting | Default | Description |
|---|---|---|
| `canonical_threshold` | 1.0 | Exact canonical form match |
| `homoglyph_threshold` | 0.85 | Unicode confusable match |
| `fuzzy_levenshtein_threshold` | 0.80 | Edit distance similarity |
| `fuzzy_jaro_winkler_threshold` | 0.85 | Prefix-weighted similarity |
| `fuzzy_partial_ratio_threshold` | 0.90 | Substring containment |
| `display_name_threshold` | 0.95 | Display name similarity |
| `composite_threshold` | 0.75 | Weighted composite score |

### Alert Settings

| Setting | Default | Description |
|---|---|---|
| `cooldown_seconds` | 3600 | Time before re-alerting on the same user (per group) |
| `send_delay_seconds` | 2 | Delay between alert sends to avoid rate limits |
| `periodic_scan_interval` | 300 | Seconds between full member audits |

## Tech Stack

- **Python 3.12+** with `python-telegram-bot` v22.x (async)
- **rapidfuzz** for fast fuzzy string matching (C++ backend)
- **confusable_homoglyphs** for Unicode confusable detection
- **SQLite** via `aiosqlite` for zero-ops persistence
- **Docker** for deployment
