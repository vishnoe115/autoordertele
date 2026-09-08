import asyncio
from logging_config import setup_logging,logging,os,time
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
import uvicorn
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup,InputFile
from telegram.ext import ApplicationBuilder,CommandHandler,CallbackQueryHandler,MessageHandler,ConversationHandler,ContextTypes,filters
import db
from config import *
from klikqris import KlikQRIS
logging.basicConfig(level=getattr(logging,LOG.upper(),logging.INFO),format='%(asctime)s | %(levelname)s | %(message)s'); log=logging.getLogger('bot'); pay=KlikQRIS()
WAIT_QTY,WAIT_PAY,ADD_NAME,ADD_DESC,ADD_PRICE,SEND_PRODUCT=range(6)
def rp(x): return 'Rp{:,.0f}'.format(x).replace(',','.')
def ot(o): return f"🧾 <b>#{o['order_id']}</b>\n👤 <code>{o['telegram_id']}</code>\n📦 {o['product_name']} x{o['quantity']}\n💰 <b>{rp(o['total_amount'])}</b>\n💳 {o['payment_method']}\n📌 <b>{o['status']}</b>"
def ak(oid): return InlineKeyboardMarkup([[InlineKeyboardButton('✅ Konfirmasi Pembayaran',callback_data='a:paid:'+oid),InlineKeyboardButton('❌ Batalkan',callback_data='a:cancel:'+oid)],[InlineKeyboardButton('📦 Kirim Produk',callback_data='a:send:'+oid)]])
async def notify(c,oid,extra=''):
 o=db.order(oid)
 if o: await c.bot.send_message(ADMIN_USER_ID,ot(o)+'\n\n'+extra,parse_mode='HTML',reply_markup=ak(oid))
