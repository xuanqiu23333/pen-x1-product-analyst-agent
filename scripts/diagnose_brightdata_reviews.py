"""Diagnose Bright Data Amazon Reviews trigger failures without writing business data."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.brightdata_client import (  # noqa: E402
    BrightDataAPIError,
    BrightDataClient,
    BrightDataSettings,
)


CASE_A_INPUT = [{
    'url': 'https://www.amazon.com/Solar-Eclipse-Glasses-Certified-Viewing/dp/B08GB3QC1H',
    'reviews_to_not_include': [],
    'max_reviews': 10,
    'variation_specific': False,
}]

CASE_B_INPUT = [{
    'url': 'https://www.amazon.com/dp/B0CTCDPXFY/',
    'reviews_to_not_include': [],
    'max_reviews': 10,
    'variation_specific': True,
}]


def _emit_failure(case_name: str, error: BrightDataAPIError,
                  output: Callable[[str], None], snapshot_id: str = '') -> None:
    output(f'{case_name}=FAIL')
    output(f'HTTP={error.status_code if error.status_code is not None else ""}')
    output(f'snapshot_id={error.snapshot_id or snapshot_id}')
    output(f'error_code={error.error_code or ""}')
    output(f'error_message={error.error_message or error.message}')
    output(f'response_excerpt={error.response_excerpt}')


def _wait_for_snapshot(client: BrightDataClient, snapshot_id: str,
                       sleep: Callable[[float], None]) -> list[dict]:
    poll_interval = client.settings.poll_interval_seconds
    deadline = time.monotonic() + client.settings.max_poll_seconds
    while True:
        status_payload = client.get_snapshot_status(snapshot_id)
        status = str(status_payload.get('status') or '').lower()
        if status == 'ready':
            return client.download_snapshot(snapshot_id)
        if status in {'failed', 'canceled'}:
            raise BrightDataAPIError(
                None, f'Bright Data 快照状态为 {status}。', False,
                snapshot_id=snapshot_id, error_message=f'Bright Data 快照状态为 {status}。',
            )
        if status not in {'starting', 'running'}:
            raise BrightDataAPIError(
                None, 'Bright Data 快照状态无效。', False,
                snapshot_id=snapshot_id, error_message='Bright Data 快照状态无效。',
            )
        if time.monotonic() >= deadline:
            raise BrightDataAPIError(
                None, 'TIMEOUT：Bright Data 快照轮询超时。', True,
                snapshot_id=snapshot_id, error_code='TIMEOUT',
                error_message='TIMEOUT：Bright Data 快照轮询超时。',
            )
        sleep(poll_interval)


def run_diagnostics(client: BrightDataClient, output: Callable[[str], None] = print,
                    sleep: Callable[[float], None] = time.sleep) -> int:
    try:
        case_a_snapshot = client.trigger_collection(CASE_A_INPUT)
    except BrightDataAPIError as error:
        _emit_failure('CASE_A', error, output)
        return 1

    output('CASE_A=PASS')
    output('HTTP=200')
    output(f'snapshot_id={case_a_snapshot}')
    output('error_code=')
    output('error_message=')
    output('response_excerpt=')

    try:
        case_b_snapshot = client.trigger_collection(CASE_B_INPUT)
    except BrightDataAPIError as error:
        _emit_failure('CASE_B', error, output)
        return 1

    output('CASE_B=PASS')
    output('HTTP=200')
    output(f'snapshot_id={case_b_snapshot}')
    output('error_code=')
    output('error_message=')
    output('response_excerpt=')

    try:
        rows = _wait_for_snapshot(client, case_b_snapshot, sleep)
    except BrightDataAPIError as error:
        _emit_failure('CASE_B_RESULT', error, output, case_b_snapshot)
        return 1

    actual_fields = sorted({str(key) for row in rows for key in row})
    output(f'actual_records={len(rows)}')
    output(f'actual_fields={",".join(actual_fields)}')
    return 0


def main() -> int:
    load_dotenv(PROJECT_ROOT / '.env')
    settings = BrightDataSettings.from_environment()
    print(f'credential_configured={str(settings.configured).lower()}')
    if not settings.configured:
        return 2
    return run_diagnostics(BrightDataClient(settings))


if __name__ == '__main__':
    raise SystemExit(main())
