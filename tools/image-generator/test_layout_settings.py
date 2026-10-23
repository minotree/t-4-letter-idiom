"""Settings-only fixtures; no production overrides, images or approvals."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from comic_engine.common import EngineError
from comic_engine.layout_settings import (load_template, load_override, resolve_settings,
    merge_known, validate, canonical_json, settings_sha256, require_render_support)


class LayoutSettingsTests(unittest.TestCase):
    def test_common_template_load(self):
        settings=load_template()
        self.assertEqual(settings['canvas'],{'width':512,'height':1536})
        self.assertEqual(settings['mode'],'settings_only')
        self.assertFalse(settings['safety']['auto_approve'])

    def test_partial_nested_merge_and_list_replacement(self):
        base=load_template(); original=copy.deepcopy(base)
        merged=merge_known(base,{'panels':{'2':{'bubble':{'width':240},'protected_regions':[[1,1,50,80]]}}})
        validate(merged)
        self.assertEqual(merged['panels']['2']['bubble']['candidates'],base['panels']['2']['bubble']['candidates'])
        self.assertEqual(merged['panels']['1'],base['panels']['1'])
        self.assertEqual(merged['panels']['2']['protected_regions'],[[1,1,50,80]])
        self.assertEqual(base,original)

    def test_override_file_is_only_temporary_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'0002.json'
            path.write_text(json.dumps({'schema_version':1,'template_version':'1.0','id':'2',
                'panels':{'2':{'bubble':{'width':240}}}}),encoding='utf-8')
            self.assertEqual(load_override(path)['id'],'2')
            result=resolve_settings(override_path=path)
            self.assertEqual(result['id'],'2')
            self.assertEqual(result['settings']['panels']['2']['bubble']['width'],240)
            self.assertEqual(result['sha256'],resolve_settings(override_path=path)['sha256'])

    def test_unknown_keys_and_missing_fields_block(self):
        for override in ({'bad':1},{'panels':{'5':{}}},{'panels':{'1':{'bubble':{'bad':3}}}}):
            with self.subTest(override=override),self.assertRaises(EngineError):
                merge_known(load_template(),override)
        settings=load_template(); del settings['answer']
        with self.assertRaises(EngineError): validate(settings)

    def test_invalid_coordinates_and_ranges_block(self):
        for change in ({'protected_regions':[[0,0,513,30]]},
                       {'protected_regions':[[20,20,10,30]]},
                       {'bubble':{'width':400,'candidates':[[240,12]]}},
                       {'number_position':[500,370]}, {'protected_regions':[[False,0,10,10]]}):
            with self.subTest(change=change),self.assertRaises(EngineError):
                validate(merge_known(load_template(),{'panels':{'1':change}}))

    def test_version_and_types_block(self):
        for key,value in [('schema_version',True),('schema_version',2),('template_version','2.0'),('layout_version',3)]:
            settings=load_template(); settings[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(EngineError): validate(settings)

    def test_unsupported_features_and_render_use_block(self):
        for change in ({'speaker':'child'}, {'tail_direction':'right'}):
            with self.subTest(change=change),self.assertRaises(EngineError):
                validate(merge_known(load_template(),{'panels':{'1':change}}))
        settings=load_template(); settings['features']['automatic_width_selection']=True
        with self.assertRaises(EngineError): validate(settings)
        with self.assertRaisesRegex(EngineError,'adapter'):
            require_render_support(load_template())

    def test_deterministic_serialization_and_hash(self):
        settings=load_template()
        reordered=dict(reversed(list(settings.items())))
        self.assertEqual(canonical_json(settings),canonical_json(reordered))
        self.assertEqual(settings_sha256(settings),settings_sha256(reordered))
        merged=merge_known(settings,{'panels':{'1':{'bubble':{'width':240}}}})
        self.assertNotEqual(settings_sha256(settings),settings_sha256(merged))

    def test_duplicate_json_keys_and_bad_override_version(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'override.json'
            for text in ('{"id":"2","id":"3"}',
                         '{"schema_version":1,"template_version":"2.0","id":"2"}',
                         '{"schema_version":1,"template_version":"1.0","id":"02"}'):
                p.write_text(text,encoding='utf-8')
                with self.assertRaises(EngineError):load_override(p)
