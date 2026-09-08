import logging
import database as db
from config import settings
log=logging.getLogger(__name__)
async def handle(request,bot):
    from fastapi.responses import JSONResponse
    try: payload=await request.json()
    except Exception:return JSONResponse({'ok':False,'error':'invalid_json'},status_code=400)
    data=payload.get('data') if isinstance(payload.get('data'),dict) else payload
    oid=data.get('order_id'); status=str(data.get('status','')).upper(); signature=data.get('signature'); total=data.get('total_amount')
    if not oid:return JSONResponse({'ok':False,'error':'missing_order_id'},status_code=400)
    order=db.get_order(oid)
    if not order:return JSONResponse({'ok':True,'ignored':'unknown_order'})
    if order['status']=='PAID':return JSONResponse({'ok':True,'ignored':'already_paid'})
    if order['signature'] and signature and order['signature']!=signature:return JSONResponse({'ok':False,'error':'invalid_signature'},status_code=403)
    if status in {'PAID','SUCCESS'}:
        try:
            if total is not None and int(float(total))!=int(order['total_amount']):return JSONResponse({'ok':False,'error':'amount_mismatch'},status_code=400)
        except Exception:return JSONResponse({'ok':False,'error':'invalid_amount'},status_code=400)
        changed,_=db.mark_paid(oid,'KlikQRIS webhook')
        if changed:
            await bot.send_message(order['telegram_id'],f"✅ <b>Pembayaran berhasil!</b>\nOrder: <code>{oid}</code>",parse_mode='HTML')
            await bot.send_message(settings.admin_user_id,f"💸 PAID via webhook\nOrder: <code>{oid}</code>",parse_mode='HTML')
    elif status=='EXPIRED':db.update_order_payment(oid,status='EXPIRED')
    return JSONResponse({'ok':True})
