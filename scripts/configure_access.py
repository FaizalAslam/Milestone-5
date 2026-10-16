"""Set a strong local app password only if no password is configured. Never print it."""
import os
from pathlib import Path
import re
import secrets
import tomllib


def ensure_access_password(path: Path, environment_password='') -> bool:
    source = path.read_text(encoding='utf-8') if path.exists() else ''
    config = tomllib.loads(source)
    if config.get('DEMO_ACCESS_PASSWORD') or environment_password:
        return False
    line = 'DEMO_ACCESS_PASSWORD = "' + secrets.token_urlsafe(32) + '"'
    if re.search(r'^DEMO_ACCESS_PASSWORD\s*=', source, flags=re.M):
        source = re.sub(r'^DEMO_ACCESS_PASSWORD\s*=.*$', line, source, flags=re.M)
    else:
        source += '\n' + line + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding='utf-8')
    return True


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    created = ensure_access_password(root / '.streamlit/secrets.toml', os.getenv('DEMO_ACCESS_PASSWORD', ''))
    print('Local demo access password generated in .streamlit/secrets.toml; value not printed.' if created
          else 'Existing demo access password preserved; value not printed.')
