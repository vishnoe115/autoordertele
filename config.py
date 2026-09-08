import os
from dotenv import load_dotenv
load_dotenv()
def b(n,d=False): return os.getenv(n,str(d)).lower() in ('1','true','yes','on')
BOT_TOKEN=os.getenv('BOT_TOKEN',''); ADMIN_USER_ID=int(os.getenv('ADMIN_USER_ID','0')); PUBLIC_BASE_URL=os.getenv('PUBLIC_BASE_URL','').rstrip('/'); WEBHOOK_PATH=os.getenv('WEBHOOK_PATH','/webhook/klikqris'); API_KEY=os.getenv('KLIKRIS_API_KEY',''); MERCHANT_ID=os.getenv('KLIKRIS_MERCHANT_ID',''); SANDBOX=b('KLIKRIS_SANDBOX'); DANA_NUMBER=os.getenv('DANA_NUMBER',''); DANA_NAME=os.getenv('DANA_NAME',''); MANUAL_QRIS_IMAGE=os.getenv('MANUAL_QRIS_IMAGE','./data/dana_qris.png'); POLL=int(os.getenv('STATUS_POLL_SECONDS','30')); HOST=os.getenv('HOST','0.0.0.0'); PORT=int(os.getenv('PORT','8080')); LOG=os.getenv('LOG_LEVEL','INFO')
def validate():
 if not BOT_TOKEN or not ADMIN_USER_ID: raise RuntimeError('BOT_TOKEN and ADMIN_USER_ID are required')
 if not PUBLIC_BASE_URL.startswith('https://'): raise RuntimeError('PUBLIC_BASE_URL must be HTTPS')
 if not API_KEY or not MERCHANT_ID: raise RuntimeError('KLIKRIS_API_KEY and KLIKRIS_MERCHANT_ID are required')
