import logging, database as db
from payments.klikqris import KlikQRIS
from config import settings
log=logging.getLogger(__name__); client=KlikQRIS()
async def run(context):
    for order in db.list_pending_auto_orders():
        try:
            data=await client.status(order['order_id']); status=str(data.get('status','')).upper()
            if status in {'SUCCESS','PAID'}:
                total=int(float(data.get('total_amount',order['total_amount'])))
                if total!=int(order['total_amount']): log.error('Amount mismatch %s',order['order_id']); continue
                changed,_=db.mark_paid(order['order_id'],'KlikQRIS status polling')
                if changed:
                    await context.bot.send_message(settings.admin_user_id,f"💸 PAID otomatis\nOrder: <code>{order['order_id']}</code>",parse_mode='HTML')
                    await context.bot.send_message(order['telegram_id'],f"✅ <b>Pembayaran berhasil!</b>\nOrder: <code>{order['order_id']}</code>",parse_mode='HTML')
            elif status=='EXPIRED': db.update_order_payment(order['order_id'],status='EXPIRED')
        except Exception: log.exception('Payment polling failed: %s',order['order_id'])
