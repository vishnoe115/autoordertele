# Telegram Auto Order Bot — KlikQRIS + Manual DANA

Modular Telegram auto-order bot with KlikQRIS automatic QRIS and manual DANA/QRIS fallback.

## Features
- Product catalog and quantity selection
- KlikQRIS QRIS create + webhook + status polling
- Manual DANA/QRIS fallback
- Admin order notifications and manual payment confirmation
- Admin can send/copy product details to buyer
- SQLite database
- Rotating application logs and Telegram error handler
- FastAPI webhook
- systemd/Nginx examples
- GitHub Issues/PR templates
- Sandbox support

## Structure
```text
bot.py
config.py
database.py
logging_config.py
handlers/
payments/
services/
web/
jobs/
deploy/
data/
tests/
.github/
```

## Important security rule
Never commit `.env`, bot tokens, KlikQRIS API keys, database files, or your private QRIS image. `.gitignore` already excludes them.

## Deploy
```bash
git clone https://github.com/YOUR_USERNAME/telegram-auto-order-klikqris.git
cd telegram-auto-order-klikqris
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

For systemd:
```bash
sudo cp deploy/systemd/telegram-auto-order.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-auto-order
sudo journalctl -u telegram-auto-order -f
```

## Update
```bash
git pull --ff-only
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart telegram-auto-order
```

## Webhook
Set KlikQRIS callback to:
`https://YOUR_DOMAIN/webhook/klikqris`

Health:
`https://YOUR_DOMAIN/health`

## Testing
```bash
python3 check_install.py
python3 -m pytest -q
```

Before production, test KlikQRIS Sandbox and verify your webhook, signature validation, amount checks, and duplicate-payment handling.
