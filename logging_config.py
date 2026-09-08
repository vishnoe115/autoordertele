import logging, os
from logging.handlers import RotatingFileHandler
from config import settings

def setup_logging():
    os.makedirs(os.path.dirname(settings.log_file) or '.', exist_ok=True)
    root=logging.getLogger(); root.handlers.clear(); root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    fmt=logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
    sh=logging.StreamHandler(); sh.setFormatter(fmt); root.addHandler(sh)
    fh=RotatingFileHandler(settings.log_file,maxBytes=5_000_000,backupCount=5,encoding='utf-8'); fh.setFormatter(fmt); root.addHandler(fh)
