from fontTools.ttLib import TTFont
from PIL import ImageFont

from .common import EngineError, NOTICE, NUMBERS


class CheckedFont:
    def __init__(self, spec):
        self.path, self.index = spec['path'], spec['index']
        try:
            with TTFont(self.path, fontNumber=self.index) as font:
                self.cmap = {code for code, glyph in (font.getBestCmap() or {}).items()
                             if glyph != '.notdef'}
            self.at(24)
        except Exception as exc:
            raise EngineError(f'Font unavailable or invalid: {self.path}, face {self.index}') from exc

    def missing(self, text):
        return sorted({ord(char) for char in text if not char.isspace() and ord(char) not in self.cmap})

    def require(self, text):
        missing = self.missing(text)
        if missing:
            raise EngineError('Missing glyphs in configured font: ' +
                              ', '.join(f'U+{code:04X}' for code in missing))

    def at(self, size):
        return ImageFont.truetype(self.path, size=size, index=self.index)


class Fonts:
    def __init__(self, config):
        self.korean = CheckedFont(config['korean_font'])
        self.hanja = CheckedFont(config['hanja_font'])

    def check_manifest(self, rows):
        hanja_text = ''.join(row['hanja'] for row in rows)
        korean_text = ''.join(row['reading'] for row in rows) + NOTICE + NUMBERS
        # All modern Korean syllables; other characters are checked per dialogue.
        korean_text += ''.join(chr(code) for code in range(0xAC00, 0xD7A4))
        korean_missing = self.korean.missing(korean_text)
        hanja_missing = self.hanja.missing(hanja_text)
        report = {
            'row_count': len(rows),
            'unique_source_characters': len(set(hanja_text)),
            'korean_font': {'path': self.korean.path, 'index': self.korean.index},
            'hanja_font': {'path': self.hanja.path, 'index': self.hanja.index},
            'missing_korean': [f'U+{code:04X}' for code in korean_missing],
            'missing_hanja': [f'U+{code:04X}' for code in hanja_missing],
        }
        if korean_missing or hanja_missing:
            raise EngineError('Font coverage failed: ' + str(report))
        return report
