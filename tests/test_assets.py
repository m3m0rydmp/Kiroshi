import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from dashboard.server import App


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(self.temp.name)

    def tearDown(self):
        self.app.shutdown()
        self.app.db.close()
        self.temp.cleanup()

    def asset(self, key, value, engagement='one', tool='urlfinder', status=None):
        record = dict(id=key, value=value, engagement_id=engagement, tool=tool, updated='2026-10-16', job_ids=['historical-run'], detail={'status_code':status, 'header':{'private':'large-evidence-marker'}})
        self.app.put('asset', record)
        return record

    def test_pagination_is_stable_bounded_and_does_not_load_evidence(self):
        originals = [self.asset(str(i).zfill(3), 'https://example.test/path/' + str(i)) for i in range(121)]
        first = self.app.asset_page(dict(limit=50))
        second = self.app.asset_page(dict(limit=50, page=2))
        self.assertEqual((first['total'], first['pages']), (121, 3))
        self.assertEqual(len(first['items']), 50)
        self.assertFalse(set(a['id'] for a in first['items']) & set(a['id'] for a in second['items']))
        self.assertNotIn('large-evidence-marker', json.dumps(first))
        self.assertEqual(self.app.get('asset', originals[0]['id']), originals[0])
        self.assertEqual(self.app.asset_page(dict(page=999))['page'], 3)
        for params in ({'limit':201}, {'page':0}, {'type':'anything'}, {'sort':'updated; DROP TABLE records'}):
            with self.assertRaises(ValueError):
                self.app.asset_page(params)

    def test_host_type_source_status_and_engagement_filters(self):
        self.asset('host', 'example.test', tool='subfinder')
        self.asset('ip', '::1', tool='dnsx')
        self.asset('url', 'https://example.test/a', tool='httpx', status=301)
        self.asset('other', 'https://other.test/a', engagement='two', status=200)
        for filters, expected in (({'host':'EXAMPLE.test'},2), ({'type':'ip'},1), ({'tool':'httpx'},1), ({'status':'3xx'},1), ({'engagement_id':'two'},1), ({'engagement_id':'one','type':'url','status':'3xx'},1)):
            self.assertEqual(self.app.asset_page(filters)['total'], expected)
        self.assertEqual(self.app.asset_page({'type':'ip'})['items'][0]['host'], '::1')
        self.assertEqual(self.app.asset_page({'engagement_id':'one'})['facets']['types'], {'host':1,'ip':1,'url':1})

    def test_search_is_global_not_current_page_and_wildcards_are_literal(self):
        for i in range(60):
            self.asset(str(i).zfill(3), 'https://example.test/' + ('needle%_value' if i==59 else str(i)))
        result = self.app.asset_page(dict(q='needle%_value', limit=25))
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['id'], '059')
        self.assertEqual(self.app.asset_page(dict(q="' OR 1=1 --"))['total'], 0)

    def test_updates_keep_index_in_sync_without_modifying_raw_evidence(self):
        record = self.asset('same','https://example.test/a',tool='urlfinder')
        record.update(tool='httpx', detail={'status_code':200},job_ids=['old','new'])
        self.app.put('asset',record)
        result = self.app.asset_page({'tool':'httpx'})
        self.assertEqual((result['total'],result['items'][0]['job_count'],result['items'][0]['status']), (1,2,200))
        self.assertEqual(self.app.asset_page({'tool':'urlfinder'})['total'],0)
        overview = self.app.asset_overview()
        self.assertEqual(overview['by_engagement'],{'one':1})

    def test_imported_records_are_backfilled_once_and_summary_stays_small(self):
        with self.app.lock:
            self.app.db.executemany('INSERT INTO records VALUES (?,?,?)', [('asset',str(i),json.dumps(dict(id=str(i),engagement_id='import',value='https://example.test/'+str(i),detail={'body':'x'*1000}))) for i in range(1001)])
            self.app.db.commit()
        overview = self.app.asset_overview()
        self.assertEqual(overview['total'],1001)
        self.assertEqual(len(overview['preview']),10)
        self.assertLess(len(json.dumps(overview)),10000)
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM asset_index').fetchone()[0],1001)
        self.assertEqual(self.app.asset_page({'page':2})['total'],1001)

    def test_host_sort_keeps_same_host_adjacent(self):
        self.asset('1','https://z.example.test/a')
        self.asset('2','https://a.example.test/z')
        self.asset('3','https://a.example.test/a')
        self.assertEqual([a['id'] for a in self.app.asset_page({'sort':'host'})['items']],['3','2','1'])


if __name__ == '__main__':
    unittest.main()
