"""Manual real-review collection orchestration for configured providers."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from app.data_providers.apify_review_provider import ApifyReviewProvider
from app.data_providers.brightdata_review_provider import BrightDataReviewProvider
from app.data_providers.review_collection_provider import ReviewCollectionProvider
from app.services.apify_client import ApifyAPIError, ApifyClient, ApifySettings
from app.services.brightdata_client import (
    BrightDataAPIError,
    BrightDataClient,
    BrightDataSettings,
)
from app.services.review_cleaning import normalize_brightdata_review
from app.services.review_store import ReviewStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewCollectionService:
    def __init__(self, data_root: Path,
                 settings: BrightDataSettings | ApifySettings | None = None,
                 provider: ReviewCollectionProvider | None = None,
                 store: ReviewStore | None = None, provider_name: str | None = None):
        self.data_root = Path(data_root)
        inferred = ('BRIGHTDATA' if isinstance(settings, BrightDataSettings) else
                    'APIFY' if isinstance(settings, ApifySettings) else
                    getattr(provider, 'provider_name', None))
        self.provider_name = (
            provider_name or inferred or os.getenv('REVIEW_COLLECTION_PROVIDER', 'APIFY')
        ).upper()
        if self.provider_name not in {'APIFY', 'BRIGHTDATA'}:
            raise ValueError('真实评论采集 Provider 仅支持 APIFY 或 BRIGHTDATA。')
        self.settings = settings or (
            ApifySettings.from_environment() if self.provider_name == 'APIFY'
            else BrightDataSettings.from_environment()
        )
        self.store = store or ReviewStore(self.data_root / 'reviews_real' / 'reviews.sqlite3')
        self.provider = provider
        if self.provider is None and self.settings.configured:
            self.provider = (
                ApifyReviewProvider(ApifyClient(self.settings))
                if self.provider_name == 'APIFY'
                else BrightDataReviewProvider(BrightDataClient(self.settings))
            )
        self.source_type = 'APIFY_REAL' if self.provider_name == 'APIFY' else 'BRIGHTDATA_REAL'
        self.source_name = 'APIFY_API' if self.provider_name == 'APIFY' else 'BRIGHTDATA_API'
        self.last_schema_probe: Path | None = None

    def _competitors(self) -> list[dict]:
        path = self.data_root / 'config' / 'amazon_competitors.json'
        return json.loads(path.read_text(encoding='utf-8'))

    @staticmethod
    def _product_summary(item: dict, target: int, status: str) -> dict:
        return {
            'brand': item.get('brand', ''), 'model': item.get('model', ''),
            'asin': item.get('asin', ''), 'amazon_url': item.get('amazon_url', ''),
            'status': status, 'target_reviews': target, 'requested_reviews': 0,
            'collected_reviews': 0, 'valid_reviews': 0,
            'duplicate_reviews': 0, 'invalid_reviews': 0,
        }

    def _empty_summary(self, competitors: list[dict], target: int, status: str) -> dict:
        products = []
        for item in competitors:
            product_status = ('PRODUCT_URL_REQUIRED' if not item.get('amazon_url')
                              else status)
            products.append(self._product_summary(item, target, product_status))
        return {
            'status': status, 'provider': self.provider_name,
            'credential_configured': self.settings.configured,
            'target_products': len(competitors), 'target_reviews': len(competitors) * target,
            'requested_reviews': 0, 'collected_reviews': 0, 'valid_reviews': 0,
            'duplicate_reviews': 0, 'invalid_reviews': 0, 'failed_products': 0,
            'products': products, 'started_at': None, 'finished_at': None,
            'snapshot_id': None, 'actor_run_id': None, 'dataset_id': None,
        }

    def collect_all_competitor_reviews(self,
                                       max_reviews_per_product: int | None = None) -> dict:
        target = (self.settings.review_target_per_product if max_reviews_per_product is None
                  else max_reviews_per_product)
        if not 1 <= target <= 300:
            raise ValueError('每个商品的评论目标必须在 1 到 300 之间。')
        competitors = self._competitors()
        if not self.settings.configured:
            status = 'APIFY_NOT_CONFIGURED' if self.provider_name == 'APIFY' else 'NOT_CONFIGURED'
            return self._empty_summary(competitors, target, status)
        ready = [item for item in competitors if item.get('amazon_url')]
        missing = [item for item in competitors if not item.get('amazon_url')]
        if not ready:
            return self._empty_summary(competitors, target, 'PRODUCT_URL_REQUIRED')
        if (self.provider_name == 'BRIGHTDATA'
                and not self.settings.schema_confirmed
                and (target > 5 or len(ready) > 1)):
            return self._empty_summary(competitors, target, 'SCHEMA_CONFIRMATION_REQUIRED')

        product_summaries = []
        for item in competitors:
            summary = self._product_summary(
                item, target, 'PRODUCT_URL_REQUIRED' if not item.get('amazon_url') else 'COMPLETED'
            )
            if item.get('amazon_url'):
                summary['requested_reviews'] = target
            product_summaries.append(summary)
        requested = len(ready) * target
        try:
            if self.provider is None:
                if self.provider_name == 'APIFY':
                    raise ApifyAPIError(None, 'Apify Provider 不可用。', False)
                raise BrightDataAPIError(None, 'Bright Data Provider 不可用。', False)
            collected = self.provider.collect_competitors(ready, target)
            snapshot_id = collected.get('snapshot_id')
            actor_run_id = collected.get('actor_run_id')
            dataset_id = collected.get('dataset_id')
            rows = collected.get('reviews') or []
        except (BrightDataAPIError, ApifyAPIError) as error:
            failed_products = len(ready)
            for item in product_summaries:
                if item['status'] != 'PRODUCT_URL_REQUIRED':
                    item['status'] = 'FAILED'
            result = self.store.import_records(
                [], self.source_type, self.source_name, competitors=ready,
                requested_reviews=requested, target_products=len(competitors),
                failed_products=failed_products, status='FAILED',
                product_summaries=product_summaries,
                snapshot_id=getattr(error, 'snapshot_id', None),
                provider=self.provider_name,
                actor_run_id=getattr(error, 'actor_run_id', None),
            )
            result.update(provider=self.provider_name, credential_configured=True,
                          target_reviews=len(competitors) * target, error=error.message)
            return result

        overall_status = 'PARTIAL' if missing else 'COMPLETED'
        result = self.store.import_records(
            rows, self.source_type, self.source_name, competitors=ready,
            requested_reviews=requested, target_products=len(competitors),
            failed_products=len(missing), status=overall_status,
            product_summaries=product_summaries, snapshot_id=snapshot_id,
            provider=self.provider_name, actor_run_id=actor_run_id, dataset_id=dataset_id,
        )
        result.update(provider=self.provider_name, credential_configured=True,
                      target_reviews=len(competitors) * target)
        if self.provider_name == 'APIFY' and rows:
            self.last_schema_probe = self._write_apify_schema_probe(rows)
            result['schema_probe'] = str(self.last_schema_probe)
        elif self.provider_name == 'BRIGHTDATA' and not self.settings.schema_confirmed:
            self.last_schema_probe = self._write_schema_probe(snapshot_id, rows, ready)
            result['schema_probe'] = str(self.last_schema_probe)
            result['schema_confirmation_required'] = True
        return result

    def _write_apify_schema_probe(self, rows: list[dict]) -> Path:
        private_keys = {
            'author', 'authorname', 'authorid', 'authorlink',
            'reviewer', 'reviewername', 'reviewerid', 'reviewerprofile',
            'username', 'profilepath', 'email', 'userid', 'user',
        }

        def sanitize(value):
            if isinstance(value, dict):
                return {
                    key: sanitize(item) for key, item in value.items()
                    if re.sub(r'[^a-z]', '', str(key).lower()) not in private_keys
                }
            if isinstance(value, list):
                return [sanitize(item) for item in value]
            if isinstance(value, str) and self.settings.api_token:
                return value.replace(self.settings.api_token, '[REDACTED]')
            return value

        path = self.data_root / 'fixtures' / 'apify_review_response.sample.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([sanitize(row) for row in rows[:5]], ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        return path

    def _write_schema_probe(self, snapshot_id: str | None, rows: list[dict],
                            competitors: list[dict]) -> Path:
        fields: dict[str, set[str]] = {}
        safe_previews = []
        for row in rows[:5]:
            for key, value in row.items():
                fields.setdefault(str(key), set()).add(type(value).__name__)
            competitor = self.store._competitor_for(row, competitors)
            normalized, _ = normalize_brightdata_review(row, competitor)
            safe_previews.append({
                key: normalized.get(key) for key in (
                    'external_review_id', 'asin', 'product_name', 'marketplace', 'rating',
                    'review_date', 'verified_purchase', 'helpful_votes', 'review_url',
                    'product_url', 'content_hash',
                )
            })
        safe_snapshot = re.sub(r'[^A-Za-z0-9_-]', '_', snapshot_id or 'unknown')
        path = self.data_root / 'reviews_real' / 'schema_probe' / f'{safe_snapshot}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'snapshot_id': snapshot_id, 'observed_at': _now(), 'record_count': len(rows),
            'fields': {key: sorted(values) for key, values in sorted(fields.items())},
            'safe_previews': safe_previews,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return path

    def latest_collection(self) -> dict:
        latest = self.store.latest_collection(self.source_name)
        competitors = self._competitors()
        target = self.settings.review_target_per_product
        if latest:
            persisted_target = sum(
                int(item.get('target_reviews') or 0) for item in latest.get('products', [])
            )
            latest.update(credential_configured=self.settings.configured,
                          provider=self.provider_name,
                          target_reviews=persisted_target or len(competitors) * target)
            return latest
        if not self.settings.configured:
            status = 'APIFY_NOT_CONFIGURED' if self.provider_name == 'APIFY' else 'NOT_CONFIGURED'
        elif not any(item.get('amazon_url') for item in competitors):
            status = 'PRODUCT_URL_REQUIRED'
        elif self.provider_name == 'BRIGHTDATA' and not self.settings.schema_confirmed:
            status = 'SCHEMA_CONFIRMATION_REQUIRED'
        else:
            status = 'PENDING'
        return self._empty_summary(competitors, target, status)
