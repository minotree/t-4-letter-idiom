from contextlib import contextmanager
import csv
import io
from pathlib import Path
import re

from validate_data import FIELDS, load_source
from .common import EngineError, atomic_bytes

STATUSES = {'pending', 'generating', 'completed', 'failed', 'needs_review'}


def read_manifest(path, source):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != FIELDS:
            raise EngineError('Manifest columns differ from the supported schema')
        rows = list(reader)
    original, _ = load_source(source)
    if len(rows) != len(original):
        raise EngineError('Manifest count differs from source')
    ids, filenames = set(), set()
    for row, expected in zip(rows, original):
        if None in row or any(value is None for value in row.values()):
            raise EngineError('Malformed manifest row')
        if any(row[key] != expected[key] for key in FIELDS[:4]):
            raise EngineError('Manifest identity/order differs from original CSV')
        if row['id'] in ids or row['filename'].casefold() in filenames:
            raise EngineError('Manifest ID or Windows filename collision')
        ids.add(row['id'])
        filenames.add(row['filename'].casefold())
        if re.search(r'[<>:"/\\|?*\x00-\x1f]', row['filename']) or Path(row['filename']).name != row['filename']:
            raise EngineError('Unsafe output filename')
        if row['status'] not in STATUSES:
            raise EngineError('Unknown manifest status')
    return rows


def save_manifest(path, rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, buffer.getvalue().encode('utf-8-sig'))


@contextmanager
def manifest_lock(path):
    # Stable separate inode: atomic manifest replacements cannot invalidate the lock.
    # OS releases the lock on process exit/crash; the empty marker is reusable.
    lock_path = Path(str(path) + '.lock.tmp')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stream = lock_path.open('a+b')
    locked = False
    try:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        import os
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise EngineError('Another process holds this manifest lock') from None
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise EngineError('Another process holds this manifest lock') from None
        locked = True
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()
