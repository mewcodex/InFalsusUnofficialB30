import unittest
import struct
from pathlib import Path
import b30

def packed_string(value, utf8=True):
    if utf8:
        encoded=value.encode('utf8')
        return struct.pack('<ii',~len(encoded),len(value.encode('utf-16le'))//2)+encoded
    encoded=value.encode('utf-16le')
    return struct.pack('<i',len(encoded)//2)+encoded

def fixture(rows, utf8=True, history=(), character=None):
    # Empty card + particle inventories with the verified MemoryPack headers.
    data=b'\x09\x03\x02'+struct.pack('<ii',0,0)+struct.pack('<ii',0,0)
    data+=b'\x02\x02'+struct.pack('<iii',0,0,-1)+b'\x04'+struct.pack('<i',len(rows))
    for name,sid,diff,score in rows:
        data+=b'\x03'+packed_string(name,utf8)+struct.pack('<HB',sid,diff)
        result=bytearray(96)
        struct.pack_into('<HBBB',result,0,sid,diff,2,2)
        struct.pack_into('<Q',result,80,score)
        data+=result
    data+=b'\x02'+struct.pack('<i',len(history))+b''.join(history)+struct.pack('<i',len(history))
    if character is not None:
        data+=b'\x02'+struct.pack('<iiq',0,0,0) # mappings + updateId
        data+=b'\x02\x02'+struct.pack('<iiq',0,0,0) # encounters
        data+=b'\x02'+struct.pack('<iq',0,0) # stories
        data+=bytes([17,character])
    return data

class Tests(unittest.TestCase):
    def test_rating_boundaries(self):
        self.assertEqual(b30.play_rating(12,100_002_000),14)
        self.assertEqual(b30.play_rating(12,100_000_000),14)
        self.assertEqual(b30.play_rating(12,99_000_000),13.5)
        self.assertEqual(b30.play_rating(12,98_000_000),13)
        self.assertAlmostEqual(b30.play_rating(12,97_999_999),13-1/3_000_000)
        self.assertEqual(b30.play_rating(12,95_000_000),12)
        self.assertEqual(b30.play_rating(1,0),0)

    def test_parser_both_string_encodings(self):
        for utf8 in (True,False):
            data=fixture([('alamode',2,4,99_100_321)],utf8)
            row=b30.parse_save(data)[0]
            self.assertEqual(row['score'],99_100_321)
            self.assertEqual(row['base_name'],'alamode')
            self.assertEqual(row['difficulty'],4)

    def test_empty_and_truncated(self):
        self.assertEqual(b30.parse_save(fixture([])),[])
        data=fixture([('alamode',2,4,99_100_321)])
        for n in range(len(data)):
            with self.assertRaises((b30.InputError,UnicodeError)):
                b30.parse_save(data[:n])

    def test_version_and_mismatched_key(self):
        data=fixture([('alamode',2,4,99_100_321)])
        with self.assertRaises(b30.InputError):b30.parse_save(b'\x08'+data[1:])
        bad=bytearray(data);bad[-105]=3
        with self.assertRaises(b30.InputError):b30.parse_save(bad)

    def test_rank_dedup_and_unknown(self):
        catalog=b30.load_catalog()
        rows=[dict(base_name='alamode',difficulty=4,score=s) for s in [95_000_000,99_000_000,98_000_000]]
        rows+=[dict(base_name='alamode',difficulty=8,score=95_000_000),dict(base_name='tutorialmin',difficulty=1,score=100_000_100)]
        ranked,skipped=b30.rank_records(rows,catalog)
        self.assertEqual(len(ranked),2)
        self.assertEqual(next(r['score'] for r in ranked if r['difficulty']==4),99_000_000)
        self.assertEqual(skipped,[('tutorialmin',1)])
        self.assertAlmostEqual(b30.b30_value(ranked),sum(r['rating'] for r in ranked)/30)

    def test_input_and_output_validation(self):
        with self.assertRaises(b30.InputError):b30.load_records('scores.csv')
        with self.assertRaises(b30.InputError):b30.validate_output('savestate_V3.sav')
        with self.assertRaises(b30.InputError):b30.validate_output('same.sav','same.sav','.sav')

    def test_assets_complete(self):
        c=b30.load_catalog()
        self.assertEqual(len(c['songs']),70)
        self.assertEqual(sum(len(s['charts']) for s in c['songs']),280)
        for s in c['songs']:
            self.assertTrue((b30.ASSETS/s['jacket']).is_file())
            for chart in s['charts']:self.assertEqual(chart['constant'],float(chart['level']))
        for bg in c['backgrounds']:self.assertTrue((b30.ASSETS/bg['file']).is_file())
        for char in b30.CHARACTERS:self.assertTrue((b30.ASSETS/'avatars'/f'{char.lower()}.png').is_file())

    def test_history_judgements_and_character(self):
        result=bytearray(96)
        struct.pack_into('<HBBB',result,0,2,4,2,2)
        struct.pack_into('<7H',result,10,0,3,5,6,100,34,1126)
        score=99_100_321
        struct.pack_into('<Q',result,80,score)
        rows=b30.parse_save(fixture([('alamode',2,4,score)],history=[result],character=2))
        self.assertEqual(rows.selected_character,'Ayame')
        self.assertEqual(rows[0]['judgements'],dict(exact=1260,shiny=1126,near=11,breaks=3))
        self.assertEqual(rows[0]['judgement_source'],'matching-history')
        # A different score must never borrow these judgement counts.
        rows=b30.parse_save(fixture([('alamode',2,4,score-1)],history=[result]))
        self.assertIsNone(rows[0]['judgements'])

class CustomConstantsTests(unittest.TestCase):
    def setUp(self):
        self.catalog=b30.load_catalog()
        self.template=b30.constants_template(self.catalog)

    def edited(self,value):
        import csv,io
        rows=list(csv.reader(io.StringIO(self.template)))
        rows[1][-1]=value
        stream=io.StringIO();csv.writer(stream).writerows(rows)
        return stream.getvalue()

    def test_template_roundtrip_and_defaults(self):
        import csv,io
        values=b30.parse_constants('\ufeff'+self.template,self.catalog)
        self.assertEqual(len(values),280)
        for song in self.catalog['songs']:
            for chart in song['charts']:
                self.assertEqual(values[song['base_name'],chart['difficulty']],float(chart['level']))
        rows=list(csv.reader(io.StringIO(self.template)))
        stream=io.StringIO();csv.writer(stream).writerows([rows[0],*reversed(rows[1:])])
        self.assertEqual(values,b30.parse_constants(stream.getvalue(),self.catalog))

    def test_precision_and_invalid_rows(self):
        for value in ('12.34','-1.0','NaN','inf','','1e1','=12.3'):
            with self.subTest(value=value),self.assertRaises(b30.InputError):b30.parse_constants(self.edited(value),self.catalog)
        self.assertIn(12.3,b30.parse_constants(self.edited('12.3'),self.catalog).values())
        self.assertIn(12.0,b30.parse_constants(self.edited('12'),self.catalog).values())
        rows=self.template.splitlines()
        for bad in ('\n'.join(rows[:-1]),self.template+rows[1]+'\n',self.template.replace('alamode0','unknown',1),self.template.replace(',MIN,',',ULT,',1)):
            with self.assertRaises(b30.InputError):b30.parse_constants(bad,self.catalog)

    def test_custom_constants_change_ranking_and_total(self):
        values=b30.parse_constants(self.template,self.catalog)
        rows=[dict(base_name='alamode',difficulty=d,score=100_000_000) for d in (1,8)]
        default,_=b30.rank_records(rows,self.catalog)
        unchanged,_=b30.rank_records(rows,self.catalog,values)
        self.assertEqual(default,unchanged)
        values['alamode',1]=19.9
        custom,_=b30.rank_records(rows,self.catalog,values)
        self.assertEqual(custom[0]['difficulty'],1)
        self.assertEqual(custom[0]['constant'],19.9)
        self.assertAlmostEqual(custom[0]['rating'],21.9)
        self.assertGreater(b30.b30_value(custom),b30.b30_value(default))

if __name__=='__main__':unittest.main()
