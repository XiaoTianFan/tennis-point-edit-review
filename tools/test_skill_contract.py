import tempfile, unittest
from pathlib import Path
from check_skill_contract import check_rules, check_section_links


class ContractTests(unittest.TestCase):
    def test_each_relocated_obligation_is_required(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'entry.md').write_text('deliver review',encoding='utf8')
            (root/'protocol.md').write_text('preserve answers',encoding='utf8')
            rules=[{'id':'review','checks':[
                {'path':'entry.md','text':'deliver review'},
                {'path':'protocol.md','text':'preserve answers'}]}]
            self.assertEqual(check_rules(root,rules),[])
            (root/'protocol.md').write_text('changed',encoding='utf8')
            self.assertEqual(len(check_rules(root,rules)),1)
            self.assertEqual(len(check_rules(root,[{'id':'empty','checks':[]}])),1)

    def test_legacy_rule_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=root/'entry.md'; p.write_text('required',encoding='utf8')
            rules=[{'id':'original','path':'entry.md','text':'required'}]
            self.assertEqual(check_rules(root,rules),[])
            p.unlink()
            self.assertEqual(len(check_rules(root,rules)),1)

    def test_renamed_section_is_detected_with_file_still_present(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'entry.md').write_text('[精剪](ref.md#剪辑)\n[重复](ref.md#剪辑-1)',encoding='utf8')
            ref=root/'ref.md'
            ref.write_text('# 剪辑\n## 剪辑\n[本节](#剪辑)',encoding='utf8')
            self.assertEqual(check_section_links(root),[])
            ref.write_text('# 已改名\n[本节](#剪辑)',encoding='utf8')
            self.assertEqual(len(check_section_links(root)),3)


if __name__=='__main__':unittest.main()
