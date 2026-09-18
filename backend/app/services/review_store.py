"""SQLite storage for imported (not platform-verified) real-review CSV rows."""

import csv
import io
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.review_cleaning import normalize_review


REQUIRED_COLUMNS = {'review_id', 'asin', 'product', 'rating', 'title', 'review_text',
                    'date', 'verified', 'helpful', 'source_url'}
MAX_CSV_BYTES = 5 * 1024 * 1024
REVIEW_COLUMNS = ('external_review_id', 'asin', 'product_name', 'marketplace', 'rating', 'title',
                  'review_text', 'review_date', 'verified_purchase', 'helpful_votes', 'source_type',
                  'source_url', 'collected_at', 'content_hash', 'raw_status', 'collection_run_id')


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
                collected_reviews INTEGER NOT NULL DEFAULT 0, valid_reviews INTEGER NOT NULL DEFAULT 0,
                duplicate_reviews INTEGER NOT NULL DEFAULT 0, invalid_reviews INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT, external_review_id TEXT, asin TEXT,
                product_name TEXT, marketplace TEXT, rating REAL, title TEXT, review_text TEXT,
                review_date TEXT, verified_purchase INTEGER, helpful_votes INTEGER,
                source_type TEXT NOT NULL, source_url TEXT, collected_at TEXT NOT NULL,
                content_hash TEXT, raw_status TEXT NOT NULL,
                collection_run_id TEXT NOT NULL REFERENCES review_collection_run(run_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS review_valid_external_id
                ON review_raw(source_type, external_review_id)
                WHERE raw_status='VALID' AND external_review_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS review_valid_missing_id_hash
                ON review_raw(source_type, content_hash)
                WHERE raw_status='VALID' AND external_review_id IS NULL AND content_hash IS NOT NULL;
        ''')
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='review_valid_hash'").fetchone():
            connection.execute('DROP INDEX review_valid_hash')
        return connection

    def import_csv(self, csv_text: str) -> dict:
        if len(csv_text.encode('utf-8')) > MAX_CSV_BYTES:
            raise ValueError('CSV 文件不能超过 5 MB。')
        reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')))
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            raise ValueError('CSV 表头缺少必需列。')
        run_id, started = str(uuid4()), _now()
        counts = {'collected_reviews': 0, 'valid_reviews': 0, 'duplicate_reviews': 0,
                  'invalid_reviews': 0}
        asins: set[str] = set()
        with closing(self._connect()) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('INSERT INTO review_collection_run(run_id,source,started_at,status) VALUES(?,?,?,?)',
                               (run_id, 'CSV_IMPORT', started, 'RUNNING'))
            for row in reader:
                normalized, valid = normalize_review(row)
                counts['collected_reviews'] += 1
                if normalized['asin']:
                    asins.add(normalized['asin'])
                if not valid:
                    status = 'INVALID'
                    counts['invalid_reviews'] += 1
                else:
                    lookup = ('external_review_id', normalized['external_review_id']) if normalized['external_review_id'] else ('content_hash', normalized['content_hash'])
                    previous = connection.execute(f"SELECT id FROM review_raw WHERE raw_status='VALID' AND source_type='IMPORTED_REAL' AND {lookup[0]}=? LIMIT 1",
                                                  (lookup[1],)).fetchone()
                    status = 'DUPLICATE' if previous else 'VALID'
                    counts['duplicate_reviews' if previous else 'valid_reviews'] += 1
                values = normalized | {'collected_at': started, 'raw_status': status,
                                       'collection_run_id': run_id}
                placeholders = ','.join('?' for _ in REVIEW_COLUMNS)
                connection.execute(f"INSERT INTO review_raw({','.join(REVIEW_COLUMNS)}) VALUES({placeholders})",
                                   tuple(values[column] for column in REVIEW_COLUMNS))
            finished = _now()
            result = {'run_id': run_id, 'source': 'CSV_IMPORT', 'started_at': started,
                      'finished_at': finished, 'target_products': len(asins), **counts,
                      'status': 'PARTIAL' if counts['invalid_reviews'] else 'COMPLETED'}
            connection.execute('''UPDATE review_collection_run SET finished_at=?, target_products=?,
                collected_reviews=?, valid_reviews=?, duplicate_reviews=?, invalid_reviews=?, status=?
                WHERE run_id=?''', (finished, len(asins), *counts.values(), result['status'], run_id))
        return result

    def valid_reviews(self) -> list[dict]:
        if not self.db_path.exists():
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM review_raw WHERE raw_status='VALID' AND source_type='IMPORTED_REAL' ORDER BY id").fetchall()
        return [dict(row) | {'review_id': row['external_review_id'] or f"h-{row['content_hash']}",
                             'product': row['product_name'], 'date': row['review_date'],
                             'source': '导入的真实评论（未经 Amazon 平台核验）'} for row in rows]

    def stats(self) -> dict:
        counts = {'VALID': 0, 'DUPLICATE': 0, 'INVALID': 0}
        products: dict[str, int] = {}
        last_collected = None
        config = self.db_path.parent.parent / 'config' / 'amazon_competitors.json'
        if config.exists():
            for item in json.loads(config.read_text(encoding='utf-8')):
                products[f"{item['brand']} {item['model']}"] = 0
        if self.db_path.exists():
            with closing(self._connect()) as connection:
                for row in connection.execute('SELECT raw_status, COUNT(*) AS amount FROM review_raw GROUP BY raw_status'):
                    counts[row['raw_status']] = row['amount']
                for row in connection.execute("SELECT product_name, COUNT(*) AS amount FROM review_raw WHERE raw_status='VALID' AND source_type='IMPORTED_REAL' GROUP BY product_name"):
                    products[row['product_name']] = row['amount']
                latest = connection.execute('SELECT MAX(finished_at) AS value FROM review_collection_run').fetchone()
                last_collected = latest['value']
        valid = counts['VALID']
        coverage = ('NEED_DATA' if valid == 0 else 'LOW_COVERAGE' if valid < 50 else
                    'PARTIAL' if valid < 200 else 'SUFFICIENT_FOR_DEMO')
        return {'raw_reviews': sum(counts.values()), 'valid_reviews': valid,
                'duplicate_reviews': counts['DUPLICATE'], 'invalid_reviews': counts['INVALID'],
                'real_percent': 100 if valid else 0, 'sample_percent': 0,
                'last_collected': last_collected, 'coverage_level': coverage, 'products': products,
                'source_type': 'IMPORTED_REAL'}
