# Migrasi dari versi repository lama

Versi ini mengganti wiring utama bot dan Docker.

## Disarankan: backup runtime data

```bash
cp -a data data-backup
```

Jangan hapus database production tanpa sengaja.

## File/folder lama yang tidak lagi dipakai

Versi baru tidak membutuhkan implementasi lama berikut jika masih ada:

```text
services/delivery_service.py
services/order_service.py
services/payment_service.py
web/webhook.py
```

File tersebut boleh dihapus agar repository lebih bersih, tetapi tidak akan di-import oleh versi baru.

Folder `jobs/` tetap digunakan dan sekarang berisi `payment_checker.py`.

## Setelah mengganti source

```bash
cp config-sample.env config.env
nano config.env

mkdir -p data logs

docker compose down
docker compose up -d --build

docker compose ps
docker compose logs -f autoordertele
```

Database lama dengan tabel `users`, `products`, dan `orders` tetap kompatibel dengan schema versi ini.
