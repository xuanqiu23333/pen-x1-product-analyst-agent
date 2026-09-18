"""Manual sync, sanitized snapshots, and Fact/Evidence conversion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.data_providers.amazon_sp_api_provider import AmazonSPAPIProvider
from app.schemas.amazon import AmazonProductSync, AmazonSyncSummary
from app.schemas.models import Evidence, Fact
from app.services.amazon_auth import AmazonAuth, AmazonAuthError, AmazonSettings
from app.services.amazon_sp_api_client import AmazonAPIError, AmazonSPAPIClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AmazonSyncService:
    def __init__(self, data_root: Path, settings: AmazonSettings | None = None,
                 provider: AmazonSPAPIProvider | None = None):
        self.data_root = Path(data_root)
        self.settings = settings or AmazonSettings.from_environment()
        self._provider = provider

    def _targets(self) -> list[dict]:
        path = self.data_root / 'config' / 'amazon_competitors.json'
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, list):
            raise ValueError('Amazon 竞品配置必须是列表。')
        return data

    def latest_snapshot(self) -> dict | None:
        path = self.data_root / 'amazon' / 'latest' / 'snapshot.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def _save(self, snapshot: dict) -> None:
        root = self.data_root / 'amazon'
        latest = root / 'latest'
        history = root / 'history' / snapshot['summary']['started_at'][:10]
        latest.mkdir(parents=True, exist_ok=True)
        history.mkdir(parents=True, exist_ok=True)
        content = json.dumps(snapshot, ensure_ascii=False, indent=2)
        history_path = history / f"{snapshot['summary']['run_id']}.json"
        history_path.write_text(content, encoding='utf-8')
        temp_path = latest / f".{snapshot['summary']['run_id']}.json"
        temp_path.write_text(content, encoding='utf-8')
        temp_path.replace(latest / 'snapshot.json')

    @staticmethod
    def _normalize(product: AmazonProductSync) -> tuple[list[Fact], list[Evidence]]:
        facts: list[Fact] = []
        evidence: list[Evidence] = []
        catalog = product.catalog
        pricing = product.pricing
        for field, value, name in (
            ('title', catalog.title if catalog else None, '商品标题'),
            ('brand', catalog.brand if catalog else None, '品牌'),
            ('model', catalog.model if catalog else None, '型号'),
            ('sales_rank', catalog.sales_rank if catalog else None, '销售排名'),
            ('listing_price', pricing.listing_price if pricing else None, '新商品报价'),
        ):
            if value is None:
                continue
            source = pricing if field == 'listing_price' else catalog
            nature = 'PUBLIC_DATA' if source.status == 'LIVE' else 'PUBLIC_FIXTURE'
            facts.append(Fact(
                id=f'amazon-{product.asin}-{field}', category='competitor', name=f'{product.asin} {name}',
                value=value, unit=pricing.currency if field == 'listing_price' else None,
                source_type='AMAZON_SP_API', source_name='Amazon SP-API',
                source_url=source.source_url, retrieved_at=source.retrieved_at,
                status='CONFIRMED' if source.status == 'LIVE' else 'NEED_VERIFY',
                confidence='HIGH' if source.status == 'LIVE' else 'LOW', data_nature=nature,
            ))
        for index, item in enumerate(product.feedback, 1):
            evidence.append(Evidence(
                id=f'ev-amazon-feedback-{product.asin}-{item.sentiment}-{index}',
                source='Amazon Customer Feedback API', source_name='Amazon Customer Feedback API',
                source_type='AMAZON_CUSTOMER_FEEDBACK', source_url=item.source_url,
                retrieved_at=item.retrieved_at,
                content=f'{item.sentiment} topic: {item.topic}; mentions: {item.mentions if item.mentions is not None else "UNKNOWN"}; star rating impact: {item.star_rating_impact if item.star_rating_impact is not None else "UNKNOWN"}',
                data_nature='PUBLIC_DATA' if item.status == 'LIVE' else 'PUBLIC_FIXTURE',
                status='CONFIRMED' if item.status == 'LIVE' else 'NEED_VERIFY',
                confidence='HIGH' if item.status == 'LIVE' else 'LOW',
            ))
        return facts, evidence

    def sync_all_competitors(self) -> AmazonSyncSummary:
        started = _now()
        targets = self._targets()
        summary = AmazonSyncSummary(
            run_id=str(uuid4()), started_at=started, finished_at=started,
            status='PENDING', mode=self.settings.mode,
            credential_configured=self.settings.configured, target_products=len(targets),
        )
        products: list[AmazonProductSync] = []
        facts: list[Fact] = []
        evidence: list[Evidence] = []
        disabled = self.settings.mode == 'production' and not self.settings.real_data_enabled
        client = None
        provider = self._provider
        for target in targets:
            asin = (target.get('asin') or '').strip().upper()
            product = AmazonProductSync(asin=asin, brand=target.get('brand'), model=target.get('model'))
            if not asin:
                product.status = 'ASIN_REQUIRED'
            elif not self.settings.configured:
                product.status = 'NOT_CONFIGURED'
            elif disabled:
                product.status = 'DISABLED'
            else:
                if provider is None:
                    auth = AmazonAuth(self.settings.client_id, self.settings.client_secret,
                                      self.settings.refresh_token, token_url=self.settings.lwa_token_url,
                                      timeout=self.settings.timeout,
                                      refresh_buffer_seconds=self.settings.token_refresh_buffer_seconds)
                    client = AmazonSPAPIClient(auth, endpoint=self.settings.api_endpoint,
                                               timeout=self.settings.timeout,
                                               max_retries=self.settings.max_retries)
                    provider = AmazonSPAPIProvider(client, self.settings.marketplace_id,
                                                   self.settings.mode)
                operations = (
                    ('catalog', provider.get_catalog_item),
                    ('pricing', provider.get_pricing),
                    ('feedback', provider.get_customer_feedback),
                    ('trends', provider.get_customer_feedback_trends),
                )
                trends = {}
                for name, operation in operations:
                    try:
                        value = operation(asin)
                        if name == 'trends':
                            trends = value
                        else:
                            setattr(product, name, value)
                    except AmazonAPIError as error:
                        product.errors.append({'operation': error.operation, 'status_code': error.status_code,
                                               'message': error.message, 'request_id': error.request_id,
                                               'retryable': error.retryable})
                    except AmazonAuthError:
                        product.errors.append({'operation': name, 'message': 'Amazon 认证不可用。'})
                    except (ValueError, TypeError, KeyError):
                        product.errors.append({'operation': name, 'message': 'Amazon 响应格式不可用。'})
                for item in product.feedback:
                    item.trend = trends.get((item.topic, item.sentiment), [])
                catalog_ok = product.catalog is not None and product.catalog.status in ('LIVE', 'SANDBOX')
                pricing_ok = product.pricing is not None and product.pricing.status in ('LIVE', 'SANDBOX')
                has_data = catalog_ok or pricing_ok or bool(product.feedback)
                product.status = ('ERROR' if not has_data else
                                  'PARTIAL' if product.errors or not (catalog_ok and pricing_ok) else
                                  'SANDBOX' if self.settings.mode == 'sandbox' else 'LIVE')
            if product.status in ('LIVE', 'SANDBOX'):
                summary.successful_products += 1
            else:
                summary.failed_products += 1
                summary.fallback_records += 1
            summary.catalog_records += int(product.catalog is not None and product.catalog.status in ('LIVE', 'SANDBOX'))
            summary.pricing_records += int(product.pricing is not None and product.pricing.status in ('LIVE', 'SANDBOX'))
            summary.feedback_topics += len(product.feedback)
            summary.live_records += sum([product.catalog is not None and product.catalog.status == 'LIVE',
                                         product.pricing is not None and product.pricing.status == 'LIVE'])
            summary.live_records += sum(item.status == 'LIVE' for item in product.feedback)
            item_facts, item_evidence = self._normalize(product)
            facts.extend(item_facts)
            evidence.extend(item_evidence)
            products.append(product)
            summary.products.append({'brand': product.brand, 'model': product.model,
                                     'asin': product.asin, 'status': product.status,
                                     'errors': product.errors})
        client = client or getattr(provider, 'client', None)
        if client:
            for field in ('api_requests', 'api_errors', 'rate_limit_events'):
                setattr(summary, field, getattr(client, field, 0))
            summary.rate_limits = getattr(client, 'rate_limits', {})
            summary.request_ids = getattr(client, 'request_ids', [])
        summary.status = ('NOT_CONFIGURED' if not self.settings.configured else
                          'DISABLED' if disabled else
                          'ASIN_REQUIRED' if not any(item.asin for item in products) else
                          'COMPLETED' if summary.successful_products == summary.target_products else
                          'PARTIAL' if summary.successful_products else 'ERROR')
        summary.finished_at = _now()
        self._save({'summary': summary.model_dump(), 'products': [item.model_dump() for item in products],
                    'facts': [item.model_dump() for item in facts],
                    'evidence': [item.model_dump() for item in evidence]})
        return summary
