"""Final approval CSV publication, serialized and recoverable by reapproval."""
import csv
import hashlib
import io
from pathlib import Path
from validate_data import source_table, filename_for
from .common import EngineError, atomic_bytes
from .manifest import manifest_lock
from .render import validate_webp


def record_approved_image(source, row, output, expected_hash):
    if row.get('status') != 'completed' or row.get('review_status') != 'approved':
        raise EngineError('CSV recording requires final human approval')
    filename = row['filename']
    if filename != filename_for(int(row['id']), row['reading']):
        raise EngineError('Final filename does not match idiom ID')
    image_path = Path(output) / filename
    if any(part.casefold() in ('previews', 'imports') for part in image_path.resolve().parts):
        raise EngineError('Preview/import images cannot be recorded')
    raw_image = image_path.read_bytes()
    validate_webp(raw_image)
    if hashlib.sha256(raw_image).hexdigest() != expected_hash:
        raise EngineError('Final approved image hash mismatch')
    source = Path(source)
    with manifest_lock(source):
        raw = source.read_bytes()
        header, rows = source_table(raw)
        index = int(row['id']) - 1
        if not 0 <= index < len(rows) or rows[index][:2] != [row['hanja'], row['reading']]:
            raise EngineError('Source identity/order differs at approved ID')
        if header is None:
            header = ['hanja', 'reading']
        if 'image_filename' not in header:
            header.append('image_filename')
            for record in rows:
                record.append('')
        column = header.index('image_filename')
        previous = rows[index][column]
        if previous == filename:
            return False
        if previous:
            raise EngineError('Different image filename already recorded')
        rows[index][column] = filename
        # Retain BOM presence and newline convention; parsed source values are untouched.
        newline = '\r\n' if b'\r\n' in raw else '\n'
        buffer = io.StringIO(newline='')
        writer = csv.writer(buffer, lineterminator=newline)
        writer.writerow(header)
        writer.writerows(rows)
        encoding = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
        encoded = buffer.getvalue().encode(encoding)
        new_header, new_rows = source_table(encoded)
        assert new_header == header and new_rows == rows
        backup = source.with_name(source.name + '.' + hashlib.sha256(raw).hexdigest() + '.bak')
        if backup.exists():
            if backup.read_bytes() != raw:
                raise EngineError('Source backup differs; refusing update')
        else:
            # Flush the immutable backup before replacing the source.
            import os
            with backup.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        if source.read_bytes() != raw:
            raise EngineError('Source changed during update')
        atomic_bytes(source, encoded)
        return True