async def start(u,c):
 db.user(u.effective_user); await u.message.reply_text('Selamat datang! 👋',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🛍️ Lihat Produk',callback_data='catalog')]]))
async def catalog(u,c):
 q=u.callback_query; await q.answer(); ps=db.products(); rows=[[InlineKeyboardButton(f"{p['name']} — {rp(p['price'])}",callback_data=f"p:{p['id']}")] for p in ps]; await q.edit_message_text('🛍️ <b>Pilih Produk</b>',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(rows))
async def select_product(u,c):
 q=u.callback_query; await q.answer(); p=db.product(int(q.data.split(':')[1])); c.user_data['pid']=p['id']; await q.edit_message_text(f"📦 <b>{p['name']}</b>\n{p['description']}\n\nHarga: {rp(p['price'])}\n\nKirim jumlah:",parse_mode='HTML'); return WAIT_QTY
async def qty(u,c):
 try:n=int(u.message.text); assert 1<=n<=100
 except: await u.message.reply_text('Jumlah harus 1–100.'); return WAIT_QTY
 p=db.product(c.user_data['pid']); c.user_data['qty']=n;c.user_data['amount']=p['price']*n
 await u.message.reply_text(f"{p['name']} x{n}\nTotal: <b>{rp(p['price']*n)}</b>\n\nPilih pembayaran:",parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⚡ QRIS Otomatis — KlikQRIS',callback_data='pay:k')],[InlineKeyboardButton('📱 QRIS Manual — DANA',callback_data='pay:m')]]));return WAIT_PAY
async def payment(u,c):
 q=u.callback_query;await q.answer(); p=db.product(c.user_data['pid']);n=c.user_data['qty'];amount=c.user_data['amount'];oid=f"INV-{q.from_user.id}-{int(time.time())}"
 method='KLIKRIS' if q.data=='pay:k' else 'MANUAL_DANA';db.order_create(oid,q.from_user.id,p,n,amount,method)
 if method=='KLIKRIS':
  try:
   x=await pay.create(oid,amount,f"{p['name']} x{n}"); total=int(float(x['total_amount']));db.update_payment(oid,total=total,sig=x.get('signature'),qris=x.get('qris_url'),direct=x.get('direct_url'),expired=x.get('expired_at'))
   text=f"🧾 <b>{oid}</b>\n📦 {p['name']} x{n}\n💰 Bayar: <b>{rp(total)}</b>\n\nScan QRIS. Pembayaran akan terverifikasi otomatis."
   if x.get('qris_url'): await q.message.reply_photo(x['qris_url'],caption=text,parse_mode='HTML')
   else: await q.message.reply_text(text+'\n🔗 '+str(x.get('direct_url','-')),parse_mode='HTML')
   await notify(c,oid,'Menunggu pembayaran KlikQRIS.')
  except Exception: log.exception('create failed');db.cancel(oid);await q.message.reply_text('QRIS otomatis gagal dibuat. Silakan ulangi dan pilih QRIS manual/DANA.')
 else:
  text=f"🧾 <b>{oid}</b>\n📦 {p['name']} x{n}\n💰 <b>{rp(amount)}</b>\n\n📱 DANA: <code>{DANA_NUMBER}</code>\nNama: {DANA_NAME}\n\nSetelah bayar tekan tombol di bawah."
  kb=InlineKeyboardMarkup([[InlineKeyboardButton('✅ Saya Sudah Bayar',callback_data='manual:'+oid)]])
  if os.path.exists(MANUAL_QRIS_IMAGE):
   with open(MANUAL_QRIS_IMAGE,'rb') as f: await q.message.reply_photo(InputFile(f),caption=text,parse_mode='HTML',reply_markup=kb)
  else: await q.message.reply_text(text+'\n\n⚠️ QRIS image belum dipasang.',parse_mode='HTML',reply_markup=kb)
  await notify(c,oid,'Menunggu konfirmasi pembayaran manual DANA.')
 c.user_data.clear();return ConversationHandler.END
async def manual(u,c):
 q=u.callback_query;await q.answer();oid=q.data.split(':',1)[1];o=db.order(oid)
 if o and o['telegram_id']==q.from_user.id: await q.message.reply_text('Notifikasi pembayaran dikirim ke admin. Kirim bukti pembayaran jika diperlukan.');await notify(c,oid,'⚠️ Customer menekan Saya Sudah Bayar.')
async def proof(u,c):
 if not u.message.photo:return
 os_= [o for o in db.recent(50) if o['telegram_id']==u.effective_user.id and o['status']=='PENDING']
 if not os_:return
 o=os_[0];fid=u.message.photo[-1].file_id;db.proof(o['order_id'],fid);await u.message.reply_text('📎 Bukti diterima.');await c.bot.send_photo(ADMIN_USER_ID,fid,caption=f"Bukti {o['order_id']}");await notify(c,o['order_id'],'Ada bukti pembayaran baru.')
async def admin(u,c):
 if u.effective_user.id!=ADMIN_USER_ID:return
 await u.message.reply_text('🔐 Admin',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🧾 Order Terbaru',callback_data='a:orders')],[InlineKeyboardButton('📦 Produk',callback_data='a:products')]]))
async def a_orders(u,c):
 q=u.callback_query;await q.answer()
 if q.from_user.id!=ADMIN_USER_ID:return
 for o in db.recent(10):await q.message.reply_text(ot(o),parse_mode='HTML',reply_markup=ak(o['order_id']))
async def a_products(u,c):
 q=u.callback_query;await q.answer()
 if q.from_user.id==ADMIN_USER_ID: await q.message.reply_text('\n'.join(f"#{p['id']} {p['name']} — {rp(p['price'])}" for p in db.products(False)) or 'Kosong')
async def a_paid(u,c):
 q=u.callback_query;await q.answer();
 if q.from_user.id!=ADMIN_USER_ID:return
 oid=q.data.split(':')[2];changed=db.paid(oid,'Admin confirmed');o=db.order(oid);await q.edit_message_reply_markup(reply_markup=None)
 if o: await q.message.reply_text('✅ Payment confirmed.');await c.bot.send_message(o['telegram_id'],f"✅ Pembayaran diterima untuk <b>{oid}</b>. Admin akan mengirim produk/detail.",parse_mode='HTML')
async def a_cancel(u,c):
 q=u.callback_query;await q.answer();
 if q.from_user.id!=ADMIN_USER_ID:return
 oid=q.data.split(':')[2];db.cancel(oid);o=db.order(oid);await q.edit_message_reply_markup(reply_markup=None);await q.message.reply_text('❌ Order dibatalkan.')
 if o:await c.bot.send_message(o['telegram_id'],f"❌ Order <b>{oid}</b> dibatalkan.",parse_mode='HTML')
async def a_send_start(u,c):
 q=u.callback_query;await q.answer();
 if q.from_user.id!=ADMIN_USER_ID:return ConversationHandler.END
 oid=q.data.split(':')[2];o=db.order(oid)
 if not o:return ConversationHandler.END
 if o['status']!='PAID':await q.message.reply_text('⚠️ Order belum PAID.');return ConversationHandler.END
 c.user_data['send_oid']=oid;await q.message.reply_text(f'📦 Kirim pesan produk/detail untuk {oid}. Bot akan menyalinnya ke customer.');return SEND_PRODUCT
async def a_send(u,c):
 oid=c.user_data.get('send_oid');o=db.order(oid) if oid else None
 if not o:return ConversationHandler.END
 await u.message.copy(chat_id=o['telegram_id']);await u.message.reply_text('✅ Detail/produk terkirim.');c.user_data.clear();return ConversationHandler.END
async def add_start(u,c):
 if u.effective_user.id!=ADMIN_USER_ID:return ConversationHandler.END
 await u.message.reply_text('Nama produk:');return ADD_NAME
async def add_name(u,c):c.user_data['n']=u.message.text;await u.message.reply_text('Deskripsi:');return ADD_DESC
async def add_desc(u,c):c.user_data['d']=u.message.text;await u.message.reply_text('Harga angka:');return ADD_PRICE
async def add_price(u,c):
 try:p=int(u.message.text);assert p>0
 except:await u.message.reply_text('Harga tidak valid.');return ADD_PRICE
 i=db.add_product(c.user_data['n'],c.user_data['d'],p);c.user_data.clear();await u.message.reply_text(f'✅ Produk #{i} ditambahkan.');return ConversationHandler.END
async def webhook(req,c):
 try:j=await req.json()
 except:return JSONResponse({'ok':False},status_code=400)
 d=j.get('data') if isinstance(j.get('data'),dict) else j;oid=d.get('order_id');st=str(d.get('status','')).upper();sig=d.get('signature');total=d.get('total_amount') or d.get('amount_paid')
 if not oid:return JSONResponse({'ok':False,'error':'missing_order_id'},status_code=400)
 o=db.order(oid)
 if not o:return JSONResponse({'ok':True,'ignored':'unknown_order'})
 if o['status']=='PAID':return JSONResponse({'ok':True,'ignored':'already_paid'})
 if o['klik_signature'] and sig and o['klik_signature']!=sig:return JSONResponse({'ok':False,'error':'invalid_signature'},status_code=403)
 if st in ('PAID','SUCCESS'):
  if total is not None and int(float(total))!=int(o['total_amount']):return JSONResponse({'ok':False,'error':'amount_mismatch'},status_code=400)
  if db.paid(oid,'KlikQRIS webhook'):await notify(c,oid,'💸 KlikQRIS payment verified automatically.');await c.bot.send_message(o['telegram_id'],f'✅ Pembayaran <b>{oid}</b> berhasil.',parse_mode='HTML')
 elif st=='EXPIRED':db.update_payment(oid,status='EXPIRED')
 return JSONResponse({'ok':True})
async def poll(c):
 for o in db.pending_auto():
  try:
   x=await pay.status(o['order_id']);st=str(x.get('status','')).upper()
   if st in ('SUCCESS','PAID') and int(float(x.get('total_amount',o['total_amount'])))==int(o['total_amount']):
    if db.paid(o['order_id'],'KlikQRIS polling'):await notify(c,o['order_id'],'💸 Payment found by backup status polling.');await c.bot.send_message(o['telegram_id'],'✅ Pembayaran berhasil diverifikasi.')
   elif st=='EXPIRED':db.update_payment(o['order_id'],status='EXPIRED')
  except Exception:log.exception('poll failed for %s',o['order_id'])
def build():
 a=ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(False).build()
 purchase=ConversationHandler(entry_points=[CallbackQueryHandler(select_product,r'^p:\d+$')],states={WAIT_QTY:[MessageHandler(filters.TEXT&~filters.COMMAND,qty)],WAIT_PAY:[CallbackQueryHandler(payment,r'^pay:')]},fallbacks=[CommandHandler('start',start)],per_message=False,per_chat=True,per_user=True,conversation_timeout=600)
 send=ConversationHandler(entry_points=[CallbackQueryHandler(a_send_start,r'^a:send:')],states={SEND_PRODUCT:[MessageHandler(filters.ALL&~filters.COMMAND,a_send)]},fallbacks=[CommandHandler('admin',admin)],per_message=False,per_chat=True,per_user=True)
 add=ConversationHandler(entry_points=[CommandHandler('admin_add_product',add_start)],states={ADD_NAME:[MessageHandler(filters.TEXT&~filters.COMMAND,add_name)],ADD_DESC:[MessageHandler(filters.TEXT&~filters.COMMAND,add_desc)],ADD_PRICE:[MessageHandler(filters.TEXT&~filters.COMMAND,add_price)]},fallbacks=[CommandHandler('admin',admin)],per_message=False,per_chat=True,per_user=True)
 a.add_handler(CommandHandler('start',start));a.add_handler(CommandHandler('admin',admin));a.add_handler(add);a.add_handler(send);a.add_handler(purchase);a.add_handler(CallbackQueryHandler(catalog,r'^catalog$'));a.add_handler(CallbackQueryHandler(manual,r'^manual:'));a.add_handler(CallbackQueryHandler(a_paid,r'^a:paid:'));a.add_handler(CallbackQueryHandler(a_cancel,r'^a:cancel:'));a.add_handler(CallbackQueryHandler(a_orders,r'^a:orders$'));a.add_handler(CallbackQueryHandler(a_products,r'^a:products$'));a.add_handler(MessageHandler(filters.PHOTO,proof));a.job_queue.run_repeating(poll,interval=POLL,first=10);return a
async def main():
 validate();db.init();app=build();web=FastAPI()
 @web.get('/health')
 async def health():return {'ok':True}
 @web.post(WEBHOOK_PATH)
 async def wh(req:Request):return await webhook(req,app)
 s=uvicorn.Server(uvicorn.Config(web,host=HOST,port=PORT,log_level=LOG.lower()))
 await app.initialize();await app.start();await app.updater.start_polling()
 try:await s.serve()
 finally:await app.updater.stop();await app.stop();await app.shutdown()
if __name__=='__main__':asyncio.run(main())
