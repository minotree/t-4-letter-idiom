"""Offline editorial/export/import workflow. No SDK, API keys, browser or network."""
from datetime import date, datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from collections import Counter

from PIL import Image

from .artwork import artwork_prompt
from .common import EngineError, ROOT, NOTICE, NUMBERS, atomic_json
from .fonts import Fonts
from .layout import verified_regions
from .manifest import manifest_lock, read_manifest, save_manifest
from .render import compose, encode_webp, preflight, validate_webp
from .story import validate_story

DEFAULT_WORKSPACE = ROOT / 'data/manual_workflow'


def seoul_today():
    return datetime.now(timezone(timedelta(hours=9))).date()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def packed(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


class FileStore:
    """Publish complete files without ever replacing an existing different file."""
    def exists(self, path):
        return Path(path).is_file()

    def read(self, path):
        return Path(path).read_bytes()

    def put(self, path, data):
        path = Path(path)
        if path.exists():
            if path.read_bytes() == data:
                return
            raise EngineError('Existing artifact differs; refusing to overwrite')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # Atomic create-only publication, including two independent workers.
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise EngineError('Concurrent artifact collision; refusing overwrite') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def identity(row):
    return {key: row[key] for key in ('id', 'hanja', 'reading', 'filename')}


def review_stamp(entry, prefix):
    if not isinstance(entry.get(prefix + '_reviewer'), str) or not entry[prefix + '_reviewer'].strip():
        raise EngineError('Reviewer name is required')
    try:
        reviewed = date.fromisoformat(entry[prefix + '_reviewed_on'])
        if reviewed > seoul_today():
            raise ValueError()
    except (TypeError, ValueError):
        raise EngineError('Valid non-future review date is required') from None


def approved_story(entry, row):
    if entry.get('meaning_status') != 'verified':
        raise EngineError('meaning_pending')
    if not isinstance(entry.get('meaning'), str) or not entry['meaning'].strip():
        raise EngineError('Verified meaning is empty')
    references = entry.get('meaning_sources')
    if not isinstance(references, list) or not references or any(not isinstance(ref, str) or not ref.strip() for ref in references):
        raise EngineError('Meaning needs source references')
    review_stamp(entry, 'meaning')
    if entry.get('story_status') != 'verified':
        raise EngineError('story_pending')
    review_stamp(entry, 'story')
    story = validate_story(entry.get('story'), row)
    if story['meaning'] != entry['meaning']:
        raise EngineError('Story meaning differs from verified meaning')
    return story


def read_catalog(path, rows):
    catalog = json.loads(Path(path).read_text(encoding='utf-8'))
    if catalog.get('schema_version') != 1 or not isinstance(catalog.get('items'), list) or len(catalog['items']) != len(rows):
        raise EngineError('Catalog schema or count differs from source')
    for entry, row in zip(catalog['items'], rows):
        if not isinstance(entry, dict) or any(entry.get(key) != value for key, value in identity(row).items()):
            raise EngineError('Catalog identity/order differs from original source')
    return catalog


def initialize(workspace, rows):
    workspace = Path(workspace)
    catalog_path = workspace / 'catalog.json'
    if not catalog_path.exists():
        items = [dict(identity(row), meaning_status='pending', meaning=None, meaning_sources=[],
                      meaning_reviewer='', meaning_reviewed_on=None, story_status='pending', story=None,
                      story_reviewer='', story_reviewed_on=None) for row in rows]
        FileStore().put(catalog_path, packed({'schema_version': 1, 'items': items}))
    read_catalog(catalog_path, rows)
    manifest = workspace / 'image_manifest.csv'
    if not manifest.exists():
        save_manifest(manifest, rows)


def production_packet(entry, row):
    story = approved_story(entry, row)
    packet = dict(identity(row), meaning=entry['meaning'], meaning_sources=entry['meaning_sources'],
                  meaning_reviewer=entry['meaning_reviewer'], meaning_reviewed_on=entry['meaning_reviewed_on'],
                  story_reviewer=entry['story_reviewer'], story_reviewed_on=entry['story_reviewed_on'], story=story)
    # Answer/reading/dialogue are in the editorial packet ONLY, not this prompt.
    prompt = artwork_prompt(story) + '\nKeep all important characters inside their own panel. Do not render any text.\n'
    packet['image_prompt_sha256'] = sha(prompt.encode('utf-8'))
    return packet, prompt


def prepare(workspace, rows):
    workspace = Path(workspace)
    with manifest_lock(workspace / 'image_manifest.csv'):
        initialize(workspace, rows)
        catalog = read_catalog(workspace / 'catalog.json', rows)
        report = {'total': len(rows), 'meaning_pending': 0, 'story_pending': 0, 'ready': 0, 'invalid': 0, 'items': []}
        for entry, row in zip(catalog['items'], rows):
            try:
                packet, prompt = production_packet(entry, row)
                revision = sha(packed(packet))
                destination = workspace / 'prompts' / f'{int(row["id"]):04d}' / revision
                FileStore().put(destination / 'production.json', packed(packet))
                FileStore().put(destination / 'image_prompt.txt', prompt.encode('utf-8'))
                report['ready'] += 1
                report['items'].append({'id': row['id'], 'state': 'ready', 'directory': str(destination)})
            except EngineError as exc:
                state = str(exc) if str(exc) in ('meaning_pending', 'story_pending') else 'invalid'
                report[state] += 1
                report['items'].append({'id': row['id'], 'state': state, 'error': str(exc)})
        atomic_json(workspace / 'preparation_report.json', report)
    return report


def verify_overlays(overlays, row=None, story=None, *, layout_settings=None):
    if layout_settings is not None:
        from .layout_v2 import validate_overlays
        return validate_overlays(overlays, row, story, layout_settings)
    art_boxes = [(2, 116 + i * 384, 510, 306 + i * 384) for i in range(4)]
    if not isinstance(overlays, list) or len(overlays) < 10:
        raise EngineError('Composition overlay audit is incomplete')
    boxes = []
    for entry in overlays:
        box = entry.get('box')
        if (not isinstance(box, list) or len(box) != 4
                or any(type(v) not in (int, float) for v in box)
                or not (0 <= box[0] <= box[2] <= 512 and 0 <= box[1] <= box[3] <= 1536)):
            raise EngineError('Text overlay outside canvas')
        for other in art_boxes + boxes:
            if max(box[0], other[0]) < min(box[2], other[2]) and max(box[1], other[1]) < min(box[3], other[3]):
                raise EngineError('Text overlaps artwork or another text box')
        boxes.append(box)
    if row is not None and story is not None:
        expected = list(NUMBERS) + [panel['dialogue'] for panel in story['panels']] + [row['hanja'], NOTICE]
        if Counter(overlay.get('text') for overlay in overlays) != Counter(expected):
            raise EngineError('Composition text differs from approved script or required labels')
        answers = [overlay for overlay in overlays if overlay.get('role') == 'answer']
        if (len(answers) != 1 or answers[0]['text'] != row['hanja']
                or answers[0]['box'][1] < 1461 or answers[0].get('font_size', 0) < 28):
            raise EngineError('Final answer is missing, misplaced or too small')
        for index, number in enumerate(NUMBERS):
            found = next(overlay for overlay in overlays if overlay['text'] == number)
            if not index * 384 <= found['box'][1] < (index + 1) * 384:
                raise EngineError('Panel numbering order is invalid')


class PillowProcessor:
    def __init__(self, config):
        self.config = config
        self.fonts = Fonts(config)

    def inspect(self, data):
        if len(data) > 30_000_000:
            raise EngineError('Import exceeds 30 MB')
        # PNG metadata access can load the image and invalidate verify().
        # Verify an untouched object, then reopen for metadata inspection.
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            if (image.format != 'PNG' or getattr(image, 'n_frames', 1) != 1
                    or min(image.size) < 512 or image.width * image.height > 8294400
                    or image.getexif().get(274, 1) != 1):
                raise EngineError('Import must be a static PNG with supported dimensions and no rotated EXIF')
            return image.size

    def render(self, data, story, row, regions):
        preflight(story, row, self.fonts)
        self.inspect(data)
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.mode == 'RGBA' or 'transparency' in image.info:
                white = Image.new('RGBA', image.size, 'white')
                image = Image.alpha_composite(white, image.convert('RGBA')).convert('RGB')
            else:
                image = image.convert('RGB')
            final, overlays = compose(image, story, row, self.fonts, mock=False, panel_regions=regions,
                                      artwork_top=116, artwork_height=190)
        verify_overlays(overlays, row, story)
        encoded, compression = encode_webp(final, self.config)
        return encoded, {'overlays': overlays, 'compression': compression, 'dimensions': [512, 1536], 'format': 'WEBP'}

    def validate(self, data):
        validate_webp(data)


def import_context(workspace, row, catalog, imports, config, store, processor):
    entry = catalog['items'][int(row['id']) - 1]
    packet, prompt = production_packet(entry, row)
    revision = sha(packed(packet))
    exported = Path(workspace) / 'prompts' / f'{int(row["id"]):04d}' / revision
    if store.read(exported / 'production.json') != packed(packet) or store.read(exported / 'image_prompt.txt') != prompt.encode('utf-8'):
        raise EngineError('Exported prompt is missing or stale; run prepare first')
    input_path = Path(imports) / f'{int(row["id"]):04d}.png'
    raw = store.read(input_path)
    sidecar = json.loads(store.read(input_path.with_suffix('.json')).decode('utf-8'))
    if (any(sidecar.get(key) != row[key] for key in ('id', 'hanja', 'reading'))
            or sidecar.get('identity_confirmed') is not True
            or not isinstance(sidecar.get('reviewer'), str) or not sidecar['reviewer'].strip()
            or sidecar.get('image_prompt_sha256') != packet['image_prompt_sha256']):
        raise EngineError('Import identity or prompt confirmation does not match')
    width, height = processor.inspect(raw)
    regions = verified_regions(width, height, sidecar, sha(raw))
    context = {'identity': identity(row), 'packet_sha256': revision, 'input_sha256': sha(raw),
               'sidecar_sha256': sha(packed(sidecar)), 'config': config, 'manual_version': 1}
    return raw, packet['story'], regions, sha(packed(context))


def import_item(workspace, rows, source, identifier, imports, output, config, *, store=None, processor=None):
    workspace, output = Path(workspace), Path(output)
    store = store or FileStore()
    manifest = workspace / 'image_manifest.csv'
    with manifest_lock(manifest):
        local_rows = read_manifest(manifest, source)
        row = next((r for r in local_rows if r['id'] == identifier), None)
        if row is None:
            raise EngineError('Unknown import ID')
        if row['status'] == 'completed':
            return {'id': identifier, 'state': 'completed', 'skipped': True}
        target = output / row['filename']
        checkpoint = workspace / 'work' / f'{int(identifier):04d}'
        result_path, staged = checkpoint / 'import_result.json', checkpoint / 'final.webp'
        try:
            processor = processor or PillowProcessor(config)
            catalog = read_catalog(workspace / 'catalog.json', rows)
            raw, story, regions, context = import_context(workspace, row, catalog, imports, config, store, processor)
            row.update(status='generating', review_status='pending', error_message='')
            save_manifest(manifest, local_rows)
            if store.exists(result_path):
                result = json.loads(store.read(result_path).decode('utf-8'))
                if result.get('context_sha256') != context:
                    raise EngineError('Import checkpoint differs; existing output is preserved')
                encoded = store.read(staged)
                if sha(encoded) != result['output_sha256']:
                    raise EngineError('Staged output hash mismatch')
            else:
                if store.exists(target):
                    raise EngineError('Untracked output already exists; refusing overwrite')
                encoded, details = processor.render(raw, story, row, regions)
                verify_overlays(details['overlays'], row, story)
                answers = [overlay['text'] for overlay in details['overlays'] if overlay.get('role') == 'answer']
                if answers != [row['hanja']]:
                    raise EngineError('Composed answer differs from exact CSV source')
                result = dict(identity(row), context_sha256=context, output_sha256=sha(encoded),
                              mode='manual-chatgpt', human_review_required=True, **details)
                processor.validate(encoded)
                store.put(staged, encoded)
                store.put(result_path, packed(result))
            processor.validate(encoded)
            store.put(target, encoded)
            row.update(status='needs_review', review_status='pending', error_message='')
            save_manifest(manifest, local_rows)
            return {'id': identifier, 'state': 'needs_review', 'output': str(target)}
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            error = str(exc) if isinstance(exc, EngineError) else f'{type(exc).__name__}: local import failure'
            row.update(status='failed', review_status='pending', error_message=error)
            save_manifest(manifest, local_rows)
            raise EngineError(error) from None


def approve_item(workspace, rows, source, identifier, imports, output, config, reviewer, *, store=None, processor=None):
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise EngineError('Human reviewer is required')
    workspace = Path(workspace)
    store, processor = store or FileStore(), processor or PillowProcessor(config)
    manifest = workspace / 'image_manifest.csv'
    with manifest_lock(manifest):
        local_rows = read_manifest(manifest, source)
        row = next((r for r in local_rows if r['id'] == identifier), None)
        if row is None or row['status'] not in ('needs_review', 'completed'):
            raise EngineError('Approval requires needs_review state')
        try:
            catalog = read_catalog(workspace / 'catalog.json', rows)
            _, story, _, context = import_context(workspace, row, catalog, imports, config, store, processor)
            result_path = workspace / 'work' / f'{int(identifier):04d}' / 'import_result.json'
            result = json.loads(store.read(result_path).decode('utf-8'))
            raw = store.read(Path(output) / row['filename'])
            processor.validate(raw)
            if result.get('context_sha256') != context or result.get('output_sha256') != sha(raw):
                raise EngineError('Approval artifact changed after validation')
            verify_overlays(result['overlays'], row, story)
            approval_path = result_path.with_name('approval.json')
            if store.exists(approval_path):
                approval = json.loads(store.read(approval_path).decode('utf-8'))
                if approval.get('output_sha256') != sha(raw) or approval.get('context_sha256') != context:
                    raise EngineError('Existing human approval differs from current artifact')
            else:
                store.put(approval_path, packed({'id': identifier, 'reviewer': reviewer,
                          'reviewed_on': seoul_today().isoformat(), 'output_sha256': sha(raw), 'context_sha256': context}))
            row.update(status='completed', review_status='approved', error_message='')
            save_manifest(manifest, local_rows)
            from .source_images import record_approved_image
            record_approved_image(source, row, output, sha(raw))
            return {'id': identifier, 'state': 'completed'}
        except Exception as exc:
            row['error_message'] = str(exc) if isinstance(exc, EngineError) else type(exc).__name__ + ': local approval failure'
            save_manifest(manifest, local_rows)
            raise EngineError(row['error_message']) from None
