"""실제 임시 파일로 current A→B 전환·보존 상한·무효화 경계를 검증한다."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from llm_batch.monitor import run_index as CANDIDATE

def make(root,name,rid):
    output=root/name/'run'/'result.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps([{'post_id':1,'run_meta':{'run_id':rid},'title':name}]),encoding='utf-8')
    manifest=output.with_name('result_manifest.json')
    payload={'run_id':rid,'output_file':str(output),'publication_scope_id':'scope-'+name,'completed_count':1,'terminal_artifacts_finalized':True}
    manifest.write_text(json.dumps(payload),encoding='utf-8')
    return output,manifest,payload

class CurrentRetention(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.home=Path(self.temp.name);self.root=self.home/'out';self.root.mkdir()
        self.a,self.am,self.ap=make(self.root,'A','20261014_010000_100001')
        self.b,self.bm,self.bp=make(self.root,'B','20261014_020000_100002')
        self.index=CANDIDATE.RunIndex(ttl=3600,max_entries=0)
    def tearDown(self):self.temp.cleanup()
    def switch(self):
        first=self.index.records(self.root,current_output=self.a);key=next(iter(first))
        self.index.records(self.root,current_output=self.b)
        return key
    def test_candidate_retains_A_after_B_beyond_scan_budget(self):
        key=self.switch();record=self.index.resolve(key,self.root,current_output=self.b)
        self.assertIsNotNone(record);self.assertEqual(record.path,self.a)
        self.assertEqual(self.index.load_result(record.path,self.root)[0]['title'],'A')
        self.assertTrue(self.index.truncated);self.assertEqual(len(self.index._records),0)
    def test_retention_survives_discovery_ttl_refresh(self):
        key=self.switch();self.index._expires=0
        self.assertIsNotNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_recent_current_has_fixed_24_entry_bound(self):
        keys=[]
        for i in range(30):
            output,_,_=make(self.root,'n'+str(i),f'20261014_030000_{i:06d}')
            current=self.index.records(self.root,current_output=output)
            keys.append(next(k for k,r in current.items() if r.path==output))
        self.assertEqual(len(self.index._recent_current),24)
        current=self.index.records(self.root)
        self.assertEqual(len(current),24);self.assertEqual(set(current),set(keys[-24:]))
        self.assertIsNone(self.index.resolve(keys[0],self.root))
    def test_current_access_refreshes_recency_without_unbounded_duplicates(self):
        key=self.switch()
        for _ in range(6):self.index.records(self.root,current_output=self.a)
        self.assertEqual(len(self.index._recent_current),2)
        self.assertEqual(next(reversed(self.index._recent_current)),key)
    def test_run_id_reuse_invalidates_old_key(self):
        key=self.switch();self.ap['run_id']='20261014_040000_100004';self.am.write_text(json.dumps(self.ap),encoding='utf-8')
        self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
        current=self.index.records(self.root,current_output=self.a)
        self.assertNotIn(key,current);self.assertEqual(len(self.index._recent_current),2)
    def test_deleted_manifest_invalidates_every_lookup(self):
        key=self.switch();self.am.unlink();self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
        self.assertNotIn(key,self.index._recent_current)
    def test_malformed_manifest_invalidates_every_lookup(self):
        key=self.switch();self.am.write_text('{',encoding='utf-8')
        self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_foreign_manifest_output_cannot_reuse_A_key(self):
        key=self.switch();self.ap['output_file']=str(self.b);self.am.write_text(json.dumps(self.ap),encoding='utf-8')
        self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_invalid_run_id_is_not_retained(self):
        self.ap['run_id']='not-a-run';self.am.write_text(json.dumps(self.ap),encoding='utf-8')
        self.index.records(self.root,current_output=self.a)
        self.assertEqual(len(self.index._recent_current),0)
    def test_deleted_result_invalidates_every_lookup(self):
        key=self.switch();self.a.unlink();self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_result_replaced_by_non_array_invalidates_every_lookup(self):
        key=self.switch();self.a.write_text('{}',encoding='utf-8')
        self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_result_replaced_by_directory_invalidates_every_lookup(self):
        key=self.switch();self.a.unlink();self.a.mkdir()
        self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_latest_manifest_metadata_is_reloaded_not_cached(self):
        key=self.switch();self.ap['completed_count']=7;self.am.write_text(json.dumps(self.ap),encoding='utf-8')
        got=self.index.resolve(key,self.root,current_output=self.b)
        self.assertEqual(got.public['post_count'],7)
    def test_root_change_clears_recent_and_result_cache(self):
        key=self.switch();self.index.load_result(self.a,self.root)
        self.assertTrue(self.index._result_cache)
        other=self.home/'out2';other.mkdir();c,_,_=make(other,'C','20261014_050000_100005')
        self.index.records(other,current_output=c)
        self.assertEqual(len(self.index._recent_current),1);self.assertFalse(self.index._result_cache)
        self.assertIsNone(self.index.resolve(key,self.root))
        self.assertFalse(self.index._recent_current)
    def test_arbitrary_name_and_foreign_current_are_not_authorized(self):
        outside,_,_=make(self.home/'foreign','F','20261014_060000_100006')
        self.assertEqual(self.index.records(self.root,current_output=outside),{})
        self.assertIsNone(self.index.resolve('result.json',self.root,current_output=self.a))
        self.assertIsNone(self.index.resolve('run_'+'f'*32,self.root,current_output=self.b))
    def test_mocked_manifest_symlink_is_invalidated(self):
        key=self.switch();original=Path.is_symlink
        with patch.object(Path,'is_symlink',lambda p: p==self.am or original(p)):
            self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_mocked_parent_junction_is_invalidated(self):
        key=self.switch()
        if not hasattr(Path,'is_junction'):self.skipTest('Path.is_junction is not supported')
        original=Path.is_junction
        with patch.object(Path,'is_junction',lambda p: p==self.a.parent or original(p)):
            self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_actual_manifest_symlink_inside_root_is_not_retained(self):
        key=self.switch();target=self.root/'separate.json';target.write_text(json.dumps(self.ap),encoding='utf-8');self.am.unlink()
        try:self.am.symlink_to(target)
        except OSError as e:self.skipTest('OS symlink unavailable: '+str(e))
        self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_actual_result_symlink_outside_root_is_not_retained(self):
        key=self.switch();target=self.home/'outside.json';target.write_bytes(self.a.read_bytes());self.a.unlink()
        try:self.a.symlink_to(target)
        except OSError as e:self.skipTest('OS symlink unavailable: '+str(e))
        self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
    def test_initial_current_symlink_alias_is_not_added_to_retention(self):
        link=self.root/'alias.json'
        try:link.symlink_to(self.a)
        except OSError as e:self.skipTest('OS symlink unavailable: '+str(e))
        self.index.records(self.root,current_output=link)
        self.assertEqual(len(self.index._recent_current),0)
    def test_ttl_hit_does_not_rescan_tree_to_retain_previous_current(self):
        with patch.object(self.index,'_paths',wraps=self.index._paths) as scan:
            key=self.switch();self.assertIsNotNone(self.index.resolve(key,self.root,current_output=self.b))
        self.assertEqual(scan.call_count,1)
    def test_known_recent_key_avoids_full_scan_after_ttl_expiry(self):
        key=self.switch();self.index._expires=0
        with patch.object(self.index,'_paths',side_effect=AssertionError('known recent key must not scan')):
            record=self.index.resolve(key,self.root,current_output=self.b)
        self.assertIsNotNone(record);self.assertEqual(record.path,self.a)
    def test_changed_recent_manifest_fails_without_scan_fallback(self):
        key=self.switch();self.index._expires=0
        self.ap['run_id']='20261014_090000_100009';self.am.write_text(json.dumps(self.ap),encoding='utf-8')
        with patch.object(self.index,'_paths',side_effect=AssertionError('invalid retained key must fail closed')):
            self.assertIsNone(self.index.resolve(key,self.root,current_output=self.b))
        self.assertNotIn(key,self.index._recent_current)
    def test_unknown_key_keeps_existing_discovery_fallback(self):
        self.switch();self.index._expires=0
        with patch.object(self.index,'_paths',wraps=self.index._paths) as scan:
            self.assertIsNone(self.index.resolve('run_'+'e'*32,self.root,current_output=self.b))
        self.assertEqual(scan.call_count,1)

if __name__=='__main__':
    unittest.main()
