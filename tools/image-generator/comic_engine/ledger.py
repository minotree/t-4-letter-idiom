"""Locked, hash-chained JSONL event journal with a fail-closed head marker."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .common import ROOT, atomic_bytes, atomic_json
from .costs import CostBlocked, money
from .manifest import manifest_lock

DEFAULT_LEDGER = ROOT / 'data/api_usage_ledger.jsonl'
ZERO = '0' * 64


def digest(event):
    return hashlib.sha256(json.dumps(event, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class Ledger:
    def __init__(self, path=DEFAULT_LEDGER):
        self.path = Path(path).resolve()
        self.head = self.path.with_suffix('.state.json')
        self.locked = False

    @classmethod
    def initialize(cls, path):
        ledger = cls(path)
        with manifest_lock(ledger.path):
            if ledger.path.exists() or ledger.head.exists():
                raise CostBlocked('Ledger already exists; never initialize over prior usage')
            atomic_bytes(ledger.path, b'')
            atomic_json(ledger.head, {'seq': 0, 'hash': ZERO})
        return ledger

    @contextmanager
    def session(self):
        if self.locked:
            raise CostBlocked('Ledger session already active')
        with manifest_lock(self.path):
            self.locked = True
            try:
                self.read()
                yield self
            finally:
                self.locked = False

    def read(self):
        if not self.locked:
            raise CostBlocked('Ledger lock required')
        try:
            raw = self.path.read_bytes()
            if raw and not raw.endswith(b'\n'):
                raise ValueError()
            events, requests, previous = [], {}, ZERO
            for line in raw.decode('utf-8').splitlines():
                event = json.loads(line)
                signature = event.pop('hash')
                if (event['seq'] != len(events) + 1 or event['prev_hash'] != previous
                        or digest(event) != signature):
                    raise ValueError()
                event['hash'] = signature
                identifier = event['request_id']
                if not re.fullmatch(r'[0-9a-f]{64}-[0-9]+', identifier):
                    raise ValueError()
                money(event['estimated_cost_usd'], positive=True)
                if event['state'] == 'reserved':
                    if identifier in requests:
                        raise ValueError()
                    requests[identifier] = event.copy()
                elif event['state'] in ('succeeded', 'failed', 'cost_unknown'):
                    if identifier not in requests or requests[identifier]['state'] != 'reserved':
                        raise ValueError()
                    original = requests[identifier]
                    if any(original[key] != event[key] for key in ('logical_id', 'idiom_id', 'model', 'request_type', 'estimated_cost_usd', 'retry_count')):
                        raise ValueError()
                    if event['actual_cost_usd'] is not None:
                        money(event['actual_cost_usd'])
                    if event['state'] != 'cost_unknown' and event['actual_cost_usd'] is None:
                        raise ValueError()
                    requests[identifier] = event.copy()
                elif event['state'] == 'resolved':
                    if identifier not in requests or requests[identifier]['state'] not in ('reserved', 'cost_unknown'):
                        raise ValueError()
                    money(event['resolved_cost_usd'])
                    if event['resolution_source'] not in ('billing-dashboard', 'provider-support'):
                        raise ValueError()
                    requests[identifier] = event.copy()
                else:
                    raise ValueError()
                events.append(event)
                previous = signature
            head = json.loads(self.head.read_text(encoding='utf-8'))
            if head != {'seq': len(events), 'hash': previous}:
                raise ValueError()
            return events, requests
        except Exception as exc:
            if isinstance(exc, CostBlocked):
                raise
            raise CostBlocked('Ledger missing, corrupted, truncated or head mismatch; manual verification required') from None

    def append(self, data):
        events, _ = self.read()
        event = dict(data, seq=len(events) + 1, prev_hash=events[-1]['hash'] if events else ZERO,
                     event_time=datetime.now(timezone.utc).isoformat())
        event['hash'] = digest(event)
        raw = self.path.read_bytes() + (json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
        # If the process dies between these replacements, head mismatch blocks all
        # further calls; neither an unrecorded retry nor a zeroed budget is allowed.
        atomic_bytes(self.path, raw)
        atomic_json(self.head, {'seq': event['seq'], 'hash': event['hash']})
        return event

    def summary(self, budget=None):
        _, requests = self.read()
        reserved = sum((money(r['estimated_cost_usd']) for r in requests.values()), money(0))
        actual = sum((money(r['actual_cost_usd']) for r in requests.values() if r.get('actual_cost_usd') is not None), money(0))
        unknown = [r for r in requests.values() if r['state'] in ('reserved', 'cost_unknown')]
        unresolved = sum((money(r['estimated_cost_usd']) for r in unknown), money(0))
        consumed = sum((max(money(r['estimated_cost_usd']), money(r.get('resolved_cost_usd', r.get('actual_cost_usd') or 0)))
                        for r in requests.values()), money(0))
        return {
            'reserved_total_usd': str(reserved), 'usage_calculated_cost_usd': str(actual),
            'manually_verified_cost_usd': str(sum((money(r['resolved_cost_usd']) for r in requests.values()
                                                  if r['state'] == 'resolved'), money(0))),
            'uncertain_reserved_usd': str(unresolved), 'budget_consumed_usd': str(consumed),
            'remaining_estimated_budget_usd': str(money(budget) - consumed) if budget is not None else None,
            'uncertain_request_ids': [r['request_id'] for r in unknown],
            'success_count': sum(r.get('outcome') == 'succeeded' for r in requests.values()),
            'failure_count': sum(r.get('outcome') == 'failed' for r in requests.values()),
            'request_count': len(requests),
        }

    def ensure_ready(self, budget, estimate=None):
        summary = self.summary(budget)
        if summary['uncertain_request_ids']:
            raise CostBlocked('Uncertain request costs exist; verify billing before another API call')
        if money(summary['budget_consumed_usd']) + (estimate or money(0)) > money(budget, positive=True):
            raise CostBlocked('Cumulative estimated budget exceeded; API request blocked')

    def reserve(self, *, logical_id, idiom_id, model, kind, estimate, budget, retry_count, price_date):
        self.ensure_ready(budget, estimate)
        _, requests = self.read()
        prior = [r for r in requests.values() if r['logical_id'] == logical_id]
        if any(r.get('outcome') == 'succeeded' or r['state'] == 'resolved' for r in prior):
            raise CostBlocked('Duplicate logical request blocked; use its existing checkpoint')
        identifier = f'{logical_id}-{retry_count}'
        if identifier in requests or len(prior) != retry_count:
            raise CostBlocked('Duplicate or inconsistent request ID')
        return self.append({
            'request_id': identifier, 'logical_id': logical_id, 'idiom_id': idiom_id, 'model': model,
            'request_type': kind, 'request_time': datetime.now(timezone.utc).isoformat(),
            'state': 'reserved', 'outcome': None, 'estimated_cost_usd': str(estimate),
            'actual_tokens': None, 'actual_cost_usd': None, 'provider_request_id': None,
            'error': None, 'retry_count': retry_count, 'price_verified_on': price_date,
        })

    def finish(self, reservation, *, usage, actual_cost, outcome, error=None, provider_id=None):
        record = {key: val for key, val in reservation.items() if key not in ('seq', 'hash', 'prev_hash', 'event_time')}
        record.update(state=outcome if actual_cost is not None else 'cost_unknown', outcome=outcome,
                      actual_tokens=usage, actual_cost_usd=str(actual_cost) if actual_cost is not None else None,
                      error=error, provider_request_id=provider_id)
        return self.append(record)

    def resolve(self, identifier, amount, source):
        _, requests = self.read()
        record = requests.get(identifier)
        if record is None or record['state'] not in ('reserved', 'cost_unknown'):
            raise CostBlocked('Only uncertain requests can be manually resolved')
        if source not in ('billing-dashboard', 'provider-support'):
            raise CostBlocked('Billing verification source required')
        event = {key: val for key, val in record.items() if key not in ('seq', 'hash', 'prev_hash', 'event_time')}
        event.update(state='resolved', resolved_cost_usd=str(money(amount)), resolution_source=source)
        self.append(event)
