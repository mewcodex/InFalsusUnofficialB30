import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'docs'
api={'__file__':str(ROOT/'b30.py'),'__name__':'web_engine'}
exec(compile((ROOT/'engine/b30.py').read_text(encoding='utf-8'),'b30.py','exec'),api)
CAT={'songs':[{'id':i,'base_name':str(i),'title':str(i),'jacket':'unused',
    'charts':[{'difficulty':8,'level':12,'constant':12.0}]} for i in range(40)]}
def run(i,score,clear=2):
    return dict(base_name=str(i),difficulty=8,score=score,clear=clear,lamp=1 if clear==1 else 2,
                timestamp=0,history_index=0)
def calc(history):
    records=api['SaveRecords']()
    records.history=[dict(r,timestamp=i,history_index=i) for i,r in enumerate(history)]
    return api['recent_rating'](records,CAT)[0]
def total(history):return sum(r['rating'] for r in calc(history))

class RecentTests(unittest.TestCase):
    def test_unique_and_short_history(self):
        r=calc([run(0,99000000),run(0,98000000),run(1,95000000)])
        self.assertEqual(len(r),2)
        self.assertEqual(sum(x['rating'] for x in r),25.5)
    def test_ex_and_failed_protection(self):
        base=[run(i,99000000) for i in range(10)]+[run(0,99000000)]*20
        self.assertEqual(total(base+[run(0,98000000)]*40),total(base))
        self.assertEqual(total(base+[run(0,10000000,1)]*40),total(base))
        self.assertLess(total(base+[run(0,95000000)]*40),total(base))
    def test_new_best_evicts_weakest_not_oldest(self):
        base=[run(0,97000000)]+[run(i,94000000) for i in range(1,30)]
        after=calc(base+[run(1,96000000)])
        self.assertIn('0',[r['base_name'] for r in after])
        self.assertGreater(total(base+[run(1,96000000)]),total(base))
    def test_first_play_protection(self):
        base=[run(0,97000000)]+[run(i,94000000) for i in range(1,30)]
        self.assertEqual(total(base+[run(30,100)]),total(base))
    def test_ten_distinct_retained(self):
        base=[run(i,99000000) for i in range(10)]+[run(0,99000000)]*20
        self.assertEqual(len(calc(base+[run(0,95000000)]*60)),10)
    def test_no_history_fails_explicitly(self):
        with self.assertRaises(api['InputError']):api['recent_rating'](api['SaveRecords'](),CAT)
    def test_custom_constants(self):
        records=api['SaveRecords']();records.history=[dict(run(0,99000000),timestamp=1,history_index=0)]
        r,_=api['recent_rating'](records,CAT,{(str(i),8):13.0 for i in range(40)})
        self.assertEqual(r[0]['rating'],14.5)

if __name__=='__main__':unittest.main()
