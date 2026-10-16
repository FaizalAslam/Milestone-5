from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

from groww.ui_component import workspace_component
from groww.workspace import Workspace, recover_workspace, register_workspace

ROOT = Path(__file__).parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Groww · Review Intelligence', page_icon='📊', layout='wide', initial_sidebar_state='collapsed')
st.html("""<style>
[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stToolbar"], #MainMenu, footer {display:none!important;}
[data-testid="stAppViewContainer"], [data-testid="stApp"] {background:#f9f9ff;}
.stMainBlockContainer, [data-testid="stMainBlockContainer"] {max-width:none!important;padding:0!important;}
[data-testid="stVerticalBlock"] {gap:0!important;}
[data-testid="stMain"] {padding:0!important;}
</style>""")


def settings():
    names = {'OPENAI_API_KEY':'', 'OPENAI_MODEL':'gpt-5-mini', 'OPENAI_MAX_WORKERS':'4',
             'N8N_MCP_URL':'', 'N8N_MCP_TOKEN':'', 'GOOGLE_DOC_URL':''}
    result = {}
    for name, default in names.items():
        try:
            result[name] = str(st.secrets.get(name) or os.getenv(name, default))
        except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
            result[name] = os.getenv(name, default)
    return result


if '_workspace' not in st.session_state:
    st.session_state['_workspace'] = register_workspace(Workspace(ROOT, settings()))
    if st.query_params.get('example') == '1':
        st.session_state['_workspace'].load_example()
else:
    st.session_state['_workspace'].update_settings(settings())


polling = st.session_state['_workspace'].busy


@st.fragment(run_every='1s' if polling else None)
def render_workspace():
    controller = st.session_state['_workspace']
    if polling and not controller.busy:
        st.rerun()
    view = controller.view()
    st.session_state['workspace_view'] = view
    result = workspace_component(key='groww_workspace_ui', data=view, on_action_change=lambda: None)
    event = getattr(result, 'action', None)
    if event:
        if event.get('type') == 'restore':
            previous = recover_workspace((event.get('payload') or {}).get('workspace_id'))
            if previous:
                previous.update_settings(settings())
                st.session_state['_workspace'] = previous
            else:
                controller.notice = 'Your previous browser session expired. Upload the same CSV to resume a verified saved result.'
        else:
            controller.handle(event)
        st.rerun()


render_workspace()
