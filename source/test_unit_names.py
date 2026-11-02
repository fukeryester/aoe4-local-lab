import json,tempfile,unittest
from pathlib import Path
from unit_names import NameStore,checked,import_csv,export_csv

class NameConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'unit_names.json';self.store=NameStore(self.path)
    def test_exact_blueprint_matching_and_restart(self):
        self.store.observe(['unit_scout_1_lan','unit_scout_1_tem','unit_scout_2_lan'])
        self.store.save({'unit_scout_1_lan':{'custom_name':'我的侦察骑兵','notes':'仅此文明等级'}})
        loaded=NameStore(self.path)
        self.assertEqual(loaded.display('unit_scout_1_lan'),'我的侦察骑兵')
        self.assertEqual(loaded.display('unit_scout_1_tem'),'侦察兵')
        self.assertEqual(loaded.display('unit_scout_2_lan'),'侦察兵')
    def test_clearing_override_restores_default(self):
        self.store.save({'unit_scout_1_lan':{'custom_name':'骑兵'}})
        self.store.save({'unit_scout_1_lan':{'custom_name':''}})
        self.assertEqual(NameStore(self.path).display('unit_scout_1_lan'),'侦察兵')
    def test_discovery_preserves_existing_custom_names(self):
        self.store.save({'unit_archer_1_eng':{'custom_name':'英格兰弓箭手','notes':'自定义'}})
        other=NameStore(self.path)
        self.store.save({'unit_archer_1_eng':{'custom_name':'长弓兵','notes':'已修正'}})
        other.observe(['unit_villager_1_eng']);other.save()
        self.assertEqual(other.display('unit_archer_1_eng'),'长弓兵')
        self.assertIn('unit_villager_1_eng',other.rows)
    def test_stale_editor_cannot_overwrite_another_edit(self):
        self.store.save({'unit_scout_1_lan':{'custom_name':'名称A'}})
        before=dict(self.store.rows)
        other=NameStore(self.path);other.save({'unit_scout_1_lan':{'custom_name':'名称B'}})
        with self.assertRaises(ValueError):self.store.save({'unit_scout_1_lan':{'custom_name':'名称C'}},expected=before)
        self.assertEqual(NameStore(self.path).display('unit_scout_1_lan'),'名称B')
    def test_bad_file_is_preserved(self):
        raw=b'{invalid';self.path.write_bytes(raw);s=NameStore(self.path)
        self.assertTrue(s.error);s.observe(['unit_scout_1_lan'])
        with self.assertRaises(ValueError):s.save()
        self.assertEqual(self.path.read_bytes(),raw)
    def test_csv_chinese_and_quotes_round_trip(self):
        rows={'unit_archer_1_eng':{'custom_name':'弓箭手,精锐','notes':'备注 "第二级"'},
              'unit_scout_1_lan':{'custom_name':'','notes':''}}
        path=self.path.with_suffix('.csv');export_csv(path,rows)
        self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'));self.assertEqual(import_csv(path),rows)
    def test_import_rejects_duplicates_and_malformed_columns(self):
        path=self.path.with_suffix('.csv')
        for text in ['蓝图名称,自定义名称\na,甲\na,乙\n',
                     '蓝图名称,自定义名称\na,甲,多余\n',
                     '蓝图名称,自定义名称\na\n',
                     '蓝图名称,默认名称\na,甲\n']:
            path.write_text(text,encoding='utf-8-sig')
            with self.assertRaises(ValueError):import_csv(path)
    def test_csv_import_merges_without_deleting_other_units(self):
        self.store.save({'unit_archer_1_eng':{'custom_name':'弓手'},'unit_scout_1_lan':{'custom_name':'侦骑'}})
        path=self.path.with_suffix('.csv');path.write_text('蓝图名称,自定义名称\nunit_scout_1_lan,\n',encoding='utf-8-sig')
        self.store.save(import_csv(path))
        self.assertEqual(self.store.display('unit_archer_1_eng'),'弓手');self.assertEqual(self.store.display('unit_scout_1_lan'),'侦察兵')
    def test_control_characters_and_long_labels_rejected(self):
        for name in ['A\nB','A\tB','x'*121]:
            with self.assertRaises(ValueError):checked('unit_test',name)

if __name__=='__main__':unittest.main(verbosity=2)
