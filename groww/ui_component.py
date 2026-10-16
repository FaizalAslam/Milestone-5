"""Trusted, local Streamlit component assets. Runtime review text is passed only as data."""
import base64
from functools import lru_cache
import hashlib
from pathlib import Path
from streamlit.components.v2 import component

ASSETS = Path(__file__).with_name('ui')
@lru_cache(maxsize=4)
def _register(css, js, font):
    version = hashlib.sha256((css + js).encode() + font).hexdigest()[:12]
    encoded = base64.b64encode(font).decode('ascii')
    return component('groww_review_workspace_' + version, html='<div id="groww-workspace"></div>',
                     css=css.replace('__INTER_FONT__', 'data:font/woff2;base64,' + encoded), js=js)


def workspace_component(**kwargs):
    renderer = _register((ASSETS / 'workspace.css').read_text(encoding='utf-8'),
                         (ASSETS / 'workspace.js').read_text(encoding='utf-8'),
                         (ASSETS / 'inter.woff2').read_bytes())
    return renderer(**kwargs)
