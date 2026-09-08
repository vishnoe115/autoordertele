# AutoOrderTele — Telegram Auto Order Bot

Telegram auto-order bot dengan:

- katalog produk;
- pembelian dengan kuantitas;
- QRIS otomatis melalui KlikQRIS;
- fallback QRIS/DANA manual;
- webhook pembayaran;
- backup status polling;
- validasi signature dan nominal;
- admin confirmation;
- upload bukti pembayaran;
- pengiriman produk/file dari admin ke customer;
- SQLite persisten;
- FastAPI health endpoint;
- Docker Compose untuk Ubuntu 24.04.

## Struktur

```text
.
├── bot.py
├── config.py
├── db.py
├── jobs.py
├── logging_config.py
├── Dockerfile
├── docker-compose.yml
├── config-sample.env
├── handlers/
├── payments/
├── services/
├── web/
├── data/
└── tests/
```

## Deploy Docker di Ubuntu 24.04

Install Docker Engine + Compose plugin sesuai dokumentasi resmi Docker, lalu:

```bash
git clone https://github.com/vishnoe115/autoordertele.git
cd autoordertele

cp config-sample.env config.env
nano config.env

mkdir -p data logs
```

Jika menggunakan QRIS manual, upload gambar Anda ke:

```text
data/dana_qris.png
```

Build dan start:

```bash
docker compose up -d --build
```

Cek:

```bash
docker compose ps
docker compose logs -f autoordertele
curl http://127.0.0.1:8080/health
```

## Update

```bash
git pull --ff-only
docker compose up -d --build
docker image prune -f
```

## KlikQRIS

Jika KlikQRIS aktif:

```env
PUBLIC_BASE_URL=https://bot.example.com
WEBHOOK_PATH=/webhook/klikqris
KLIKRIS_API_KEY=...
KLIKRIS_MERCHANT_ID=...
KLIKRIS_SANDBOX=true
```

Callback yang dikirim saat create transaction menjadi:

```text
https://bot.example.com/webhook/klikqris
```

Sebelum production, gunakan sandbox KlikQRIS dan simulator pembayaran.

Jika ingin menonaktifkan pembayaran otomatis dan memakai DANA manual saja, kosongkan **keduanya**:

```env
KLIKRIS_API_KEY=
KLIKRIS_MERCHANT_ID=
```

## Reverse Proxy

Compose mengikat API ke `127.0.0.1:8080`, sehingga endpoint tidak dibuka langsung ke internet.

Contoh Nginx:

```nginx
server {
    listen 80;
    server_name bot.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Untuk KlikQRIS production, domain harus menggunakan HTTPS. Anda bisa menambahkan Certbot atau menggunakan reverse proxy lain yang mengelola TLS.

## Admin Commands

```text
/admin
/admin_add_product
```

`ADMIN_USER_ID` harus berupa numeric Telegram user ID.

## Data Persistence

Docker mem-mount:

```text
./data -> /app/data
./logs -> /app/logs
```

Database:

```text
data/orders.db
```

## Security

Jangan commit file berikut:

```text
config.env
.env
data/orders.db
data/dana_qris.png
```

File-file tersebut sudah dikecualikan oleh `.gitignore`.

## Test

Syntax check:

```bash
python check_install.py
```

Jika pytest tersedia:

```bash
pytest -q
```
