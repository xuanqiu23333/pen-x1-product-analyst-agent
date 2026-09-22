"""Whitelist, normalize and validate real-review records before persistence."""

import hashlib
import html
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup


REAL_REVIEW_SOURCE_TYPES = frozenset({'IMPORTED_REAL', 'BRIGHTDATA_REAL', 'APIFY_REAL'})


def review_coverage_level(count: int) -> str:
    """Return the project's demo-only real-review coverage hint."""
    return ('NEED_DATA' if count <= 0 else 'LOW_COVERAGE' if count < 20 else
            'PARTIAL' if count < 50 else 'GOOD_COVERAGE')


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
    if raw.lower().startswith('reviewed ') and ' on ' in raw:
        raw = raw.rsplit(' on ', 1)[-1]
    for pattern in (
        '%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d', '%b %d, %Y',
        '%B %d, %Y', '%d %B %Y',
    ):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def clean_datetime(value: object) -> str | None:
    raw = clean_text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00')).isoformat()
    except ValueError:
        return None


def _first(row: dict, *keys: str):
    for key in keys:
        value = row.get(key)
        if value is not None and value != '':
            return value
    return None


def _safe_url(value: object) -> str | None:
    url = clean_text(value) or None
    if url and urlparse(url).scheme not in {'http', 'https'}:
        return None
    return url


def normalize_review_record(row: dict, source_type: str) -> tuple[dict, bool]:
    """Normalize a canonical/CSV-like row into the ReviewStore whitelist."""
    if source_type not in REAL_REVIEW_SOURCE_TYPES:
        raise ValueError('不支持的真实评论来源。')
    review_id = clean_text(_first(row, 'external_review_id', 'review_id')) or None
    asin = clean_text(_first(row, 'asin')).upper()
    product = clean_text(_first(row, 'product_name', 'product'))
    title = clean_text(_first(row, 'title', 'review_title'))
    body = clean_text(_first(row, 'review_text', 'content'))
    review_date = clean_date(_first(row, 'review_date', 'date'))
    review_url = _safe_url(_first(row, 'review_url', 'source_url'))
    product_url = _safe_url(row.get('product_url'))
    collected_at = clean_datetime(row.get('collected_at'))
    marketplace = clean_text(row.get('marketplace')) or 'US'
    try:
        rating_text = clean_text(_first(row, 'rating', 'review_rating'))
        match = re.match(r'^\s*(\d+(?:\.\d+)?)', rating_text)
        rating = float(match.group(1)) if match else None
        if not 1 <= rating <= 5:
            rating = None
    except (TypeError, ValueError):
        rating = None
    verified_raw = clean_text(_first(row, 'verified_purchase', 'verified')).lower()
    verified = (1 if verified_raw in {'yes', 'true', '1', 'y'} else
                0 if verified_raw in {'no', 'false', '0', 'n', ''} else None)
    try:
        helpful = int(clean_text(_first(row, 'helpful_votes', 'helpful')) or '0')
        if helpful < 0:
            helpful = None
    except (TypeError, ValueError):
        helpful = None
    valid = bool(re.fullmatch(r'[A-Z0-9]{10}', asin) and product and body and review_date
                 and rating is not None and verified is not None and helpful is not None)
    content_hash = (hashlib.sha256(f'{asin}\n{body}\n{rating:g}\n{review_date}'.encode('utf-8')).hexdigest()
                    if valid else None)
    return ({'external_review_id': review_id, 'asin': asin or None, 'product_name': product or None,
             'marketplace': marketplace, 'rating': rating, 'title': title or None,
             'review_text': body or None, 'review_date': review_date,
             'verified_purchase': verified, 'helpful_votes': helpful,
             'source_type': source_type, 'source_url': review_url, 'review_url': review_url,
             'product_url': product_url, 'collected_at': collected_at,
             'content_hash': content_hash}, valid)


def normalize_review(row: dict) -> tuple[dict, bool]:
    """Backward-compatible CSV normalization entry point."""
    return normalize_review_record(row, 'IMPORTED_REAL')


def normalize_brightdata_review(raw: dict, competitor: dict) -> tuple[dict, bool]:
    """Map Bright Data aliases without retaining unrelated personal fields."""
    canonical = {
        'review_id': _first(raw, 'review_id', 'id'),
        'asin': _first(raw, 'asin') or competitor.get('asin'),
        'product': _first(raw, 'product_name', 'product') or
                   f"{competitor.get('brand', '')} {competitor.get('model', '')}".strip(),
        'rating': _first(raw, 'rating', 'review_rating'),
        'title': _first(raw, 'review_header', 'review_title', 'title'),
        'review_text': _first(raw, 'review_text', 'content'),
        'date': _first(raw, 'review_posted_date', 'review_date', 'date'),
        'verified': _first(raw, 'is_verified', 'verified_purchase', 'verified'),
        'helpful': _first(raw, 'helpful_count', 'helpful_votes'),
        'review_url': _first(raw, 'review_url'),
        'product_url': _first(raw, 'product_url', 'url') or competitor.get('amazon_url'),
        'collected_at': _first(raw, 'timestamp'),
        'marketplace': competitor.get('marketplace') or 'US',
    }
    return normalize_review_record(canonical, 'BRIGHTDATA_REAL')


def normalize_apify_review(raw: dict, competitor: dict) -> tuple[dict, bool]:
    """Map supported Apify Actor outputs while dropping reviewer identity fields."""
    domain = clean_text(_first(raw, 'domainCode', 'domain')).lower()
    marketplace = {'com': 'US', 'ca': 'CA'}.get(
        domain, competitor.get('marketplace') or domain.upper() or 'US'
    )
    canonical = {
        'review_id': _first(raw, 'reviewId', 'review_id'),
        'asin': _first(raw, 'asin') or competitor.get('asin'),
        'product': _first(raw, 'productTitle', 'product_title') or
                   f"{competitor.get('brand', '')} {competitor.get('model', '')}".strip(),
        'rating': _first(raw, 'rating'),
        'title': _first(raw, 'title'),
        'review_text': _first(raw, 'text'),
        'date': _first(raw, 'date', 'date_text'),
        'verified': _first(raw, 'verified'),
        'helpful': _first(raw, 'numberOfHelpful', 'helpful_votes'),
        'review_url': _first(raw, 'reviewUrl', 'url'),
        'product_url': _first(raw, 'productUrl') or competitor.get('amazon_url'),
        'collected_at': _first(raw, 'timestamp', 'scrapedAt', 'fetched_at'),
        'marketplace': marketplace,
    }
    return normalize_review_record(canonical, 'APIFY_REAL')
