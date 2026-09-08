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

## Channel Bukti Pembayaran & Mention Owner

Versi ini dapat otomatis mencatat transaksi ke channel Telegram.

Tambahkan ke `config.env`:

```env
PAYMENT_CHANNEL_ID=-1001234567890
OWNER_MENTION_USERNAME=your_admin_username
OWNER_MENTION_LABEL=Owner
```

`OWNER_MENTION_USERNAME` ditulis tanpa `@`. Jika dikosongkan, bot menggunakan clickable mention berbasis `ADMIN_USER_ID`.

Sebelum menjalankan bot:

1. Tambahkan bot ke channel transaksi.
2. Jadikan bot admin atau berikan izin **Post Messages**.
3. Pastikan owner/admin bergabung di channel tersebut jika ingin menerima mention/notifikasi.
4. Gunakan ID channel format `-100...` pada `PAYMENT_CHANNEL_ID`.

Flow channel:

- User menekan **Saya Sudah Bayar** → channel mendapat notifikasi bahwa user mengklaim sudah membayar.
- User mengirim screenshot bukti → foto otomatis diposting ke channel dengan Order ID, customer, produk, total, metode, status, dan mention owner.
- Admin mengonfirmasi pembayaran manual → channel mendapat record **PEMBAYARAN TERVERIFIKASI**.
- KlikQRIS webhook sukses → channel mendapat record pembayaran otomatis.
- Jika webhook terlewat tetapi status poller mendeteksi pembayaran → channel tetap mendapat record pembayaran otomatis.

Bukti foto juga tetap dikirim ke private chat admin seperti sebelumnya.
