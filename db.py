import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone
DB=Path('data/orders.db'); DB.parent.mkdir(parents=True,exist_ok=True)
def now(): return datetime.now(timezone.utc).isoformat()
def con():
 c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; c.execute('PRAGMA journal_mode=WAL'); return c
def init():
 with con() as d:
  d.executescript('''CREATE TABLE IF NOT EXISTS users(telegram_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,created_at TEXT,updated_at TEXT);
  CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT DEFAULT '',price INTEGER NOT NULL,active INTEGER DEFAULT 1,created_at TEXT);
  CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT UNIQUE NOT NULL,telegram_id INTEGER NOT NULL,product_id INTEGER NOT NULL,product_name TEXT NOT NULL,unit_price INTEGER NOT NULL,quantity INTEGER NOT NULL,amount INTEGER NOT NULL,total_amount INTEGER NOT NULL,payment_method TEXT NOT NULL,status TEXT NOT NULL,klik_signature TEXT,qris_url TEXT,direct_url TEXT,expired_at TEXT,proof_file_id TEXT,admin_note TEXT,created_at TEXT,updated_at TEXT);''')
  if d.execute('SELECT COUNT(*) FROM products').fetchone()[0]==0:
   f=Path('data/seed_products.json')
   if f.exists():
    for p in json.loads(f.read_text()): d.execute('INSERT INTO products(name,description,price,active,created_at) VALUES(?,?,?,?,?)',(p['name'],p.get('description',''),p['price'],p.get('active',1),now()))
def user(u):
 with con() as d:d.execute('''INSERT INTO users VALUES(?,?,?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name,updated_at=excluded.updated_at''',(u.id,u.username or '',u.first_name or '',now(),now()))
def products(active=True):
 with con() as d:return d.execute('SELECT * FROM products '+('WHERE active=1 ' if active else '')+'ORDER BY id').fetchall()
def product(i):
 with con() as d:return d.execute('SELECT * FROM products WHERE id=?',(i,)).fetchone()
def add_product(n,desc,price):
 with con() as d:return d.execute('INSERT INTO products(name,description,price,active,created_at) VALUES(?,?,?,?,?)',(n,desc,price,1,now())).lastrowid
def order_create(oid,uid,p,q,amount,method):
 with con() as d:d.execute('''INSERT INTO orders(order_id,telegram_id,product_id,product_name,unit_price,quantity,amount,total_amount,payment_method,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(oid,uid,p['id'],p['name'],p['price'],q,amount,amount,method,'PENDING',now(),now()))
def order(oid):
 with con() as d:return d.execute('SELECT * FROM orders WHERE order_id=?',(oid,)).fetchone()
def update_payment(oid,total=None,sig=None,qris=None,direct=None,expired=None,status=None):
 vals=[]; fs=[]
 for k,v in [('total_amount',total),('klik_signature',sig),('qris_url',qris),('direct_url',direct),('expired_at',expired),('status',status)]:
  if v is not None: fs.append(k+'=?'); vals.append(v)
 if fs:
  fs.append('updated_at=?'); vals.append(now()); vals.append(oid)
  with con() as d:d.execute('UPDATE orders SET '+','.join(fs)+' WHERE order_id=?',vals)
def paid(oid,note=''):
 with con() as d:
  r=d.execute('SELECT status FROM orders WHERE order_id=?',(oid,)).fetchone()
  if not r:return False
  if r['status']=='PAID':return False
  d.execute("UPDATE orders SET status='PAID',admin_note=?,updated_at=? WHERE order_id=?",(note,now(),oid));return True
def cancel(oid):
 with con() as d:d.execute("UPDATE orders SET status='CANCELLED',updated_at=? WHERE order_id=?",(now(),oid))
def proof(oid,fid):
 with con() as d:d.execute('UPDATE orders SET proof_file_id=?,updated_at=? WHERE order_id=?',(fid,now(),oid))
def recent(n=20):
 with con() as d:return d.execute('SELECT * FROM orders ORDER BY id DESC LIMIT ?',(n,)).fetchall()
def pending_auto():
 with con() as d:return d.execute("SELECT * FROM orders WHERE payment_method='KLIKRIS' AND status='PENDING'").fetchall()
