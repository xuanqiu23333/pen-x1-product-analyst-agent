"""Whitelist and normalize imported review fields before persistence."""

import hashlib
import html
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def clean_text(value: object) -> str:
    text = unicodedata.normalize('NFKC', str(value or ''))
    if '<' in text and '>' in text:
        soup = BeautifulSoup(text, 'html.parser')
        for element in soup(['script', 'style']):
            element.decompose()
        text = soup.get_text(' ', strip=True)
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def clean_date(value: object) -> str | None:
    raw = clean_text(value)
    if not raw:
        return None
    for pattern in ('%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d', '%b %d, %Y'):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_review(row: dict) -> tuple[dict, bool]:
    review_id = clean_text(row.get('review_id')) or None
    asin = clean_text(row.get('asin')).upper()
    product = clean_text(row.get('product'))
    title = clean_text(row.get('title'))
    body = clean_text(row.get('review_text'))
    review_date = clean_date(row.get('date'))
    source_url = clean_text(row.get('source_url')) or None
    if source_url and urlparse(source_url).scheme not in {'http', 'https'}:
        source_url = None
    try:
        rating = float(clean_text(row.get('rating')))
        if not 1 <= rating <= 5:
            rating = None
    except ValueError:
        rating = None
    verified_raw = clean_text(row.get('verified')).lower()
    verified = 1 if verified_raw in {'yes', 'true', '1', 'y'} else 0 if verified_raw in {'no', 'false', '0', 'n', ''} else None
    try:
        helpful = int(clean_text(row.get('helpful')) or '0')
        if helpful < 0:
            helpful = None
    except ValueError:
        helpful = None
    valid = bool(re.fullmatch(r'[A-Z0-9]{10}', asin) and product and body and review_date
                 and rating is not None and verified is not None and helpful is not None)
    content_hash = (hashlib.sha256(f'{asin}\n{body}\n{rating:g}\n{review_date}'.encode('utf-8')).hexdigest()
                    if valid else None)
    return ({'external_review_id': review_id, 'asin': asin or None, 'product_name': product or None,
             'marketplace': 'US', 'rating': rating, 'title': title or None, 'review_text': body or None,
             'review_date': review_date, 'verified_purchase': verified, 'helpful_votes': helpful,
             'source_type': 'IMPORTED_REAL', 'source_url': source_url, 'content_hash': content_hash}, valid)
