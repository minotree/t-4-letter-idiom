import io

from PIL import Image, ImageDraw, ImageOps, ImageStat, features

from .common import EngineError, NOTICE, NUMBERS
from .story import validate_story


def wrapped(text, font, width):
    lines, current = [], ''
    for char in text:
        candidate = current + char
        if font.getlength(candidate) > width and current:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def text_layout(text, checked_font, box, maximum=23, minimum=20):
    checked_font.require(text)
    width, height = box[2] - box[0], box[3] - box[1]
    for size in range(maximum, minimum - 1, -1):
        font = checked_font.at(size)
        lines = wrapped(text, font, width)
        spacing = size + 5
        needed_height = (len(lines) - 1) * spacing + max(
            (font.getbbox(line, anchor='lt')[3] for line in lines), default=0)
        if needed_height <= height and all(font.getlength(line) <= width for line in lines):
            return font, lines, spacing
    raise EngineError('Text cannot fit without reducing readability')


def draw_text(draw, text, checked_font, box, maximum=23, minimum=20):
    font, lines, spacing = text_layout(text, checked_font, box, maximum, minimum)
    for index, line in enumerate(lines):
        draw.text((box[0], box[1] + index * spacing), line, font=font, fill='#302d38', anchor='lt')
    return {'text': text, 'box': list(box), 'font_size': font.size, 'line_count': len(lines)}


def preflight(story, row, fonts):
    validate_story(story, row)
    for panel in story['panels']:
        text_layout(panel['dialogue'], fonts.korean, (76, 23, 482, 99))
    fonts.hanja.require(row['hanja'])
    if not row['hanja'].strip():
        raise EngineError('Empty hanja answer')
    fonts.korean.require(NOTICE + NUMBERS)


def compose(artwork, story, row, fonts, mock=False, panel_regions=None, artwork_top=104, artwork_height=202):
    preflight(story, row, fonts)
    if artwork.width < 512 or artwork.height < 512:
        raise EngineError('Artwork is too small for four panels')
    if not mock and panel_regions is None:
        raise EngineError('Live sheet composition requires verified panel boundaries')
    canvas = Image.new('RGB', (512, 1536), '#fffaf1')
    draw = ImageDraw.Draw(canvas)
    overlays = []
    for index, panel in enumerate(story['panels']):
        top = index * 384
        region = (panel_regions[index] if panel_regions is not None else
                  (0, round(index * artwork.height / 4), artwork.width, round((index + 1) * artwork.height / 4)))
        source = artwork.crop(region).convert('RGB')
        if max(ImageStat.Stat(source).stddev) < 2:
            raise EngineError(f'Artwork panel {index + 1} is blank')
        # Contain rather than stretching or cropping away scene characters.
        scene = ImageOps.contain(source, (508, artwork_height), Image.Resampling.LANCZOS)
        canvas.paste(scene, ((512 - scene.width) // 2, top + artwork_top + (artwork_height - scene.height) // 2))
        draw.rounded_rectangle((59, top + 12, 497, top + 101), radius=17, fill='white', outline='#a59baa', width=2)
        draw.polygon([(83, top + 100), (105, top + 100), (91, top + 112)], fill='white')
        overlays.append(draw_text(draw, NUMBERS[index], fonts.korean,
                                  (10, top + 24, 53, top + 65), 32, 28))
        overlays.append(draw_text(draw, panel['dialogue'], fonts.korean,
                                  (76, top + 23, 482, top + 99)))
        if index == 3:
            # The exact original source string is the only answer text.
            answer = row['hanja']
            for size in range(42, 27, -1):
                font = fonts.hanja.at(size)
                if font.getlength(answer) <= 476:
                    break
            else:
                raise EngineError('Hanja answer cannot fit legibly')
            draw.rounded_rectangle((8, top + 309, 504, top + 356), radius=8, fill='#fff0c7')
            x = (512 - font.getlength(answer)) / 2
            draw.text((x, top + 312), answer, font=font, fill='#332822', anchor='lt')
            overlays.append({'text': answer, 'box': [x, top + 312, x + font.getlength(answer), top + 356],
                             'font_size': size, 'role': 'answer'})
            overlays.append(draw_text(draw, NOTICE, fonts.korean,
                                      (115, top + 362, 500, top + 382), 17, 17))
        elif mock:
            overlays.append(draw_text(draw, 'MOCK · 배치 검사용', fonts.korean,
                                      (157, top + 335, 490, top + 363), 18, 18))
        draw.rectangle((1, top + 1, 510, top + 382), outline='#9e91a0', width=2)
    return canvas, overlays


def encode_webp(image, config):
    if not features.check('webp'):
        raise EngineError('Pillow WebP support is unavailable')
    # Never add meaningless bytes to reach the lower target; never shrink text.
    selected, selected_quality = None, None
    qualities = sorted(set([100, 95, 90, 85, config['minimum_quality']]), reverse=True)
    for quality in qualities:
        if quality < config['minimum_quality']:
            continue
        buffer = io.BytesIO()
        image.save(buffer, format='WEBP', quality=quality, method=6, exact=True)
        selected, selected_quality = buffer.getvalue(), quality
        if len(selected) <= config['target_max_bytes']:
            break
    validate_webp(selected)
    return selected, {
        'bytes': len(selected), 'quality': selected_quality,
        'within_target': config['target_min_bytes'] <= len(selected) <= config['target_max_bytes'],
        'size_note': ('within_target' if config['target_min_bytes'] <= len(selected) <= config['target_max_bytes']
                      else 'outside_target_readability_preserved'),
    }


def validate_webp(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != 'WEBP' or image.size != (512, 1536) or getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Invalid format or size')
            image.load()
    except (OSError, ValueError) as exc:
        raise EngineError('Output WebP validation failed') from exc
