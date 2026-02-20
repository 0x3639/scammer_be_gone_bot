# Scammer Be Gone Bot — Development Roadmap

## Overview

Telegram bot that detects and publicly warns about impersonator/scammer accounts mimicking group admins. Monitors multiple groups in real-time and on a 5-minute periodic schedule.

---

## Phase 1: Foundation

**Goal:** Project scaffolding, configuration system, and database layer.

- [ ] Create project directory structure and `__init__.py` files
- [ ] Write `requirements.txt` with all dependencies
- [ ] Write `.gitignore` (ignore `.env`, `*.db`, `__pycache__`, etc.)
- [ ] Write `.env.example` with required environment variables
- [ ] Implement `bot/config.py` — YAML + env config loader with dataclasses
- [ ] Write `config.yaml` — protected admins, group IDs, thresholds, whitelist
- [ ] Implement `bot/persistence/models.py` — ObservedMember, AlertRecord dataclasses
- [ ] Implement `bot/persistence/database.py` — SQLite schema creation and CRUD operations

**Deliverable:** Config loads cleanly, database initializes with correct schema.

---

## Phase 2: Detection Engine

**Goal:** Build the core similarity detection system — the brain of the bot.

- [ ] Implement `bot/detection/charmap.py` — static character substitution maps
  - Leet speak: `0→o`, `1→i`, `3→e`, `4→a`, `5→s`, `7→t`, `8→b`
  - Symbols: `@→a`, `$→s`, `!→i`, `|→i`
  - Unicode: `ø→o`, `ö→o`, `é→e`, `ü→u`, and extended set
- [ ] Implement `bot/detection/normalizer.py` — canonical form generation
  - NFKD Unicode normalization
  - Lowercase conversion
  - Combining mark (accent/diacritic) stripping
  - Character map application
  - Non-alphanumeric stripping
- [ ] Implement `bot/detection/homoglyphs.py` — confusable character detection
  - Mixed-script detection (Cyrillic `а` vs Latin `a`)
  - Latin equivalent normalization using Unicode confusables database
- [ ] Implement `bot/detection/fuzzy.py` — fuzzy string matching
  - Levenshtein ratio (threshold >= 0.80)
  - Jaro-Winkler similarity (threshold >= 0.85)
  - Partial ratio for substring matching (threshold >= 0.90)
- [ ] Implement `bot/detection/engine.py` — SimilarityEngine orchestrator
  - Compose all 4 detection layers
  - Weighted composite scoring: `0.35*canonical + 0.30*homoglyph + 0.25*fuzzy + 0.10*display_name`
  - Alert level classification: LOW (log), MEDIUM (alert), HIGH (alert)
  - Short-circuit for protected admin user IDs and whitelisted users
- [ ] Write unit tests for all detection modules
  - Test known impersonation patterns: `sug0ibtc`, `sugo1btc`, Cyrillic variants
  - Test false negatives: ensure real impersonations are caught
  - Test false positives: ensure unrelated usernames are not flagged

**Deliverable:** `SimilarityEngine.check_user()` correctly identifies impersonators with >90% accuracy on test cases.

---

## Phase 3: Bot Integration

**Goal:** Wire detection engine into a working Telegram bot with real-time + periodic scanning.

- [ ] Implement `bot/alerts/alerter.py` — alert message formatting and sending
  - HTML-formatted warning messages with suspect/admin details
  - Cooldown tracking (default 1 hour per user per group)
  - Rate-limited sending with retry on 429 errors
- [ ] Implement `bot/handlers/message_handler.py` — real-time message scanning
  - Extract user info from every group message
  - Upsert sender into observed_members database
  - Run similarity check, delegate to alerter if suspicious
- [ ] Implement `bot/handlers/member_handler.py` — join event handling
  - Handle `ChatMemberUpdated` events for new member joins
  - Immediate similarity check on join
- [ ] Implement `bot/jobs/periodic_scan.py` — 5-minute periodic re-audit
  - Query all observed members from SQLite (no Telegram API calls)
  - Re-check each against current protected admin list
  - Batch processing with delays to avoid alert flooding
- [ ] Implement `bot/main.py` — application entry point
  - Register all handlers and commands
  - Initialize database and job queue
  - Configure `allowed_updates: ["message", "chat_member", "my_chat_member"]`

**Deliverable:** Bot runs, connects to Telegram, intercepts messages, and sends alerts for impersonators.

---

## Phase 4: Admin Interface

**Goal:** Runtime management commands for group admins.

- [ ] `/protect @username DisplayName` — add user to protected admin list
- [ ] `/unprotect @username` — remove user from protected list
- [ ] `/whitelist @username reason` — exempt a legitimate user from detection
- [ ] `/status` — show bot stats: protected admins, observed members, recent alerts, last scan time
- [ ] `/check @username` — manually run similarity check with detailed score breakdown
- [ ] Permission checks — verify command sender is a group admin before executing

**Deliverable:** Admins can manage the bot entirely from within Telegram.

---

## Phase 5: Deployment & Hardening

**Goal:** Production-ready Docker deployment with proper error handling.

- [ ] Write `Dockerfile` (Python 3.12-slim base)
- [ ] Write `docker-compose.yml` with volume mounts for config and data
- [ ] Add comprehensive logging throughout all modules
- [ ] Add error handling and graceful shutdown (SIGTERM handling)
- [ ] Handle edge cases:
  - Bot temporarily loses admin permissions
  - Database corruption recovery
  - Telegram API outages (reconnection logic)
- [ ] Write `README.md` with setup instructions:
  - BotFather setup (create bot, disable privacy mode)
  - Bot permissions needed (Delete messages, Ban users)
  - Configuration guide
  - Docker deployment steps

**Deliverable:** `docker-compose up` starts a production-ready bot.

---

## Future Enhancements (Post-MVP)

- [ ] Web dashboard for alert history and analytics
- [ ] Configurable auto-restrict/auto-ban modes
- [ ] Profile photo similarity detection (comparing admin vs suspect avatars)
- [ ] Telegram inline keyboard for admins to ban/dismiss directly from alert messages
- [ ] Multi-language alert messages
- [ ] Webhook mode (instead of polling) for lower latency at scale
- [ ] Admin notification via DM in addition to group alert

---

## Technical Notes

- **No "list all members" API:** Telegram Bot API cannot enumerate group members. The bot builds its member DB incrementally from observed messages and join events.
- **Privacy mode must be disabled:** The bot needs to see all group messages, not just commands.
- **User IDs are immutable:** The primary way to distinguish the real admin from an impersonator. Username and display name can be changed at any time.
- **Rate limits:** ~30 msg/sec across chats, ~20 msg/min per group. Alert cooldowns and queuing prevent hitting these.
