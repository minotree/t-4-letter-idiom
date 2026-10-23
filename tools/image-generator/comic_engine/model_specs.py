"""Locally reviewed Images API capabilities, checked against docs 2026-10-20.

This is a fail-closed project allowlist, not a claim to cover the entire API.
No endpoint lookup or client construction takes place during validation.
"""
import re

from .common import EngineError


MODERN = {
    'gpt-image-2.5-flare', 'gpt-image-2.5-flare-2026-09-08',
    'gpt-image-2.5-sunburst', 'gpt-image-2.5-sunburst-2026-09-08',
}
EARLIER = {'gpt-image-2', 'gpt-image-2-2026-04-21'}


def validate_image_settings(config):
    model, quality, size = (config.get(key) for key in ('image_model', 'image_quality', 'image_size'))
    if not isinstance(model, str) or model not in MODERN | EARLIER:
        raise EngineError('Image model is unknown or excluded by project policy (deprecated models are disabled)')
    qualities = {'low', 'medium', 'high', 'auto'}
    if model in MODERN:
        qualities |= {'xhigh', 'max'}
    if not isinstance(quality, str) or quality not in qualities:
        raise EngineError('Unsupported quality for selected image model')
    # auto is API-supported, but excluded here: deterministic dimensions are required.
    if not isinstance(size, str) or not re.fullmatch(r'[1-9][0-9]*x[1-9][0-9]*', size):
        raise EngineError('Image size must be an explicit WIDTHxHEIGHT')
    width, height = map(int, size.split('x'))
    if width % 16 or height % 16 or max(width, height) > 3840:
        raise EngineError('Image edges must be multiples of 16, at most 3840 pixels')
    if max(width, height) > 3 * min(width, height):
        raise EngineError('Image aspect ratio must be between 1:3 and 3:1')
    if not 655360 <= width * height <= 8294400:
        raise EngineError('Image pixel count must be between 655360 and 8294400')
    if min(width, height) < 512:
        raise EngineError('Project compositor requires both image edges to be at least 512 pixels')
    return width, height


def image_request(config, prompt):
    validate_image_settings(config)
    return {'model': config['image_model'], 'quality': config['image_quality'],
            'size': config['image_size'], 'n': 1, 'output_format': 'png', 'prompt': prompt}
