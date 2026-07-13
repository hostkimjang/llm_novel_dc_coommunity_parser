from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools.build_launch_readiness_manifest import REQUIRED, REPLAY_REQUIRED, _sha, build_packet, read_packet
from tools.run_launch_packet_preflight import LaunchPacketPreflightError, preflight, read_preflight_receipt
from tools.run_launch_packet_actual_readback import LaunchPacketActualReadbackError, run as run_actual_readback
from tools.run_candidate_set_calibration_shadow_harness import write_actual_readback_bundle

class LaunchReadinessManifestTests(unittest.TestCase):
 def test_missing_inputs_are_not_ready_and_do_not_claim_runtime(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/"packet.json"; packet=build_packet(output=out,paths={},artifacts={},seed=1,replicates=2)
   self.assertEqual(packet["status"],"NOT_READY"); self.assertFalse(packet["runtime_started"]); self.assertEqual(len(packet["missing_required"]),len(REQUIRED))
 def test_complete_packet_is_only_preflight_ready(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); paths={}
   for n in REQUIRED:
    p=root/(n+".json"); p.write_text("{}",encoding="utf-8"); paths[n]=p
   arts={}
   for n in ("after_base_shadows","after_score_vectors","after_calibration_artifact","baseline_base_shadows","baseline_score_vectors","baseline_calibration_artifact"):
    p=root/(n+".json"); p.write_text("{}",encoding="utf-8"); arts[n]=p
   packet=build_packet(output=root/"packet.json",paths=paths,artifacts=arts,seed=1,replicates=2)
   self.assertEqual(packet["status"],"READY_FOR_NO_WRITE_PREFLIGHT"); self.assertFalse(packet["full_scan_approval"])
   self.assertEqual(read_packet(packet)["independent_readback"],"GO_LAUNCH_MANIFEST_BOUND")
 def test_manifest_rejects_artifact_name_gap_collision_and_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); paths={}
   for n in REQUIRED:
    p=root/(n+".json"); p.write_text("{}",encoding="utf-8"); paths[n]=p
   arts={}
   for n in ("after_base_shadows","after_score_vectors","after_calibration_artifact","baseline_base_shadows","baseline_score_vectors","baseline_calibration_artifact"):
    p=root/(n+".json"); p.write_text("{}",encoding="utf-8"); arts[n]=p
   incomplete=dict(arts); incomplete.pop("baseline_calibration_artifact")
   self.assertEqual(build_packet(output=root/"missing.json",paths=paths,artifacts=incomplete,seed=1,replicates=2)["status"],"NOT_READY")
   collision=dict(arts); collision["after_base_shadows"]=paths["p1_run_spec"]
   self.assertEqual(build_packet(output=root/"collision.json",paths=paths,artifacts=collision,seed=1,replicates=2)["status"],"NOT_READY")
   packet=build_packet(output=root/"packet.json",paths=paths,artifacts=arts,seed=1,replicates=2); packet["status"]="NOT_READY"
   with self.assertRaisesRegex(ValueError,"self-hash"):
    read_packet(packet)
 def test_rehashed_manifest_cannot_erase_required_or_replay_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); paths={}
   for n in REQUIRED:
    p=root/(n+".json"); p.write_text("{}",encoding="utf-8"); paths[n]=p
   arts={}
   for n in REPLAY_REQUIRED:
    p=root/(n+".json"); p.write_text("{}",encoding="utf-8"); arts[n]=p
   packet=build_packet(output=root/"packet.json",paths=paths,artifacts=arts,seed=1,replicates=2)
   packet["required_artifacts"]={}; packet["replay_artifacts"]={}; packet["missing_required"]=[]; packet["missing_replay_artifacts"]=[]; packet["path_collisions"]=[]; packet["status"]="READY_FOR_NO_WRITE_PREFLIGHT"
   packet["manifest_sha256"]=_sha({key:value for key,value in packet.items() if key!="manifest_sha256"})
   with self.assertRaisesRegex(ValueError,"readiness mismatch"):
    read_packet(packet)
 def test_independent_reader_cli_replays_not_ready_manifest(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); manifest=root/"packet.json"
   build_packet(output=manifest,paths={},artifacts={},seed=1,replicates=2)
   result=subprocess.run([sys.executable,"tools/read_launch_readiness_manifest.py","--manifest",str(manifest)],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,check=True)
   value=json.loads(result.stdout)
   self.assertEqual(value["status"],"NOT_READY")
   self.assertEqual(value["independent_readback"],"GO_LAUNCH_MANIFEST_BOUND")
 def test_reader_cli_returns_structured_no_go_for_invalid_manifest(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); manifest=root/"bad.json"; manifest.write_text("not-json",encoding="utf-8")
   result=subprocess.run([sys.executable,"tools/read_launch_readiness_manifest.py","--manifest",str(manifest)],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
   self.assertEqual(result.returncode,2)
   value=json.loads(result.stdout)
   self.assertEqual(value["gate"],"NO_GO_LAUNCH_MANIFEST_READBACK")
   self.assertFalse(value["runtime_started"]); self.assertFalse(value["writes_to_production"])
 def test_preflight_refuses_not_ready_before_engine_execution(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); manifest=root/"packet.json"
   build_packet(output=manifest,paths={},artifacts={},seed=1,replicates=2)
   with self.assertRaisesRegex(LaunchPacketPreflightError,"NOT_READY"):
    preflight(manifest_path=manifest,artifact_root=root)
   result=subprocess.run([sys.executable,"tools/run_launch_packet_preflight.py","--manifest",str(manifest),"--artifact-root",str(root)],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
   self.assertEqual(result.returncode,2)
   self.assertEqual(json.loads(result.stdout)["gate"],"NO_GO_LAUNCH_PACKET_PREFLIGHT")
 def test_actual_readback_refuses_not_ready_before_receipt_or_engine(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); manifest=root/"packet.json"; receipt=root/"receipt.json"; receipt.write_text("{}",encoding="utf-8")
   build_packet(output=manifest,paths={},artifacts={},seed=1,replicates=2)
   with self.assertRaisesRegex(LaunchPacketPreflightError,"NOT_READY"):
    run_actual_readback(manifest_path=manifest,preflight_receipt_path=receipt,artifact_root=root,output_dir=root/"readback")
   result=subprocess.run([sys.executable,"tools/run_launch_packet_actual_readback.py","--manifest",str(manifest),"--preflight-receipt",str(receipt),"--artifact-root",str(root),"--output-dir",str(root/"readback")],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
   self.assertEqual(result.returncode,2)
   self.assertEqual(json.loads(result.stdout)["gate"],"NO_GO_LAUNCH_PACKET_ACTUAL_READBACK")
 def test_preflight_rejects_ready_packet_outside_declared_artifact_root(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); paths={}; artifacts={}
   for name in REQUIRED:
    path=root/(name+".json"); path.write_text("{}",encoding="utf-8"); paths[name]=path
   for name in REPLAY_REQUIRED:
    path=root/(name+".json"); path.write_text("{}",encoding="utf-8"); artifacts[name]=path
   manifest=root/"packet.json"; build_packet(output=manifest,paths=paths,artifacts=artifacts,seed=1,replicates=2)
   other=root/"other"; other.mkdir()
   with self.assertRaisesRegex(LaunchPacketPreflightError,"artifact-root"):
    preflight(manifest_path=manifest,artifact_root=other)
 def test_preflight_maps_only_verified_complete_packet_refs(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); paths={}; artifacts={}
   for name in REQUIRED:
    path=root/(name+".json"); path.write_text("{}",encoding="utf-8"); paths[name]=path
   for name in REPLAY_REQUIRED:
    path=root/(name+".json"); path.write_text("{}",encoding="utf-8"); artifacts[name]=path
   manifest=root/"packet.json"; build_packet(output=manifest,paths=paths,artifacts=artifacts,seed=7,replicates=11)
   expected={"mode":"READ_ONLY_NO_WRITE_NO_RUNTIME","writes_performed":False,"runtime_started":False,"actual_metrics":None,"semantic_quality":"REVIEW-LOCKED","full_scan_approval":False,"gate":"GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED"}
   with patch("tools.run_launch_packet_preflight.build_actual_preflight_report",return_value=expected) as build:
    receipt=preflight(manifest_path=manifest,artifact_root=root)
   self.assertEqual(receipt["preflight_report"],expected)
   self.assertEqual(receipt["gate"],expected["gate"])
   self.assertFalse(receipt["runtime_started"]); self.assertFalse(receipt["writes_to_production"])
   kwargs=build.call_args.kwargs
   self.assertEqual(kwargs["seed"],7); self.assertEqual(kwargs["replicates"],11)
   self.assertEqual(kwargs["p1_run_spec_json"],"p1_run_spec.json")
   self.assertEqual(kwargs["prediction_jsonl"],"after_prediction.json")
   self.assertEqual(kwargs["baseline_prediction_jsonl"],"before_prediction.json")
   self.assertEqual(kwargs["additional_artifacts"],[(name,name+".json") for name in sorted(REPLAY_REQUIRED)])
 def test_preflight_rejects_runtime_or_approval_claim_from_engine(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); paths={}; artifacts={}
   for name in REQUIRED:
    path=root/(name+".json"); path.write_text("{}",encoding="utf-8"); paths[name]=path
   for name in REPLAY_REQUIRED:
    path=root/(name+".json"); path.write_text("{}",encoding="utf-8"); artifacts[name]=path
   manifest=root/"packet.json"; build_packet(output=manifest,paths=paths,artifacts=artifacts,seed=1,replicates=2)
   unsafe={"mode":"READ_ONLY_NO_WRITE_NO_RUNTIME","writes_performed":False,"runtime_started":True,"actual_metrics":None,"semantic_quality":"REVIEW-LOCKED","full_scan_approval":False,"gate":"GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED"}
   with patch("tools.run_launch_packet_preflight.build_actual_preflight_report",return_value=unsafe):
    with self.assertRaisesRegex(LaunchPacketPreflightError,"safety boundary"):
     preflight(manifest_path=manifest,artifact_root=root)
 def test_preflight_detects_manifest_or_artifact_swap_during_engine_call(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); paths={}; artifacts={}
   for name in REQUIRED:
    path=root/(name+".json"); path.write_text("{}",encoding="utf-8"); paths[name]=path
   for name in REPLAY_REQUIRED:
    path=root/(name+".json"); path.write_text("{}",encoding="utf-8"); artifacts[name]=path
   manifest=root/"packet.json"; build_packet(output=manifest,paths=paths,artifacts=artifacts,seed=1,replicates=2)
   safe={"mode":"READ_ONLY_NO_WRITE_NO_RUNTIME","writes_performed":False,"runtime_started":False,"actual_metrics":None,"semantic_quality":"REVIEW-LOCKED","full_scan_approval":False,"gate":"GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED"}
   original_manifest=manifest.read_bytes()
   original_p1=paths["p1_run_spec"].read_bytes()
   for target in (manifest,paths["p1_run_spec"]):
    manifest.write_bytes(original_manifest); paths["p1_run_spec"].write_bytes(original_p1)
    def mutate(**kwargs):
     target.write_bytes(b"changed")
     return safe
    with patch("tools.run_launch_packet_preflight.build_actual_preflight_report",side_effect=mutate):
     with self.assertRaisesRegex(LaunchPacketPreflightError,"artifact-root"):
      preflight(manifest_path=manifest,artifact_root=root)
 def test_preflight_actual_reader_accepts_verified_absolute_manifest_refs_as_relative(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); relative={
    "p1_run_spec":"p1/run_spec.json","p1_comparison":"p1/comparison.json","label_ledger":"labels/ledger.json","policy":"policy/actual.json","split_manifest":"dataset/split.json","source_manifest":"dataset/source.json","expected_universe":"dataset/expected.jsonl","producer":"predictions/producer.jsonl","after_prediction":"predictions/after.jsonl","before_prediction":"predictions/before.jsonl"}
   paths={}
   for name,item in relative.items():
    path=root/item; path.parent.mkdir(parents=True,exist_ok=True); path.write_text("{}\n" if path.suffix==".jsonl" else "{}",encoding="utf-8"); paths[name]=path
   replay={}
   for name in REPLAY_REQUIRED:
    suffix=".jsonl" if name.endswith(("base_shadows","score_vectors")) else ".json"
    path=root/"replay"/(name+suffix); path.parent.mkdir(parents=True,exist_ok=True); path.write_text("{}\n" if suffix==".jsonl" else "{}",encoding="utf-8"); replay[name]=path
   manifest=root/"packet.json"; build_packet(output=manifest,paths=paths,artifacts=replay,seed=7,replicates=11)
   readiness={"ready_for_split_manifest":True,"gate":"GO_ACTUAL_DATASET_READY","counts":{"ready_rows":6,"source_rows":6},"manifest_sha256":"a"*64}
   actual_run_spec={"run_spec_sha256":"b"*64,"artifacts":{"source_payload::example-1":{"relative_path":"source/example-1.json","bytes":123,"sha256":"c"*64}}}
   with patch("tools.run_calibration_dataset_readiness.build_current_readiness",return_value=readiness), patch("tools.run_candidate_set_calibration_shadow_harness.build_bound_actual_readback_from_files",return_value=(root,actual_run_spec,readiness,{"manifest_sha256":"d"*64})):
    receipt=preflight(manifest_path=manifest,artifact_root=root)
   self.assertEqual(receipt["gate"],"GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED")
   self.assertEqual(receipt["preflight_report"]["artifacts"]["p1_run_spec"]["relative_path"],"p1/run_spec.json")
   self.assertFalse(receipt["runtime_started"]); self.assertFalse(receipt["writes_to_production"])
   with patch("tools.run_calibration_dataset_readiness.build_current_readiness",return_value=readiness), patch("tools.run_candidate_set_calibration_shadow_harness.build_bound_actual_readback_from_files",return_value=(root,actual_run_spec,readiness,{"manifest_sha256":"d"*64})):
    self.assertEqual(read_preflight_receipt(receipt)["independent_readback"],"GO_LAUNCH_PACKET_PREFLIGHT_RECEIPT_BOUND")
   receipt["gate"]="NO_GO_ACTUAL_PREFLIGHT"
   with self.assertRaisesRegex(LaunchPacketPreflightError,"self-hash"):
    read_preflight_receipt(receipt,verify_artifacts=False)
 def test_actual_readback_writer_requires_new_direct_child_of_artifact_root(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); nested=root/"nested"/"bundle"; outside=root.parent/(root.name+"-outside")/"bundle"
   with patch("tools.run_candidate_set_calibration_shadow_harness.validate_actual_evidence_run_spec"):
    for output in (nested,outside):
     with self.assertRaisesRegex(ValueError,"direct child"):
      write_actual_readback_bundle(artifact_root=root,output_dir=output,run_spec={},readiness={},manifest={})
 def test_actual_readback_writer_stages_then_renames_new_direct_child(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); output=root/"bundle"
   with patch("tools.run_candidate_set_calibration_shadow_harness.validate_actual_evidence_run_spec"), patch("tools.run_candidate_set_calibration_shadow_harness.validate_actual_readback_artifacts"), patch("tools.run_candidate_set_calibration_shadow_harness.render_actual_readback_markdown",return_value="# readback\n"):
    written=write_actual_readback_bundle(artifact_root=root,output_dir=output,run_spec={},readiness={},manifest={})
   self.assertEqual(written,output.resolve()); self.assertTrue((output/"report.md").is_file())
   self.assertFalse(list(root.glob(".actual-readback-staging-*")))
 def test_actual_readback_writer_does_not_cleanup_swapped_staging_target(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); outside=root.parent/(root.name+"-outside"); outside.mkdir(); sentinel=outside/"keep.txt"; sentinel.write_text("keep",encoding="utf-8")
   token="a"*32; staging=root/(".actual-readback-staging-"+token); backup=root/"moved-staging"
   def swap_then_fail(*_args,**_kwargs):
    staging.rename(backup)
    try:
     staging.symlink_to(outside,target_is_directory=True)
    except OSError as exc:
     self.skipTest(f"symlink creation unavailable: {exc}")
    raise RuntimeError("simulated staging swap")
   with patch("tools.run_candidate_set_calibration_shadow_harness.secrets.token_hex",return_value=token), patch("tools.run_candidate_set_calibration_shadow_harness.validate_actual_evidence_run_spec"), patch("tools.run_candidate_set_calibration_shadow_harness.validate_actual_readback_artifacts",side_effect=swap_then_fail), patch("tools.run_candidate_set_calibration_shadow_harness.render_actual_readback_markdown",return_value="# readback\n"):
    with self.assertRaisesRegex(RuntimeError,"staging swap"):
     write_actual_readback_bundle(artifact_root=root,output_dir=root/"bundle",run_spec={},readiness={},manifest={})
   self.assertEqual(sentinel.read_text(encoding="utf-8"),"keep")
