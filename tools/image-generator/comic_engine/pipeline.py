import io
import json
from pathlib import Path

from PIL import Image

from .artwork import ArtworkGenerator, MockArtworkGenerator
from .common import EngineError, atomic_bytes, atomic_json, fingerprint
from .manifest import save_manifest
from .render import compose, encode_webp, preflight, validate_webp
from .story import MockStoryGenerator, StoryGenerator, validate_story
from .layout import LAYOUT_PENDING, verified_regions
from .costs import CostBlocked


def safe_error(exc):
    if isinstance(exc, EngineError):
        return str(exc)
    # A generic exception could contain a secret. Do not log it or a traceback.
    return f'{type(exc).__name__}: unexpected local failure; details suppressed'


def select_rows(rows, limit, ids=None, retry_failed=False, resume_layout=False):
    allowed = {'pending', 'generating'} | ({'failed'} if retry_failed else set())
    return [row for row in rows if
            ((row['status'] == 'needs_review' and row['error_message'] == LAYOUT_PENDING)
             if resume_layout else row['status'] in allowed)
            and (ids is None or row['id'] in ids)][:limit]


def process_rows(rows, selected, manifest, output, work, config, fonts, *, mock, gateway=None,
                 story_generator=None, artwork_generator=None, resume_layout=False):
    output, work = Path(output), Path(work)
    story_generator = story_generator or (MockStoryGenerator() if mock else StoryGenerator(config, gateway))
    artwork_generator = artwork_generator or (MockArtworkGenerator() if mock else ArtworkGenerator(config, gateway))
    counts = {'needs_review': 0, 'failed': 0}
    for row in selected:
        item_work = work / f'{int(row["id"]):04d}'
        target = output / row['filename']
        try:
            if resume_layout and not all((item_work / name).is_file() for name in
                                         ('identity.json', 'story.json', 'artwork.png', 'panel_bounds.json')):
                raise EngineError('Layout resume requires all cached stages and verified bounds; no API request allowed')
            identity = fingerprint(row, config, mock)
            metadata_path = item_work / 'identity.json'
            if metadata_path.exists():
                if json.loads(metadata_path.read_text(encoding='utf-8')) != {'fingerprint': identity}:
                    raise EngineError('Checkpoint differs from input/config; choose a new work directory')
            else:
                if target.exists():
                    raise EngineError('Untracked output already exists; refusing to overwrite')
                atomic_json(metadata_path, {'fingerprint': identity})
            row.update(status='generating', review_status='pending', error_message='')
            save_manifest(manifest, rows)
            result_path = item_work / 'result.json'
            if target.exists() and not result_path.exists():
                raise EngineError('Existing output has no result checkpoint; refusing regeneration')
            if result_path.exists():
                result = json.loads(result_path.read_text(encoding='utf-8'))
                if target.exists() and result.get('fingerprint') == identity:
                    import hashlib
                    raw = target.read_bytes()
                    validate_webp(raw)
                    if hashlib.sha256(raw).hexdigest() != result['sha256']:
                        raise EngineError('Existing output hash mismatch')
                    row.update(status='needs_review', review_status='pending', error_message='')
                    save_manifest(manifest, rows)
                    counts['needs_review'] += 1
                    continue
            story_path = item_work / 'story.json'
            if story_path.exists():
                story = validate_story(json.loads(story_path.read_text(encoding='utf-8')), row)
            else:
                story = story_generator.generate(row)
                validate_story(story, row)
                atomic_json(story_path, story)
            # Reject missing generated glyphs or overflowing dialogue BEFORE paid art generation.
            preflight(story, row, fonts)
            art_path = item_work / 'artwork.png'
            if art_path.exists():
                with Image.open(art_path) as image:
                    image.load()
                    artwork = image.convert('RGB')
            else:
                artwork = artwork_generator.generate(story) if mock else artwork_generator.generate(story, idiom_id=row['id'])
                buffer = io.BytesIO()
                artwork.save(buffer, format='PNG')
                atomic_bytes(art_path, buffer.getvalue())
            regions = None
            if not mock:
                import hashlib
                bounds_path = item_work / 'panel_bounds.json'
                if not bounds_path.exists():
                    row.update(status='needs_review', review_status='layout_pending', error_message=LAYOUT_PENDING)
                    save_manifest(manifest, rows)
                    counts['needs_review'] += 1
                    continue
                regions = verified_regions(artwork.width, artwork.height,
                                           json.loads(bounds_path.read_text(encoding='utf-8')),
                                           hashlib.sha256(art_path.read_bytes()).hexdigest())
            image, overlays = compose(artwork, story, row, fonts, mock=mock, panel_regions=regions)
            encoded, compression = encode_webp(image, config)
            import hashlib
            result = {
                'id': row['id'], 'hanja': row['hanja'], 'reading': row['reading'],
                'filename': row['filename'], 'fingerprint': identity, 'mock': mock,
                'dimensions': [512, 1536], 'format': 'WEBP', 'compression': compression,
                'panel_regions': [list(region) for region in regions] if regions else None,
                'layout_verified': not mock,
                'overlays': overlays, 'sha256': hashlib.sha256(encoded).hexdigest(),
                'human_review_required': True,
                'review_checklist': ['Meaning is accurate', 'All four scenes contain characters',
                                     'No AI-drawn text', 'Korean dialogue is natural and child-safe',
                                     'Exact hanja answer and no final-panel reading', 'Text is legible'],
            }
            # Checkpoint first: a crash after publishing can be recovered without another API call.
            atomic_json(result_path, result)
            if target.exists():
                raise EngineError('Output already exists; refusing to overwrite')
            atomic_bytes(target, encoded)
            row.update(status='needs_review', review_status='pending', error_message='')
            counts['needs_review'] += 1
        except KeyboardInterrupt:
            # generating + checkpoints are intentionally kept for explicit resume.
            save_manifest(manifest, rows)
            raise
        except CostBlocked as exc:
            row.update(status='failed', review_status='pending', error_message=safe_error(exc))
            save_manifest(manifest, rows)
            raise
        except Exception as exc:
            row.update(status='failed', review_status='pending', error_message=safe_error(exc))
            counts['failed'] += 1
        save_manifest(manifest, rows)
    return counts


def approve(rows, identifier, manifest, output, work, config, *, mock, source=None):
    row = next((row for row in rows if row['id'] == identifier), None)
    if row is None or row['status'] not in ('needs_review', 'completed'):
        raise EngineError('Approval requires an existing needs_review item')
    result = json.loads((Path(work) / f'{int(identifier):04d}' / 'result.json').read_text(encoding='utf-8'))
    if result.get('mock') is not mock or result.get('fingerprint') != fingerprint(row, config, mock):
        raise EngineError('Review artifact does not match current item/config/mode')
    import hashlib
    raw = (Path(output) / row['filename']).read_bytes()
    validate_webp(raw)
    if hashlib.sha256(raw).hexdigest() != result['sha256']:
        raise EngineError('Review artifact hash differs from generated output')
    row.update(status='completed', review_status='approved', error_message='')
    save_manifest(manifest, rows)
    if not mock:
        if source is None:
            raise EngineError('Source path required for approved image recording')
        from .source_images import record_approved_image
        record_approved_image(source, row, output, hashlib.sha256(raw).hexdigest())
