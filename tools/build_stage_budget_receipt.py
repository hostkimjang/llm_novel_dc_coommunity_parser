from __future__ import annotations

"""Write a bound, shadow-only StageBudget receipt; never starts runtime."""

import argparse, json, os, uuid
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.llm_batch.stage_budget import ArtifactRef, StageBudgetBinding, build_shadow_stage_budget_receipt

def _atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("xb") as handle:
            handle.write(json.dumps(value,ensure_ascii=False,indent=2).encode()+b"\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp,path)
        fd=None
        try: fd=os.open(str(path.parent),os.O_RDONLY); os.fsync(fd)
        except OSError: pass
        finally:
            if fd is not None: os.close(fd)
    finally: tmp.unlink(missing_ok=True)

def build(*, output: Path, run_spec: Path, scope: Path, attempt: Path, ledger: Path, events_path: Path) -> dict:
    events=json.loads(events_path.read_text(encoding="utf-8"))
    if not isinstance(events,list): raise ValueError("events JSON must be a list")
    receipt=build_shadow_stage_budget_receipt(StageBudgetBinding(ArtifactRef.snapshot(run_spec),ArtifactRef.snapshot(scope),ArtifactRef.snapshot(attempt),ArtifactRef.snapshot(ledger)),events)
    _atomic_write(output,receipt)
    return receipt

def main()->int:
    p=argparse.ArgumentParser(description="Build shadow-only bound StageBudget receipt")
    for name in ("output","run-spec","scope","attempt","ledger","events"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args(); receipt=build(output=a.output,run_spec=a.run_spec,scope=a.scope,attempt=a.attempt,ledger=a.ledger,events_path=a.events)
    print(json.dumps({"gate":receipt["gate"],"runtime_started":False,"output":str(a.output),"snapshot_sha256":receipt["snapshot_sha256"]},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
