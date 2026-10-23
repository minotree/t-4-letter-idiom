import os
import random
import time
import hashlib
import json
import re

from .common import EngineError
from .costs import CostBlocked, clean_usage, money


class APIGateway:
    """One shared attempt budget for both APIs; SDK automatic retries disabled."""

    def __init__(self, config, max_calls, *, authorized=False, confirm_live=False, budget=None,
                 ledger=None, prices=None, client=None, sleep=time.sleep):
        if authorized is not True or config['allow_live'] is not True:
            raise EngineError('Live API disabled; use --dry-run or --mock')
        if type(max_calls) is not int or max_calls < 1:
            raise EngineError('Live execution requires a positive --max-api-calls')
        if confirm_live is not True:
            raise CostBlocked('Explicit --confirm-live is required')
        self.budget = money(budget, positive=True)
        if ledger is None or not ledger.locked or prices is None:
            raise CostBlocked('Locked usage ledger and verified prices are required')
        prices.validate_models(config)
        ledger.ensure_ready(self.budget)
        key = os.environ.get('OPENAI_API_KEY', '').strip()
        if not key:
            raise CostBlocked('OPENAI_API_KEY is not set')
        self.ledger, self.prices = ledger, prices
        self.config, self.max_calls, self.calls = config, max_calls, 0
        self.sleep = sleep
        if client is None:
            from openai import OpenAI
            # Do not inherit alternate endpoints or enable SDK debug logging.
            import logging
            for name in ('openai', 'httpx', 'httpcore'):
                logger = logging.getLogger(name)
                logger.handlers.clear()
                logger.addHandler(logging.NullHandler())
                logger.setLevel(logging.CRITICAL + 1)
                logger.propagate = False
                logger.disabled = True
            client = OpenAI(api_key=key, base_url='https://api.openai.com/v1',
                            max_retries=0, timeout=config['timeout_seconds'])
        self.client = client

    def call(self, operation, *, idiom_id=None, request_type=None, model=None, payload=None):
        from openai import APIConnectionError, APITimeoutError, APIStatusError, RateLimitError
        if (not isinstance(idiom_id, str) or not idiom_id.isdecimal()
                or request_type not in ('script', 'image') or not isinstance(payload, dict)
                or model != self.config['script_model' if request_type == 'script' else 'image_model']
                or payload.get('model') != model):
            raise CostBlocked('Complete matching request metadata is required for cost estimation')
        estimate = self.prices.estimate(model, request_type, self.config, payload)
        logical_id = hashlib.sha256(json.dumps({'idiom_id': idiom_id, 'type': request_type,
                                               'model': model, 'payload': payload}, sort_keys=True,
                                              ensure_ascii=False).encode()).hexdigest()
        _, previous = self.ledger.read()
        previous_attempts = [r for r in previous.values() if r['logical_id'] == logical_id]
        if any(r.get('outcome') == 'succeeded' or r['state'] == 'resolved' for r in previous_attempts):
            raise CostBlocked('Duplicate logical request blocked; restore its checkpoint instead')
        for attempt in range(len(previous_attempts), self.config['max_attempts']):
            if self.config['allow_live'] is not True or not os.environ.get('OPENAI_API_KEY', '').strip():
                raise CostBlocked('Live permission or environment API key is no longer available')
            if self.calls >= self.max_calls:
                raise CostBlocked('API attempt budget exhausted')
            # Reserve durably BEFORE sending; unknown costs from any prior request block here.
            self.prices.validate_models(self.config)
            reservation = self.ledger.reserve(logical_id=logical_id, idiom_id=idiom_id, model=model,
                                              kind=request_type, estimate=estimate, budget=self.budget,
                                              retry_count=attempt, price_date=self.prices.data['verified_on'])
            self.calls += 1
            try:
                response = operation(self.client)
            except BaseException as exc:
                status = getattr(exc, 'status_code', None)
                usage = clean_usage(getattr(exc, 'body', {}).get('usage') if isinstance(getattr(exc, 'body', None), dict) else None)
                try:
                    actual = self.prices.actual(model, request_type, usage)
                except CostBlocked:
                    actual = None
                self.ledger.finish(reservation, usage=usage, actual_cost=actual, outcome='failed',
                                   error=f'{type(exc).__name__}: HTTP {status}')
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                if actual is None:
                    raise CostBlocked('Request failed with uncertain cost; verify billing before retry') from None
                retryable = (isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError))
                             or status in (408, 409, 429) or (status is not None and status >= 500))
                if not retryable or attempt + 1 >= self.config['max_attempts']:
                    # Never stringify SDK exceptions, response bodies, or request objects.
                    raise EngineError(f'OpenAI request failed: {type(exc).__name__}, HTTP {status}') from None
                self.sleep(min(30, self.config['retry_base_seconds'] * (2 ** attempt)) + random.random())
                continue
            usage = clean_usage(getattr(response, 'usage', None))
            try:
                actual = self.prices.actual(model, request_type, usage)
            except CostBlocked:
                actual = None
            provider_id = getattr(response, '_request_id', None)
            if not isinstance(provider_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', provider_id):
                provider_id = None
            self.ledger.finish(reservation, usage=usage, actual_cost=actual, outcome='succeeded', provider_id=provider_id)
            # Return the response for checkpointing, even if its cost is unknown.
            # The next reservation is blocked globally until billing is verified.
            return response
        raise EngineError('API retry limit reached')
