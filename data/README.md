# Runtime data

Folder ini dipersist melalui Docker volume/bind mount.

- `orders.db` dibuat otomatis.
- `orders.db-wal` dan `orders.db-shm` adalah file SQLite WAL.
- Letakkan QRIS manual Anda sebagai `dana_qris.png`.
- Edit `seed_products.json` sebelum database pertama kali dibuat jika ingin seed awal berbeda.

File database dan QRIS pribadi tidak boleh di-commit.
