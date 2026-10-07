"""Localization changes presentation, never scoring, timing or review identity."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from output_language import ROOT, resolve_language, localize, text
from template_pack import bundle, build_stats_pages
from review_io import build, review_template
from serve_overlay import build_plan
from check_serve_overlay import record


class Checks(unittest.TestCase):
    def test_resolution(self):
        self.assertEqual(resolve_language('zh-CN', 'en', 'en'), 'zh-CN')
        self.assertEqual(resolve_language(None, 'en-US', 'zh-CN'), 'en')
        self.assertEqual(resolve_language(None, None, 'en'), 'en')
        self.assertEqual(resolve_language(), 'zh-CN')
        with self.assertRaises(ValueError): resolve_language('fr')
        with self.assertRaises(ValueError): text('未翻译的新标签', 'en')

    def test_all_components_and_authoritative_overrides(self):
        manifest=json.loads((ROOT/'examples/ui-manifest.json').read_text('utf8'))
        for name in manifest['components']:
            en=bundle(name,language='en');zh=bundle(name)
            self.assertNotRegex(json.dumps(en['properties'],ensure_ascii=False), '[\u3400-\u9fff]')
            self.assertEqual(en['code'],zh['code'])
            self.assertEqual(en['placement1080p'],zh['placement1080p'])
        self.assertEqual(bundle('scoreboard', {'nameA':'王','rule':'自定'}, 'en')['props']['nameA'],'王')

    def test_stats_keep_values_and_comparison(self):
        pages=json.loads((ROOT/'examples/stats-pages.json').read_text('utf8'))
        metrics={p:{row['key']:1 for page in pages for row in page['rows']} for p in ('A','B')}
        for m in metrics.values():
            m['terminalHands']={k:{'FH':1,'BH':0,'unknown':1,'other':1} for k in ('W','UE','FE')}
            m['ueMotionCounts']={'unknown':1}
        metrics['A']['netWon']={'numerator':0,'denominator':0}
        speed={p:{'fastestServeKphEstimate':120,'firstServeMeanKphEstimate':100,'secondServeMeanKphEstimate':None,'secondServeCount':0} for p in ('A','B')}
        diag={'rallyDistribution':{k:{'numerator':1,'denominator':3} for k in ('short','medium','long')}}
        original=copy.deepcopy(metrics)
        zh=build_stats_pages(metrics,speed,diag)
        en=build_stats_pages(metrics,speed,diag,'en')
        self.assertEqual(metrics,original)
        self.assertEqual([len(p['rows']) for p in en],[7,11,6,8,7])
        self.assertNotRegex(json.dumps(en,ensure_ascii=False),'[\u3400-\u9fff]')
        for a,b in zip([r for p in zh for r in p['rows']],[r for p in en for r in p['rows']]):
            for key in ('key','comparison','highlight','comparisonValues'): self.assertEqual(a[key],b[key])

    def test_serve_language_keeps_timing(self):
        for r in (record(doubleFaultConfirmedUs=13000000),record(eventType='let',letConfirmedUs=13000000),record(method='model_imputed',imputationBasis='synthetic')):
            zh=build_plan([r],30)[0];en=build_plan([r],30,'en')[0]
            self.assertNotRegex(json.dumps(en,ensure_ascii=False),'[\u3400-\u9fff]')
            for key in zh:
                if key not in ('qualifier','labelStates'):self.assertEqual(zh[key],en[key])
            self.assertEqual([(s['startFrame'],s['endFrame']) for s in zh['labelStates']],[(s['startFrame'],s['endFrame']) for s in en['labelStates']])

    def test_html_translates_shell_not_payload(self):
        self.assertNotRegex(review_template('en'),'[\u3400-\u9fff]')
        data=json.loads((ROOT/'examples/review-data.json').read_text('utf8'))
        data['rows'][0]['reason']='原始证据 </script><script>alert(1)</script>'
        data['outputLanguage']='en'
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'review.html';build(data,target)
            html=target.read_text('utf8')
        self.assertIn('lang="en"',html)
        self.assertIn('原始证据',html)
        self.assertNotIn('</script><script>alert(1)',html)
        self.assertIn("'tennis-review:'+DATA.source+':'+DATA.ledgerRevision",html)


if __name__=='__main__': unittest.main()
