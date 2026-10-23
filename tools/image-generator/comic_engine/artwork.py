import base64
import io

from PIL import Image, ImageDraw

from .common import EngineError
from .model_specs import image_request, validate_image_settings


def artwork_prompt(story):
    return (
        'Create one TEXT-FREE comic sheet: exactly four equal horizontal panels stacked top to bottom, '
        'one column, not a 2x2 grid. Each panel independently contains a full scene AND characters. '
        'Cute bright pastel educational art, traditional Korean village, SD children wearing hanbok. '
        'Same recurring characters throughout. Child-safe, no violence or scary imagery. '
        'No writing, no letters, no Korean or Chinese glyphs, no panel numbers, no captions, '
        'no speech bubbles, no watermarks. Fill every panel with a complete story scene. '
        'All text and bubbles will be placed outside the artwork later. '
        + '\n'.join(f'Panel {i + 1}: {p["scene"]}' for i, p in enumerate(story['panels']))
    )


class ArtworkGenerator:
    def __init__(self, config, gateway):
        validate_image_settings(config)
        self.config, self.gateway = config, gateway

    def generate(self, story, idiom_id=None):
        request = image_request(self.config, artwork_prompt(story))
        result = self.gateway.call(lambda client: client.images.generate(**request), idiom_id=idiom_id,
                                   request_type='image', model=self.config['image_model'], payload=request)
        try:
            raw = base64.b64decode(result.data[0].b64_json, validate=True)
            if len(raw) > 30_000_000:
                raise ValueError('Image payload too large')
            with Image.open(io.BytesIO(raw)) as image:
                expected = tuple(map(int, self.config['image_size'].split('x')))
                if image.size != expected:
                    raise ValueError('Unexpected image dimensions')
                image.load()
                return image.convert('RGB')
        except (ValueError, TypeError, IndexError, AttributeError, OSError):
            raise EngineError('Image API returned invalid image data') from None


class MockArtworkGenerator:
    def generate(self, story):
        # Deterministic local fixture, no model and no network. Not production artwork.
        image = Image.new('RGB', (512, 1536), '#fff5e5')
        draw = ImageDraw.Draw(image)
        for panel in range(4):
            y = panel * 384
            draw.rectangle((0, y, 511, y + 383), fill=['#dff4fa', '#e5f4dc', '#fce6dd', '#efe5fc'][panel])
            draw.rectangle((0, y + 250, 511, y + 383), fill='#e5edce')
            for house_x in (25, 330):
                draw.rectangle((house_x, y + 145, house_x + 145, y + 270), fill='#f5dab9')
                draw.polygon([(house_x - 12, y + 145), (house_x + 72, y + 100),
                              (house_x + 157, y + 145)], fill='#9caec5')
                draw.rectangle((house_x + 55, y + 205, house_x + 85, y + 270), fill='#b28d77')
            for x, color in ((207 + panel * 3, '#e4a9c1'), (290 - panel * 3, '#a2c5df')):
                draw.polygon([(x, y + 215), (x - 30, y + 285), (x + 30, y + 285)], fill=color)
                draw.ellipse((x - 23, y + 166, x + 23, y + 212), fill='#ffe0ba', outline='#745a52', width=2)
                draw.arc((x - 23, y + 163, x + 23, y + 199), 180, 360, fill='#57483f', width=9)
                draw.ellipse((x - 10, y + 185, x - 6, y + 189), fill='#53453b')
                draw.ellipse((x + 6, y + 185, x + 10, y + 189), fill='#53453b')
                draw.arc((x - 7, y + 189, x + 7, y + 202), 0, 180, fill='#a76d62', width=2)
            draw.ellipse((226, y + 252, 273, y + 274), fill='#b78e65')
            for apple_x in (233, 247, 261):
                draw.ellipse((apple_x, y + 247, apple_x + 10, y + 257), fill='#e89b86')
        return image
