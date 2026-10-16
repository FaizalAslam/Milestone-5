"""Report readiness without exposing secrets; --mcp performs only tool discovery."""
import argparse
import asyncio
import importlib.util
import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mcp', action='store_true', help='Initialize MCP and list tools; never invoke a write tool.')
args = parser.parse_args()
path = ROOT / '.streamlit' / 'secrets.toml'
config = tomllib.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
names = ['OPENAI_API_KEY', 'N8N_MCP_URL', 'N8N_MCP_TOKEN', 'GOOGLE_DOC_URL']
get = lambda name: config.get(name) or os.getenv(name, '')
result = {'python': sys.version.split()[0],
          'dependencies': {n: importlib.util.find_spec(n) is not None for n in ['streamlit', 'pandas', 'openai', 'mcp', 'pytest']},
          'configured': {name: bool(get(name)) for name in names}}
if args.mcp:
    from groww.approval import N8nMCP, validate_tool_schemas
    try:
        schemas = asyncio.run(N8nMCP(get('N8N_MCP_URL'), get('N8N_MCP_TOKEN')).inspect())
        validate_tool_schemas(schemas)
        result['mcp'] = {'status': 'pass', 'tool_names': sorted(schemas), 'write_tools_called': 0}
    except Exception as exc:
        result['mcp'] = {'status': 'not_ready', 'error_type': type(exc).__name__, 'write_tools_called': 0}
print(json.dumps(result, indent=2))
