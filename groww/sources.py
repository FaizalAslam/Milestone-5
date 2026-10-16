from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import httpx
import re
from bs4 import BeautifulSoup
from .models import Source

OFFICIAL_SOURCES = [
    ('pricing', 'Groww pricing', 'https://groww.in/pricing'),
    ('brokerage', 'How much is the brokerage?',
     'https://groww.in/help/stocks%2C-f%26o-%26-ipo/searchable/how-much-is-the-brokerage'),
]


def passage_catalog(sources: list[Source]) -> dict[str, dict]:
    """Small overlapping source spans with stable labels; never ask the model to retype them."""
    catalog = {}
    for source in sources:
        words = list(re.finditer(r'\S+', source.text))
        for index, offset in enumerate(range(0, len(words), 40), 1):
            end = min(offset + 55, len(words))
            catalog[f'{source.id}:P{index}'] = {'source_id': source.id,
                'text': source.text[words[offset].start():words[end - 1].end()]}
            if end == len(words):
                break
    return catalog


def fetch_sources() -> list[Source]:
    sources = []
    with httpx.Client(timeout=35, follow_redirects=False, headers={'User-Agent': 'GrowwReviewIntelligence/1.0'}) as client:
        for sid, title, url in OFFICIAL_SOURCES:
            response = client.get(url)
            for _ in range(4):
                if response.status_code not in (301, 302, 303, 307, 308):
                    break
                target = response.url.join(response.headers['location'])
                if target.scheme != 'https' or target.host != 'groww.in':
                    raise ValueError('Official source redirected outside groww.in.')
                response = client.get(target)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for node in soup(['script', 'style', 'nav', 'footer', 'header']):
                node.decompose()
            body = soup.get_text(' ', strip=True)
            # Drop repeated navigation and marketing copy outside the fee content.
            start = body.find('Account Opening') if sid == 'pricing' else body.find('The brokerage charges')
            if start < 0:
                raise ValueError(f'Could not find fee content in {title}; check the page manually.')
            body = body[start:]
            stop = body.find('Groww Invest Tech') if sid == 'pricing' else body.find('Was the answer helpful')
            if stop > 0:
                body = body[:stop]
            if not 100 < len(body) < 40000 or 'brokerage' not in body.lower():
                raise ValueError(f'Official fee source returned unexpected content: {title}.')
            sources.append(Source(id=sid, title=title, url=url,
                                  checked_at=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat(), text=body))
    return sources
