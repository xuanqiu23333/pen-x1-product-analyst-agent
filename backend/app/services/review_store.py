"""SQLite storage for validated real-review records from supported sources."""

import csv
import io
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.review_cleaning import (
    REAL_REVIEW_SOURCE_TYPES,
    normalize_apify_review,
    normalize_brightdata_review,
    normalize_review_record,
    review_coverage_level,
)


REQUIRED_COLUMNS = {'review_id', 'asin', 'product', 'rating', 'title', 'review_text',
                    'date', 'verified', 'helpful', 'source_url'}
MAX_CSV_BYTES = 5 * 1024 * 1024
REVIEW_COLUMNS = ('external_review_id', 'asin', 'product_name', 'marketplace', 'rating', 'title',
                  'review_text', 'review_date', 'verified_purchase', 'helpful_votes', 'source_type',
                  'source_url', 'review_url', 'product_url', 'collected_at', 'content_hash',
                  'raw_status', 'collection_run_id')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.executescript('''
            CREATE TABLE IF NOT EXISTS review_collection_run (
                run_id TEXT PRIMARY KEY, source TEXT NOT NULL, started_at TEXT NOT NULL,
                finished_at TEXT, target_products INTEGER NOT NULL DEFAULT 0,
                requested_reviews INTEGER NOT NULL DEFAULT 0,
                collected_reviews INTEGER NOT NULL DEFAULT 0, valid_reviews INTEGER NOT NULL DEFAULT 0,
                duplicate_reviews INTEGER NOT NULL DEFAULT 0, invalid_reviews INTEGER NOT NULL DEFAULT 0,
                failed_products INTEGER NOT NULL DEFAULT 0,
                product_summaries_json TEXT NOT NULL DEFAULT '[]', snapshot_id TEXT,
                provider TEXT, actor_run_id TEXT, dataset_id TEXT,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT, external_review_id TEXT, asin TEXT,
                product_name TEXT, marketplace TEXT, rating REAL, title TEXT, review_text TEXT,
                review_date TEXT, verified_purchase INTEGER, helpful_votes INTEGER,
                source_type TEXT NOT NULL, source_url TEXT, review_url TEXT, product_url TEXT,
                collected_at TEXT NOT NULL, content_hash TEXT, raw_status TEXT NOT NULL,
                collection_run_id TEXT NOT NULL REFERENCES review_collection_run(run_id)
            );
        ''')
        self._migrate(connection)
        connection.executescript('''
            CREATE UNIQUE INDEX IF NOT EXISTS review_valid_external_id
                ON review_raw(source_type, external_review_id)
                WHERE raw_status='VALID' AND external_review_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS review_valid_missing_id_hash
                ON review_raw(source_type, content_hash)
                WHERE raw_status='VALID' AND external_review_id IS NULL AND content_hash IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS review_valid_real_external_id
                ON review_raw(external_review_id)
                WHERE raw_status='VALID'
                  AND source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL')
                  AND external_review_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS review_valid_real_missing_id_hash
                ON review_raw(content_hash)
                WHERE raw_status='VALID'
                  AND source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL')
                  AND external_review_id IS NULL AND content_hash IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS review_valid_all_real_external_id
                ON review_raw(external_review_id)
                WHERE raw_status='VALID'
                  AND source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL','APIFY_REAL')
                  AND external_review_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS review_valid_all_real_missing_id_hash
                ON review_raw(content_hash)
                WHERE raw_status='VALID'
                  AND source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL','APIFY_REAL')
                  AND external_review_id IS NULL AND content_hash IS NOT NULL;
        ''')
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='review_valid_hash'").fetchone():
            connection.execute('DROP INDEX review_valid_hash')
        connection.commit()
        return connection

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        run_columns = {row['name'] for row in connection.execute('PRAGMA table_info(review_collection_run)')}
        for name, declaration in {
            'requested_reviews': 'INTEGER NOT NULL DEFAULT 0',
            'failed_products': 'INTEGER NOT NULL DEFAULT 0',
            'product_summaries_json': "TEXT NOT NULL DEFAULT '[]'",
            'snapshot_id': 'TEXT',
            'provider': 'TEXT',
            'actor_run_id': 'TEXT',
            'dataset_id': 'TEXT',
        }.items():
            if name not in run_columns:
                connection.execute(f'ALTER TABLE review_collection_run ADD COLUMN {name} {declaration}')
        review_columns = {row['name'] for row in connection.execute('PRAGMA table_info(review_raw)')}
        for name in ('review_url', 'product_url'):
            if name not in review_columns:
                connection.execute(f'ALTER TABLE review_raw ADD COLUMN {name} TEXT')
        connection.execute("""UPDATE review_raw SET review_url=source_url
                            WHERE review_url IS NULL AND source_type='IMPORTED_REAL'""")

    def import_csv(self, csv_text: str) -> dict:
        if len(csv_text.encode('utf-8')) > MAX_CSV_BYTES:
            raise ValueError('CSV 文件不能超过 5 MB。')
        reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')))
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            raise ValueError('CSV 表头缺少必需列。')
        return self.import_records(list(reader), 'IMPORTED_REAL', 'CSV_IMPORT')

    def import_records(self, rows: list[dict], source_type: str, source_name: str, *,
                       competitors: list[dict] | None = None, requested_reviews: int = 0,
                       target_products: int | None = None, failed_products: int = 0,
                       status: str | None = None, product_summaries: list[dict] | None = None,
                       snapshot_id: str | None = None, provider: str | None = None,
                       actor_run_id: str | None = None, dataset_id: str | None = None) -> dict:
        if source_type not in REAL_REVIEW_SOURCE_TYPES:
            raise ValueError('不支持的真实评论来源。')
        run_id, started = str(uuid4()), _now()
        counts = {'collected_reviews': 0, 'valid_reviews': 0, 'duplicate_reviews': 0,
                  'invalid_reviews': 0}
        product_counts: dict[str, dict[str, int]] = {}
        asins: set[str] = set()
        summaries = product_summaries or []
        with closing(self._connect()) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('''INSERT INTO review_collection_run(
                run_id,source,started_at,target_products,requested_reviews,failed_products,
                product_summaries_json,snapshot_id,provider,actor_run_id,dataset_id,status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (run_id, source_name, started, target_products or 0, requested_reviews,
                 failed_products, json.dumps(summaries, ensure_ascii=False), snapshot_id,
                 provider, actor_run_id, dataset_id, 'RUNNING'))
            for row in rows:
                if source_type == 'BRIGHTDATA_REAL':
                    competitor = self._competitor_for(row, competitors or [])
                    normalized, valid = normalize_brightdata_review(row, competitor)
                elif source_type == 'APIFY_REAL':
                    competitor = self._competitor_for(row, competitors or [])
                    normalized, valid = normalize_apify_review(row, competitor)
                else:
                    normalized, valid = normalize_review_record(row, source_type)
                counts['collected_reviews'] += 1
                if normalized['asin']:
                    asins.add(normalized['asin'])
                if not valid:
                    raw_status = 'INVALID'
                    counts['invalid_reviews'] += 1
                else:
                    lookup = ('external_review_id', normalized['external_review_id']) if normalized['external_review_id'] else ('content_hash', normalized['content_hash'])
                    previous = connection.execute(
                        f"SELECT id FROM review_raw WHERE raw_status='VALID' AND source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL','APIFY_REAL') AND {lookup[0]}=? LIMIT 1",
                        (lookup[1],),
                    ).fetchone()
                    raw_status = 'DUPLICATE' if previous else 'VALID'
                    counts['duplicate_reviews' if previous else 'valid_reviews'] += 1
                values = normalized | {'source_type': source_type,
                                       'collected_at': normalized.get('collected_at') or started,
                                       'raw_status': raw_status, 'collection_run_id': run_id}
                if normalized['product_name']:
                    product_count = product_counts.setdefault(
                        normalized['product_name'],
                        {'collected_reviews': 0, 'valid_reviews': 0,
                         'duplicate_reviews': 0, 'invalid_reviews': 0},
                    )
                    product_count['collected_reviews'] += 1
                    product_count[f'{raw_status.lower()}_reviews'] += 1
                placeholders = ','.join('?' for _ in REVIEW_COLUMNS)
                connection.execute(
                    f"INSERT INTO review_raw({','.join(REVIEW_COLUMNS)}) VALUES({placeholders})",
                    tuple(values[column] for column in REVIEW_COLUMNS),
                )
            finished = _now()
            actual_targets = target_products if target_products is not None else len(asins)
            final_status = status or ('PARTIAL' if counts['invalid_reviews'] or failed_products else 'COMPLETED')
            enriched_summaries = []
            for summary in summaries:
                name = f"{summary.get('brand', '')} {summary.get('model', '')}".strip()
                enriched_summaries.append(summary | product_counts.get(name, {}))
            result = {'run_id': run_id, 'source': source_name, 'started_at': started,
                      'finished_at': finished, 'target_products': actual_targets,
                      'requested_reviews': requested_reviews, **counts,
                      'failed_products': failed_products, 'products': enriched_summaries,
                      'snapshot_id': snapshot_id, 'provider': provider,
                      'actor_run_id': actor_run_id, 'dataset_id': dataset_id,
                      'status': final_status}
            connection.execute('''UPDATE review_collection_run SET finished_at=?, target_products=?,
                requested_reviews=?, collected_reviews=?, valid_reviews=?, duplicate_reviews=?,
                invalid_reviews=?, failed_products=?, product_summaries_json=?, snapshot_id=?,
                provider=?, actor_run_id=?, dataset_id=?, status=?
                WHERE run_id=?''',
                (finished, actual_targets, requested_reviews, counts['collected_reviews'],
                 counts['valid_reviews'], counts['duplicate_reviews'], counts['invalid_reviews'],
                 failed_products, json.dumps(enriched_summaries, ensure_ascii=False), snapshot_id,
                 provider, actor_run_id, dataset_id, final_status, run_id))
        return result

    @staticmethod
    def _competitor_for(row: dict, competitors: list[dict]) -> dict:
        if len(competitors) == 1:
            return competitors[0]
        raw_asin = str(row.get('asin') or '').upper()
        if raw_asin:
            match = next((item for item in competitors if str(item.get('asin') or '').upper() == raw_asin), None)
            if match:
                return match
        raw_url = row.get('product_url') or row.get('url')
        if raw_url:
            match = next((item for item in competitors if item.get('amazon_url') == raw_url), None)
            if match:
                return match
        return {}

    def valid_reviews(self) -> list[dict]:
        if not self.db_path.exists():
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute("""SELECT * FROM review_raw
                WHERE raw_status='VALID' AND source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL','APIFY_REAL')
                ORDER BY id""").fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item.update(review_id=row['external_review_id'] or f"h-{row['content_hash']}",
                        product=row['product_name'], date=row['review_date'],
                        source=('Bright Data API 获取的真实 Amazon 评论'
                                if row['source_type'] == 'BRIGHTDATA_REAL' else
                                'Apify API 获取的真实 Amazon 评论'
                                if row['source_type'] == 'APIFY_REAL' else
                                '导入的真实评论（未经 Amazon 平台核验）'))
            results.append(item)
        return results

    def latest_collection(self, source: str = 'BRIGHTDATA_API') -> dict | None:
        if not self.db_path.exists():
            return None
        with closing(self._connect()) as connection:
            row = connection.execute('''SELECT * FROM review_collection_run
                WHERE source=? ORDER BY started_at DESC LIMIT 1''', (source,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['products'] = json.loads(result.pop('product_summaries_json') or '[]')
        return result

    def stats(self) -> dict:
        counts = {'VALID': 0, 'DUPLICATE': 0, 'INVALID': 0}
        products: dict[str, int] = {}
        sources = {source: 0 for source in sorted(REAL_REVIEW_SOURCE_TYPES)}
        last_collected = None
        config = self.db_path.parent.parent / 'config' / 'amazon_competitors.json'
        configured_products = json.loads(config.read_text(encoding='utf-8')) if config.exists() else []
        asin_labels = {str(item.get('asin') or '').upper(): f"{item['brand']} {item['model']}"
                       for item in configured_products if item.get('asin')}
        if configured_products:
            for item in configured_products:
                products[f"{item['brand']} {item['model']}"] = 0
        if self.db_path.exists():
            with closing(self._connect()) as connection:
                for row in connection.execute("""SELECT raw_status, COUNT(*) AS amount FROM review_raw
                    WHERE source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL','APIFY_REAL') GROUP BY raw_status"""):
                    counts[row['raw_status']] = row['amount']
                for row in connection.execute("""SELECT asin, product_name, COUNT(*) AS amount FROM review_raw
                    WHERE raw_status='VALID' AND source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL','APIFY_REAL')
                    GROUP BY asin, product_name"""):
                    label = asin_labels.get(str(row['asin'] or '').upper(), row['product_name'])
                    products[label] = products.get(label, 0) + row['amount']
                for row in connection.execute("""SELECT source_type, COUNT(*) AS amount FROM review_raw
                    WHERE raw_status='VALID' AND source_type IN ('IMPORTED_REAL','BRIGHTDATA_REAL','APIFY_REAL')
                    GROUP BY source_type"""):
                    sources[row['source_type']] = row['amount']
                latest = connection.execute('SELECT MAX(finished_at) AS value FROM review_collection_run').fetchone()
                last_collected = latest['value']
        valid = counts['VALID']
        coverage = review_coverage_level(valid)
        return {'raw_reviews': sum(counts.values()), 'valid_reviews': valid,
                'duplicate_reviews': counts['DUPLICATE'], 'invalid_reviews': counts['INVALID'],
                'real_percent': 100 if valid else 0, 'sample_percent': 0,
                'last_collected': last_collected, 'coverage_level': coverage, 'products': products,
                'source_type': 'REAL_REVIEW', 'sources': sources}
