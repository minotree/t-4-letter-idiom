"""Pure geometry only: no image allocation, decoding, rendering or network."""
from .common import EngineError

LAYOUT_PENDING = 'Awaiting verified panel bounds: add panel_bounds.json, then use --resume-layout'


def fit_inside(source_size, box_size):
    sw, sh = source_size
    bw, bh = box_size
    if min(sw, sh, bw, bh) <= 0:
        raise EngineError('Layout dimensions must be positive')
    scale = min(bw / sw, bh / sh)
    return max(1, round(sw * scale)), max(1, round(sh * scale))


def verified_regions(width, height, document, artwork_hash):
    if not isinstance(document, dict) or document.get('verified') is not True:
        raise EngineError('Panel boundaries require explicit human verification')
    if document.get('artwork_sha256') != artwork_hash:
        raise EngineError('Panel bounds do not match the checkpoint artwork hash')
    cuts = document.get('cut_lines')
    if (not isinstance(cuts, list) or len(cuts) != 5
            or any(type(value) is not int for value in cuts)
            or cuts[0] != 0 or cuts[-1] != height
            or any(a >= b for a, b in zip(cuts, cuts[1:]))):
        raise EngineError('cut_lines must be five strictly increasing integers from 0 to image height')
    # Full-width, contiguous regions retain every source pixel. The verified flag
    # attests that the human checked no character crosses these horizontal lines.
    return [(0, top, width, bottom) for top, bottom in zip(cuts, cuts[1:])]
