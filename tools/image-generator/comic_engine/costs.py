from datetime import datetime, date, timezone, timedelta
from decimal import Decimal, InvalidOperation
import json
import hashlib
from pathlib import Path
from urllib.parse import urlparse

from .common import EngineError
from .model_specs import validate_image_settings

DEFAULT_PRICES = Path(__file__).resolve().parents[1] / 'prices.json'


class CostBlocked(EngineError):
    pass


def money(value, positive=False):
    try:
        if isinstance(value, bool):
            raise ValueError()
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or (positive and result <= 0):
            raise ValueError()
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise CostBlocked('Invalid USD amount') from None


def token(value):
    if type(value) is not int or value < 0:
        raise CostBlocked('Usage token count is missing or invalid')
    return value


class Prices:
    def __init__(self, path=DEFAULT_PRICES, *, today=None):
        try:
            self.path, self.today = Path(path), today
            raw = self.path.read_bytes()
            self.file_hash = hashlib.sha256(raw).hexdigest()
            self.data = json.loads(raw.decode('utf-8'))
            checked = date.fromisoformat(self.data['verified_on'])
            now = today or datetime.now(timezone(timedelta(hours=9))).date()
            age_limit = self.data['max_age_days']
            if (self.data['schema_version'] != 1 or type(age_limit) is not int
                    or not 1 <= age_limit <= 30 or not 0 <= (now - checked).days <= age_limit):
                raise ValueError()
            self.models = self.data['models']
            if not isinstance(self.models, dict):
                raise ValueError()
        except Exception:
            raise CostBlocked('Price file invalid, future-dated or stale; review official prices') from None

    def entry(self, model, kind):
        try:
            now = self.today or datetime.now(timezone(timedelta(hours=9))).date()
            if (not 0 <= (now - date.fromisoformat(self.data['verified_on'])).days <= self.data['max_age_days']
                    or hashlib.sha256(self.path.read_bytes()).hexdigest() != self.file_hash):
                raise ValueError()
        except Exception:
            raise CostBlocked('Price file changed or expired during execution') from None
        entry = self.models.get(model)
        if not isinstance(entry, dict) or entry.get('type') != kind:
            raise CostBlocked('No matching verified model price')
        source = urlparse(entry.get('source', ''))
        if source.scheme != 'https' or source.hostname not in ('developers.openai.com', 'platform.openai.com'):
            raise CostBlocked('Price source must be an official HTTPS document')
        for field in ('input_per_million', 'output_per_million'):
            money(entry.get(field), positive=True)
        money(entry.get('cached_input_per_million' if kind == 'script' else 'image_input_per_million'), positive=True)
        return entry

    def estimate(self, model, kind, config, payload=None):
        entry = self.entry(model, kind)
        input_limit = token(entry.get('reservation_input_tokens'))
        if input_limit <= 0:
            raise CostBlocked('Input reservation is unavailable')
        if payload is not None:
            # UTF-8 bytes + fixed protocol allowance is a conservative local guard,
            # not the provider tokenizer or a billable token measurement.
            input_fields = {k: v for k, v in payload.items() if k not in ('model', 'max_output_tokens')}
            if len(json.dumps(input_fields, ensure_ascii=False).encode('utf-8')) + 512 > input_limit:
                raise CostBlocked('Request exceeds configured input reservation; review pricing profile')
        if kind == 'script':
            output = token(entry.get('reservation_output_tokens'))
            if payload is not None and payload.get('max_output_tokens') != output:
                raise CostBlocked('Script output limit differs from pricing reservation')
        elif kind == 'image':
            validate_image_settings(config)
            profile = entry.get('profiles', {}).get(config['image_size'] + '/' + config['image_quality'])
            if not isinstance(profile, dict) or profile.get('basis') != 'operator_estimate_not_api_output_limit':
                raise CostBlocked('Image size/quality estimate unavailable')
            output = token(profile.get('reservation_output_tokens'))
        else:
            raise CostBlocked('Unknown request type')
        if output <= 0:
            raise CostBlocked('Output estimate unavailable')
        return (money(entry['input_per_million']) * input_limit + money(entry['output_per_million']) * output) / 1000000

    def validate_models(self, config):
        return {kind: self.estimate(config[field], kind, config)
                for kind, field in (('script', 'script_model'), ('image', 'image_model'))}

    def actual(self, model, kind, usage):
        entry = self.entry(model, kind)
        if not isinstance(usage, dict):
            raise CostBlocked('Response usage unavailable')
        incoming, outgoing = token(usage.get('input_tokens')), token(usage.get('output_tokens'))
        details = usage.get('input_tokens_details') or {}
        if not isinstance(details, dict):
            raise CostBlocked('Usage details invalid')
        if kind == 'script':
            cached = token(details.get('cached_tokens', 0))
            if cached > incoming:
                raise CostBlocked('Usage details inconsistent')
            input_cost = ((incoming - cached) * money(entry['input_per_million'])
                          + cached * money(entry.get('cached_input_per_million')))
        else:
            text_count, image_count = token(details.get('text_tokens')), token(details.get('image_tokens'))
            if text_count + image_count != incoming:
                raise CostBlocked('Image input usage breakdown unavailable')
            input_cost = text_count * money(entry['input_per_million']) + image_count * money(entry.get('image_input_per_million'))
        return (input_cost + outgoing * money(entry['output_per_million'])) / 1000000


def clean_usage(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None
    result = {}
    for key in ('input_tokens', 'output_tokens', 'total_tokens'):
        if type(value.get(key)) is int and value[key] >= 0:
            result[key] = value[key]
    details = value.get('input_tokens_details')
    if isinstance(details, dict):
        result['input_tokens_details'] = {key: val for key, val in details.items()
                                          if key in ('cached_tokens', 'text_tokens', 'image_tokens')
                                          and type(val) is int and val >= 0}
    return result or None
