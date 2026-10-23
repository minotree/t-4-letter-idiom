"""Read-only golden checks for approved ID 1, independent of current defaults."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image
from comic_engine.common import ROOT

OUTPUT = 'd7db83fee675b6660660fb0a235e4d3826976a03b13f0cbd8c96df66c0ca0bfd'
EVIDENCE = {
    'input_sha256':'5168bc9a4dc4198cae3d9b005ea9a12742c127c42825d5fbd69ec68a0ad3492d',
    'layout_sha256':'36a4a212cd4c3741a6d76af5c0c1f49381a42362ea7df681c5c75eeebeb0de9a',
    'packet_sha256':'7bddd41b2fa36b777cf0d57fde84912fe8802d273cd0eeba030fdfa688fa84df',
    'report_sha256':'3cd5344185b82727e1ec551099e93d8855d8cd0baef163b746899618c82627b9',
    'output_sha256':OUTPUT, 'layout_version':2, 'render_revision':3,
}
FILENAME = '0001_가가호호.webp'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document(path):
    return json.loads(path.read_text(encoding='utf-8'))


def canonical(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')


class ID1PreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = ROOT/'data/manual_workflow'
        cls.image = ROOT/'assets/idioms'/FILENAME
        cls.preview = ROOT/'assets/previews/0001_layout_v2_centered.webp'
        cls.approval = cls.workspace/'approvals_v2/0001'/(OUTPUT+'.json')
        cls.protected = [p for folder in ('data','assets') for p in (ROOT/folder).rglob('*') if p.is_file()]
        cls.before = {p:digest(p) for p in cls.protected}

    @classmethod
    def tearDownClass(cls):
        after = {p:digest(p) for folder in ('data','assets') for p in (ROOT/folder).rglob('*') if p.is_file()}
        if cls.before != after:
            raise AssertionError('Preservation tests modified production assets/data')

    def test_final_hash_and_preview_link(self):
        self.assertEqual(digest(self.image),OUTPUT)
        self.assertEqual(digest(self.preview),OUTPUT)

    def test_final_webp_decode_read_only(self):
        with Image.open(self.image) as im:
            self.assertEqual(im.format,'WEBP')
            self.assertEqual(im.size,(512,1536))
            self.assertEqual(im.n_frames,1)
            im.load()

    def test_csv_bom_schema_count_and_id1(self):
        raw = (ROOT/'data/sajaseongeo_final_quiz_v3.csv').read_bytes()
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True))
        self.assertEqual(rows[0],['hanja','reading','image_filename'])
        self.assertEqual(len(rows)-1,695)
        self.assertTrue(all(len(row)==3 for row in rows[1:]))
        self.assertEqual(rows[1],['家家戶戶','가가호호',FILENAME])
        self.assertTrue((ROOT/'assets/idioms'/rows[1][2]).is_file())

    def test_both_manifests_approved(self):
        for path in (self.workspace/'image_manifest.csv',ROOT/'data/image_manifest.csv'):
            with self.subTest(path=path):
                rows=list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'),newline='')))
                row=rows[0]
                self.assertEqual(len(rows),695)
                self.assertEqual([r['id'] for r in rows],[str(i) for i in range(1,696)])
                self.assertEqual([row[k] for k in ('hanja','reading','filename','status','review_status')],
                                 ['家家戶戶','가가호호',FILENAME,'completed','approved'])

    def check_archived_evidence(self):
        approval=document(self.approval)
        self.assertEqual(approval,{'id':'1','reviewer':'사용자','reviewed_on':'2026-10-21',
                                   'workflow':'manual-v2','evidence':EVIDENCE})
        report_path=self.preview.with_suffix('.json')
        self.assertEqual(digest(report_path),EVIDENCE['report_sha256'])
        report=document(report_path)
        for key in ('input_sha256','layout_sha256','packet_sha256','output_sha256','layout_version','render_revision'):
            self.assertEqual(report[key],EVIDENCE[key])
        self.assertEqual(digest(ROOT/'assets/imports/0001.png'),EVIDENCE['input_sha256'])
        settings=document(ROOT/'tools/image-generator/layouts/0001_v2.json')
        self.assertEqual(hashlib.sha256(canonical(settings)).hexdigest(),EVIDENCE['layout_sha256'])
        packet=self.workspace/'prompts/0001'/EVIDENCE['packet_sha256']/'production.json'
        self.assertEqual(digest(packet),EVIDENCE['packet_sha256'])
        self.assertEqual(document(packet)['hanja'],'家家戶戶')
        self.assertEqual(report['dimensions'],[512,1536])
        answer=[e for e in report['overlays'] if e['role']=='answer']
        self.assertEqual([e['text'] for e in answer],['家家戶戶'])
        self.assertGreaterEqual(answer[0]['font_size'],28)

    def test_approval_evidence_chain_is_frozen(self):
        self.check_archived_evidence()

    def test_new_renderer_defaults_cannot_redefine_archived_baseline(self):
        # Simulate a future renderer without invoking its compose/approve functions.
        # Archived verification uses pinned versions/hashes, never current globals.
        with patch('comic_engine.layout_v2.VERSION',999), patch('comic_engine.layout_v2.RENDER_REVISION',999):
            self.check_archived_evidence()
            self.assertEqual(digest(self.image),OUTPUT)

    def test_id1_transaction_committed_and_linked(self):
        transaction=document(self.workspace/'v2_approval_transaction.json')
        self.assertEqual(transaction['id'],'1')
        self.assertEqual(transaction['state'],'committed')
        self.assertEqual(transaction['evidence'],EVIDENCE)
        self.assertEqual(len(transaction['files']),3)
        # Check ID 1 fields, not whole CSV/manifest hashes: later IDs may be approved.
        for entry in transaction['files']:
            content=base64.b64decode(entry['after'],validate=True).decode('utf-8-sig')
            rows=list(csv.DictReader(io.StringIO(content,newline='')))
            self.assertEqual(rows[0]['hanja'],'家家戶戶')
            if 'image_filename' in rows[0]:
                self.assertEqual(rows[0]['image_filename'],FILENAME)
            else:
                self.assertEqual((rows[0]['status'],rows[0]['review_status']),('completed','approved'))
