import hashlib
import json
import os
from pathlib import Path
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'config.toml'
NOTICE = 'AI가 제작한 이미지입니다'
NUMBERS = '①②③④'


class EngineError(Exception):
    """Safe diagnostic: only application-controlled text may be exposed."""


def config_from(path=DEFAULT_CONFIG):
    path = Path(path)
    with path.open('rb') as stream:
        config = tomllib.load(stream)
    from .model_specs import validate_image_settings
    validate_image_settings(config)
    if not 1 <= config['max_attempts'] <= 5 or config['timeout_seconds'] <= 0:
        raise EngineError('Invalid retry/timeout configuration')
    if config['retry_base_seconds'] < 0 or not 80 <= config['minimum_quality'] <= 100:
        raise EngineError('Invalid retry delay or minimum WebP quality')
    if not 0 < config['target_min_bytes'] <= config['target_max_bytes']:
        raise EngineError('Invalid target byte range')
    for role in ('korean_font', 'hanja_font'):
        font = config[role]
        font_path = Path(font['path'])
        font['path'] = str(font_path if font_path.is_absolute() else path.parent / font_path)
        if not isinstance(font['index'], int) or font['index'] < 0:
            raise EngineError('Invalid font face index')
    return config


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def fingerprint(row, config, mock):
    value = {key: row[key] for key in ('id', 'hanja', 'reading', 'filename')}
    value.update(config=config, mock=mock, pipeline_version=2)
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
