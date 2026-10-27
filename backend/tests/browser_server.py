"""Disposable browser-QA server. Never load/save real accounts or call AI.

Run from backend: .venv/Scripts/python.exe tests/browser_server.py
The real routes, auth/session logic, parsers and evaluators are used.
"""
import builtins
import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['ALLOWED_ORIGINS'] = 'http://127.0.0.1:5175'
os.environ.pop('OPENROUTER_API_KEY', None)
real_open = builtins.open
account_file = ROOT / 'data' / 'users.json'


def isolated_open(file, mode='r', *args, **kwargs):
    if isinstance(file, (str, Path)) and Path(file).resolve() == account_file:
        if mode != 'r':
            raise AssertionError('Real account writes forbidden')
        return StringIO('{}')
    return real_open(file, mode, *args, **kwargs)


if __name__ == '__main__':
    import uvicorn
    with patch('builtins.open', side_effect=isolated_open):
        import main
        with patch('auth.auth._save_users'), \
             patch('ai.matcher.get_client', side_effect=RuntimeError('QA provider disabled')), \
             patch('ai.improvements.get_client', side_effect=RuntimeError('QA provider disabled')):
            uvicorn.run(main.app, host='127.0.0.1', port=8003, access_log=False)
