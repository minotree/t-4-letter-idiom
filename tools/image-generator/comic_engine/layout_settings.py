"""Settings-only schema v1. No renderer/approval integration or file writes."""
import copy
import hashlib
import json
from pathlib import Path

from .common import EngineError

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1]/'templates/comic_v2/1.0.json'


def fail(message):
    raise EngineError('Layout settings: '+message)


def canonical_json(settings):
    validate(settings)
    return (json.dumps(settings,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')


def settings_sha256(settings):
    return hashlib.sha256(canonical_json(settings)).hexdigest()


def read_json(path):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: fail('duplicate key '+key)
            result[key]=value
        return result
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,
                          parse_constant=lambda value: fail('non-finite number'))
    except (ValueError,UnicodeError) as error:
        fail('invalid JSON: '+type(error).__name__)


def merge_known(base, override, path=''):
    if not isinstance(override,dict): fail(path+' must be an object')
    result=copy.deepcopy(base)
    for key,value in override.items():
        if key not in base: fail('unsupported key '+path+key)
        if isinstance(base[key],dict):
            result[key]=merge_known(base[key],value,path+key+'.')
        else:
            result[key]=copy.deepcopy(value)
    return result


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def point(value, width=512, height=384):
    return isinstance(value,list) and len(value)==2 and all(type(v) is int for v in value) and 2<=value[0]<width-2 and 2<=value[1]<height-2


def rect(value):
    return (isinstance(value,list) and len(value)==4 and all(type(v) is int for v in value)
            and 0<=value[0]<value[2]<=512 and 0<=value[1]<value[3]<=384)


def shape(value, schema, path=''):
    if isinstance(schema,dict):
        if not isinstance(value,dict) or set(value)!=set(schema): fail('missing/unsupported keys at '+path)
        for k in schema: shape(value[k],schema[k],path+k+'.')
    elif schema is None:
        if value is not None: fail('speaker tracking is not implemented')
    elif type(value) is not type(schema):
        fail('invalid type at '+path)


def validate(settings):
    # The bundled template defines the explicit key/type schema. Policy constants
    # below remain code-owned, so editing the JSON cannot enable future features.
    baseline=read_json(DEFAULT_TEMPLATE)
    expected_top={'schema_version','template_version','layout_version','mode','canvas','grid','artwork',
                  'dialogue','bubble','number','answer','notice','output','safety','features','panels'}
    if not isinstance(settings,dict) or set(settings)!=expected_top: fail('missing/unsupported top-level keys')
    if not isinstance(settings['panels'],dict) or set(settings['panels'])!={'1','2','3','4'}: fail('exactly four numbered panels required')
    panel_keys={'protected_regions','speaker','tail_direction','bubble','number_position'}
    for key,panel in settings['panels'].items():
        expected=panel_keys|({'answer_box','notice_box'} if key=='4' else set())
        if not isinstance(panel,dict) or set(panel)!=expected: fail('unsupported panel keys')
    shape(settings,baseline)
    fixed={
        'schema_version':1,'template_version':'1.0','layout_version':2,'mode':'settings_only',
        'canvas':{'width':512,'height':1536},
        'grid':{'columns':1,'rows':4,'panel_width':512,'panel_height':384},
        'artwork':{'max_width':508,'max_height':380,'fit':'contain'},
        'answer':{'measurement':'font_bbox','padding_x':12,'alignment':'center','minimum_font_size':28,'maximum_font_size':32},
        'notice':{'text':'AI가 제작한 이미지입니다','font_size':17},
        'safety':{'auto_approve':False,'on_collision':'needs_review'},
        'features':{'automatic_width_selection':False,'automatic_number_placement':False,'speaker_tracking':False,'directional_tails':False}}
    for k,v in fixed.items():
        if settings[k]!=v: fail('unsupported version/feature/policy at '+k)
    if settings['dialogue']!={'minimum_font_size':20,'maximum_font_size':23}: fail('unsupported dialogue font policy')
    bubble=settings['bubble']
    if bubble['padding_x']!=12 or bubble['padding_y']!=10: fail('unsupported bubble padding')
    if not bubble['width_candidates'] or not all(integer(w,48,508) for w in bubble['width_candidates']): fail('invalid width candidates')
    for points in (bubble['position_candidates'],settings['number']['position_candidates']):
        if not points or not all(point(p) for p in points): fail('invalid position candidates')
    if settings['number']['labels']!=list('①②③④'): fail('invalid panel labels')
    for p in settings['number']['position_candidates']:
        if p[0]+40>510 or p[1]+40>382: fail('number outside panel')
    output=settings['output']
    if (output['format']!='WEBP' or not integer(output['minimum_quality'],82,100)
            or not integer(output['target_min_bytes'],1,2**31) or not integer(output['target_max_bytes'],1,2**31)
            or output['target_min_bytes']>output['target_max_bytes'] or output['readability_first'] is not True): fail('invalid output policy')
    for key,panel in settings['panels'].items():
        if panel['tail_direction']!='fixed_down_left': fail('directional tails are not implemented')
        if not all(rect(box) for box in panel['protected_regions']): fail('invalid protected region')
        b=panel['bubble']
        if not integer(b['width'],48,508) or not b['candidates']: fail('invalid bubble width/candidates')
        if not all(point(p) and p[0]+b['width']<=510 and p[1]+30<=382 for p in b['candidates']): fail('bubble candidate outside panel')
        n=panel['number_position']
        if not point(n) or n[0]+40>510 or n[1]+40>382: fail('number outside panel')
        if key=='4':
            for name in ('answer_box','notice_box'):
                box=panel[name]
                if not rect(box) or box[0]<2 or box[2]>510 or box[1]<2 or box[3]>382: fail('invalid '+name)
            if panel['answer_box'][3]-panel['answer_box'][1]<36: fail('answer box too short')
            if panel['notice_box'][3]-panel['notice_box'][1]<25: fail('notice box too short')
    return settings


def load_template(path=DEFAULT_TEMPLATE):
    return validate(read_json(path))


def load_override(path):
    override=read_json(path)
    if not isinstance(override,dict) or set(override)-{'schema_version','template_version','id','panels'}: fail('invalid override keys')
    if type(override.get('schema_version')) is not int or override['schema_version']!=1 or override.get('template_version')!='1.0': fail('override version mismatch')
    if not isinstance(override.get('id'),str) or not override['id'].isdigit() or not 1<=int(override['id'])<=695 or str(int(override['id']))!=override['id']: fail('invalid idiom ID')
    if not isinstance(override.get('panels',{}),dict): fail('override panels must be an object')
    return override


def resolve_settings(template_path=DEFAULT_TEMPLATE, override_path=None):
    base=load_template(template_path)
    if override_path is not None:
        override=load_override(override_path)
        base=merge_known(base,{'panels':override.get('panels',{})})
    validate(base)
    # ID is carried separately: settings hashes represent layout content only.
    return {'id':override['id'] if override_path is not None else None,
            'settings':base,'sha256':settings_sha256(base)}


def require_render_support(settings):
    validate(settings)
    fail('schema-only configuration; renderer adapter is not implemented')
