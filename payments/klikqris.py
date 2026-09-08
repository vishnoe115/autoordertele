import httpx
from config import API_KEY,MERCHANT_ID,SANDBOX,PUBLIC_BASE_URL,WEBHOOK_PATH
class KlikQRIS:
 def __init__(self): self.base='https://klikqris.com/api/sandbox' if SANDBOX else 'https://klikqris.com/api'
 def headers(self): return {'Content-Type':'application/json','x-api-key':API_KEY,'id_merchant':MERCHANT_ID}
 async def create(self,oid,amount,desc):
  p={'order_id':oid,'id_merchant':MERCHANT_ID,'amount':amount,'keterangan':desc,'callback_url':PUBLIC_BASE_URL+WEBHOOK_PATH}
  async with httpx.AsyncClient(timeout=30) as c:r=await c.post(self.base+'/qris/create',json=p,headers=self.headers()); r.raise_for_status(); j=r.json()
  if not j.get('status'): raise RuntimeError(j.get('message','KlikQRIS create failed'))
  return j['data']
 async def status(self,oid):
  async with httpx.AsyncClient(timeout=20) as c:r=await c.get(self.base+'/qris/status/'+oid,headers=self.headers()); r.raise_for_status(); j=r.json()
  if not j.get('status'): raise RuntimeError(j.get('message','KlikQRIS status failed'))
  return j['data']
