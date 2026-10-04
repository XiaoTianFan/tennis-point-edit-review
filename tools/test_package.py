import base64,hashlib,importlib.util,json,tempfile,unittest,zlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('transport',Path(__file__).with_name('package.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class PackageTests(unittest.TestCase):
    def test_distribution_excludes_development_records(self):
        files=m.read_package()
        archive=json.loads(files[m.ARCHIVE])['files']
        self.assertEqual(set(archive),set(files)-{m.ARCHIVE})
        for names in (files,archive):
            self.assertFalse(any('/history/' in name for name in names))
            self.assertTrue({'references/validation.md','references/reorganization-map.md',
                'references/reorganization-manifest.json','scripts/check_reorganization.py'}.isdisjoint(names))
        for name,content in files.items():
            if not name.endswith('.md'):continue
            for retired in ('历史验收','本轮检查版本','本轮host','本次旧项目','仓库调研报告','交接提示词','先前会话','本次七原因版'):
                self.assertNotIn(retired,content,name)
    def test_package_documentation_links_are_self_contained(self):
        import re
        files=m.read_package()
        root=m.SKILL.resolve()
        for name,content in files.items():
            if not name.endswith('.md'):continue
            for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',content):
                if re.match(r'\w+://',target) or target.startswith('#'):continue
                path=(root/name).parent/target.split('#')[0]
                self.assertTrue(path.resolve().is_relative_to(root),(name,target))
                self.assertTrue(path.exists(),(name,target))
    def test_v1_archive_import_remains_supported(self):
        values={'SKILL.md':'旧版中文','references/package-version.json':'{"version":"legacy"}'}
        archive={'version':'legacy','files':{k:{'text':v,'sha256':m.sha(v)} for k,v in values.items()}}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'old.json';p.write_text(json.dumps(archive),encoding='utf-8')
            loaded,_=m.load_snapshot(p)
        self.assertEqual(loaded['SKILL.md'],'旧版中文')
        self.assertEqual(json.loads(loaded[m.ARCHIVE])['schema'],'tennis-recovery/v2')
    def test_compressed_archive_roundtrip_and_tampering(self):
        text='中文 / café / alpha\n'*200
        files=m.with_archive({'SKILL.md':text,'references/package-version.json':'{"version":"test"}'})
        arc=json.loads(files[m.ARCHIVE]);record=arc['files']['SKILL.md']
        self.assertEqual(m._archive.archive_text(record),text)
        self.assertLess(len(record['data']),len(text.encode()))
        record['sha256']='0'*64
        with self.assertRaises(ValueError):m._archive.archive_text(record)
    def test_compressed_archive_rejects_bomb_and_trailing_payload(self):
        for payload in (zlib.compress(b'x'*1000001),zlib.compress(b'x')+b'junk'):
            record={'encoding':'zlib+base64','data':base64.b64encode(payload).decode(),'sha256':hashlib.sha256(b'x').hexdigest()}
            with self.assertRaises(ValueError):m._archive.archive_text(record)
    def fixture(self):
        return m.with_archive({'SKILL.md':'base','references/package-version.json':'{"version":"test"}','references/retained.md':'retained'})
    def write_fixture(self,root,files):
        for name,text in files.items():
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
    def test_import_preserves_local_only_file_and_updates_archive(self):
        base=self.fixture();local=dict(base,LICENSE='local license');incoming=m.with_archive(dict(base,**{'SKILL.md':'updated'}))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'skill';outside=Path(d)/'README.md';outside.write_text('outside',encoding='utf-8')
            self.write_fixture(root,local)
            m.apply_snapshot(root,incoming,m.plan_merge(local,incoming,m.fingerprints(base)))
            actual=m.read_package(root)
            self.assertEqual(actual['SKILL.md'],'updated');self.assertEqual(actual['LICENSE'],'local license')
            self.assertEqual(outside.read_text(),'outside')
            self.assertEqual(actual[m.ARCHIVE],m.with_archive(actual)[m.ARCHIVE])
    def test_delete_requires_flag_and_refusal_writes_nothing(self):
        base=self.fixture();incoming=dict(base);del incoming['references/retained.md'];incoming=m.with_archive(incoming)
        plan=m.plan_merge(base,incoming,m.fingerprints(base))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.write_fixture(root,base)
            with self.assertRaises(ValueError):m.apply_snapshot(root,incoming,plan)
            self.assertEqual(m.read_package(root),base)
            m.apply_snapshot(root,incoming,plan,allow_deletes=True)
            self.assertFalse((root/'references/retained.md').exists())
    def test_incoming_only_update(self):
        a={'SKILL.md':'base'};b={'SKILL.md':'new'}
        self.assertEqual(m.plan_merge(a,b,m.fingerprints(a))['write'],['SKILL.md'])
    def test_local_only_update_preserved(self):
        base={'SKILL.md':'base'};local={'SKILL.md':'local'}
        p=m.plan_merge(local,base,m.fingerprints(base))
        self.assertEqual(p['localOnlyChanges'],['SKILL.md']);self.assertEqual(p['write'],[])
    def test_conflicting_edit_refused(self):
        p=m.plan_merge({'SKILL.md':'local'},{'SKILL.md':'remote'},m.fingerprints({'SKILL.md':'base'}))
        self.assertEqual(p['conflicts'],['SKILL.md'])
    def test_no_baseline_does_not_overwrite(self):
        self.assertEqual(m.plan_merge({'SKILL.md':'one'},{'SKILL.md':'two'})['conflicts'],['SKILL.md'])
    def test_equal_edits_are_not_conflicts(self):
        self.assertFalse(m.plan_merge({'SKILL.md':'same'},{'SKILL.md':'same'},{'SKILL.md':'old'})['conflicts'])
    def test_removed_remote_and_changed_local_is_conflict(self):
        b={'SKILL.md':'x','references/a.md':'old'}
        p=m.plan_merge({'SKILL.md':'x','references/a.md':'edited'},{'SKILL.md':'x'},m.fingerprints(b))
        self.assertEqual(p['conflicts'],['references/a.md'])
    def test_path_escape_and_private_files_rejected(self):
        for p in ('../escape','/abs','C:/abs','references/../escape','references\\bad','README.md','.env'):
            with self.assertRaises(ValueError):m.safe_name(p)
    def test_corrupted_text_recovers_only_from_verified_archive(self):
        files={'SKILL.md':'example','references/package-version.json':'{"version":"test"}'}
        files=m.with_archive(files);files['SKILL.md']='examp\ufffd'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'export.json';p.write_text(json.dumps({'packageFiles':files}),encoding='utf-8')
            recovered,notes=m.load_snapshot(p)
        self.assertEqual(recovered['SKILL.md'],'example');self.assertEqual(notes,['SKILL.md'])
    def test_stale_archive_does_not_undo_valid_new_text(self):
        files=m.with_archive({'SKILL.md':'old','references/package-version.json':'{"version":"test"}'})
        files['SKILL.md']='intentional edit'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'export.json';p.write_text(json.dumps(files),encoding='utf-8')
            with self.assertRaises(ValueError):m.load_snapshot(p)
    def test_omitted_snapshot_file_refused(self):
        files=m.with_archive({'SKILL.md':'example','references/package-version.json':'{"version":"test"}'})
        del files['references/package-version.json']
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'export.json';p.write_text(json.dumps(files),encoding='utf-8')
            with self.assertRaises(ValueError):m.load_snapshot(p)
if __name__=='__main__':unittest.main()
