import secrets
from datetime import datetime

def rupiah(value): return f"Rp{int(value):,}".replace(',', '.')
def new_order_id(user_id): return f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{user_id}-{secrets.token_hex(2).upper()}"
def format_order(order): return (f"🧾 <b>Order #{order['order_id']}</b>\n👤 User ID: <code>{order['telegram_id']}</code>\n📦 {order['product_name']} x{order['quantity']}\n💰 <b>{rupiah(order['total_amount'])}</b>\n💳 {order['payment_method']}\n📌 <b>{order['status']}</b>")
