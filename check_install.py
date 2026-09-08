import ast
from pathlib import Path
for p in Path('.').rglob('*.py'):
    if '.venv' not in p.parts: ast.parse(p.read_text(encoding='utf-8')); print('OK',p)
