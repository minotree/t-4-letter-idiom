"""Offline preview layout. Coordinates in settings are panel-local output pixels.

Protected regions are editorial proposals until a human reviews the preview.
No import/checkpoint/approval state is changed by this module.
"""
from collections import Counter
from PIL import Image, ImageDraw, ImageOps
from .common import EngineError, NOTICE, NUMBERS
from .render import text_layout, draw_text
from .story import validate_story

VERSION = 2
RENDER_REVISION = 3


def centered_answer(text, checked_font, vertical_box, padding=12):
    """Measure ink bounds, including font bearings, and center on the panel."""
    checked_font.require(text)
    for size in range(32, 27, -1):
        font = checked_font.at(size)
        left, top, right, bottom = font.getbbox(text, anchor='lt')
        width, height = right-left, bottom-top
        if width > 0 and height > 0 and width+2*padding <= 508 and height+8 <= vertical_box[3]-vertical_box[1]:
            x = (512-width)/2
            y = (vertical_box[1]+vertical_box[3]-height)/2
            return {'text':text,'role':'answer','panel':3,'font_size':size,
                    'box':[x,y,x+width,y+height],
                    'surface':[x-padding,vertical_box[1],x+width+padding,vertical_box[3]],
                    'draw_position':[x-left,y-top], 'padding':padding}
    raise EngineError('Hanja answer cannot fit legibly; needs_review')


def intersects(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def inside(a, b):
    return b[0] <= a[0] < a[2] <= b[2] and b[1] <= a[1] < a[3] <= b[3]


def validate_overlays(overlays, row, story, settings):
    if settings.get('layout_version') != VERSION or len(settings.get('panels', [])) != 4:
        raise EngineError('Invalid layout version or panel configuration')
    expected = list(NUMBERS) + [p['dialogue'] for p in story['panels']] + [row['hanja'], NOTICE]
    if Counter(e['text'] for e in overlays) != Counter(expected):
        raise EngineError('Composition text differs from approved script')
    for i, config in enumerate(settings['panels']):
        entries = [e for e in overlays if e['panel'] == i]
        if Counter(e['role'] for e in entries) != Counter(
                ['number', 'dialogue'] + (['answer', 'notice'] if i == 3 else [])):
            raise EngineError('Missing or duplicate panel labels')
        protected = config['protected_regions']
        for box in protected:
            if not inside(box, [0, 0, 512, 384]):
                raise EngineError('Invalid protected region')
        surfaces = []
        for entry in entries:
            if not inside(entry['box'], [0, 0, 512, 384]):
                raise EngineError('Text outside panel')
            if entry['role'] == 'number' and entry['text'] != NUMBERS[i]:
                raise EngineError('Invalid panel number')
            if entry['role'] == 'dialogue' and (entry['text'] != story['panels'][i]['dialogue'] or entry['font_size'] < 20):
                raise EngineError('Invalid dialogue')
            if entry['role'] == 'answer' and (entry['text'] != row['hanja'] or entry['font_size'] < 28):
                raise EngineError('Invalid answer')
            body = entry['surface']
            if not inside(body, [2, 2, 510, 382]) or not inside(entry['box'], body):
                raise EngineError('Text clipped by label or panel')
            shapes = [body] + ([entry['tail_box']] if 'tail_box' in entry else [])
            for shape in shapes:
                if not inside(shape, [2, 2, 510, 382]):
                    raise EngineError('Bubble tail outside panel')
                if any(intersects(shape, region) for region in protected):
                    raise EngineError('Overlay intersects protected region; needs_review')
                if any(intersects(shape, other) for other in surfaces):
                    raise EngineError('Labels overlap')
            surfaces.extend(shapes)


def compose_preview(artwork, story, row, fonts, regions, settings):
    validate_story(story, row)
    if settings.get('layout_version') != VERSION or len(settings.get('panels', [])) != 4 or len(regions) != 4:
        raise EngineError('Invalid layout configuration')
    canvas = Image.new('RGB', (512, 1536), '#fffaf1')
    overlays, placements = [], []
    for i, config in enumerate(settings['panels']):
        source = artwork.crop(regions[i]).convert('RGB')
        scene = ImageOps.contain(source, (508, 380), Image.Resampling.LANCZOS)
        x, y = (512-scene.width)//2, (384-scene.height)//2
        canvas.paste(scene, (x, i*384+y))
        placements.append({'panel': i, 'source_region': list(regions[i]), 'art_box': [x,y,x+scene.width,y+scene.height]})
        local = []
        font, lines, spacing = text_layout(story['panels'][i]['dialogue'], fonts.korean,
                                          (0,0,config['bubble_width']-24,90), 23,20)
        height = (len(lines)-1)*spacing + max(font.getbbox(line,anchor='lt')[3] for line in lines) + 20
        for bx, by in config['bubble_candidates']:
            body = [bx,by,bx+config['bubble_width'],by+height]
            tail = [bx+24,by+height,bx+44,by+height+10]
            if (inside(body,[x,y,x+scene.width,y+scene.height])
                    and inside(tail,[x,y,x+scene.width,y+scene.height])
                    and not any(intersects(s,p) for s in (body,tail) for p in config['protected_regions'])):
                break
        else:
            raise EngineError('No safe speech bubble placement; needs_review')
        local.append({'text':story['panels'][i]['dialogue'],'role':'dialogue','panel':i,
                      'box':[bx+12,by+10,body[2]-12,body[3]-10],'font_size':font.size,
                      'surface':body,'tail_box':tail})
        nx,ny=config['number_position']
        local.append({'text':NUMBERS[i],'role':'number','panel':i,'box':[nx+4,ny+3,nx+36,ny+36],
                      'surface':[nx,ny,nx+40,ny+40],'font_size':28})
        if i==3:
            local.append(centered_answer(row['hanja'],fonts.hanja,config['answer_box']))
            for role,text,box,size in [('notice',NOTICE,config['notice_box'],17)]:
                f,ls,sp=text_layout(text,fonts.hanja if role=='answer' else fonts.korean,
                                   (box[0]+8,box[1]+4,box[2]-8,box[3]-4),size,size)
                local.append({'text':text,'role':role,'panel':i,'box':[box[0]+8,box[1]+4,box[2]-8,box[3]-4],
                              'surface':box,'font_size':f.size})
        overlays.extend(local)
    validate_overlays(overlays,row,story,settings)
    draw=ImageDraw.Draw(canvas)
    for e in overlays:
        offset=e['panel']*384
        b=e['surface']; shifted=(b[0],b[1]+offset,b[2],b[3]+offset)
        draw.rounded_rectangle(shifted,radius=12,fill='white',outline='#776977',width=1)
        if 'tail_box' in e:
            t=e['tail_box']
            draw.polygon([(t[0],t[1]+offset),(t[2],t[1]+offset),(t[0]+5,t[3]+offset)],fill='white')
        box=e['box']; box=(box[0],box[1]+offset,box[2],box[3]+offset)
        if e['role']=='answer':
            px,py=e['draw_position']
            draw.text((px,py+offset),e['text'],font=fonts.hanja.at(e['font_size']),
                      fill='#302d38',anchor='lt')
        else:
            draw_text(draw,e['text'],fonts.korean,box,e['font_size'],e['font_size'])
    for i in range(4):
        draw.rectangle((1,i*384+1,510,i*384+382),outline='#776977',width=2)
    return canvas, {'layout_version':VERSION,'render_revision':RENDER_REVISION,'overlays':overlays,'placements':placements,
                    'state':'needs_review','protected_regions_human_verified':False}
