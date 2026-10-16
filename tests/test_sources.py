import httpx
import pytest
from groww.sources import fetch_sources


def test_sources_use_official_content_and_checked_dates(monkeypatch):
    client_class = httpx.Client
    def handler(request):
        title = 'Account Opening' if request.url.path == '/pricing' else 'The brokerage charges'
        return httpx.Response(200, text=f'<html><nav>Ignore navigation</nav><main>{title} brokerage details. ' +
                              'Official fee context and applicable conditions. ' * 5 + '</main></html>')
    monkeypatch.setattr('groww.sources.httpx.Client', lambda **kw: client_class(transport=httpx.MockTransport(handler), **kw))
    sources = fetch_sources()
    assert len(sources) == 2
    assert all(s.checked_at and 'navigation' not in s.text for s in sources)


def test_nonofficial_redirect_blocked(monkeypatch):
    client_class = httpx.Client
    monkeypatch.setattr('groww.sources.httpx.Client', lambda **kw: client_class(
        transport=httpx.MockTransport(lambda _: httpx.Response(302, headers={'location': 'https://evil.example/fees'})), **kw))
    with pytest.raises(ValueError, match='outside groww.in'):
        fetch_sources()


def test_missing_or_blocked_fee_content_fails_closed(monkeypatch):
    client_class = httpx.Client
    monkeypatch.setattr('groww.sources.httpx.Client', lambda **kw: client_class(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text='<h1>Access blocked</h1>')), **kw))
    with pytest.raises(ValueError, match='Could not find fee content'):
        fetch_sources()
