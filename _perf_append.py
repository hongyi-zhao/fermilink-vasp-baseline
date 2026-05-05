#!/usr/bin/env python3
"""Append a VASP perf record to ~/fermilink/vasp-demo/perf_log.jsonl.

Reads OUTCAR for SCF metrics + INCAR for keywords (KPAR/NCORE/ENCUT).
Use PERF_OUTCAR_PATH, PERF_INCAR_PATH, and PERF_STAGES_PATH to route
canonical subdirectory artifacts without root-level compatibility links.
Reads stage_times.tsv (if present) for per-stage real wall times.
"""
import json, os, re, datetime, sys
from pathlib import Path

cwd = Path.cwd()

def resolve_configured_path(env_name, default_name=None, *, fallback_glob=None, required=False):
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        path = cwd / env_value
        if not path.exists():
            print(f"[perf] {env_name}={env_value} but file not found in {cwd}", file=sys.stderr)
            sys.exit(0)
        return path
    if default_name is not None:
        path = cwd / default_name
        if path.exists():
            return path
    if fallback_glob:
        cands = sorted(cwd.glob(fallback_glob), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands:
            return cands[0]
    if required:
        label = default_name or env_name
        print(f"[perf] no {label} found", file=sys.stderr)
        sys.exit(0)
    return None

# ---- find OUTCAR ----
# Priority: PERF_OUTCAR_PATH env var (per goal.md SITE FACTS rule 5)
#   > cwd/OUTCAR (default)
#   > most recent OUTCAR* by mtime (fallback)
outcar = resolve_configured_path("PERF_OUTCAR_PATH", "OUTCAR", fallback_glob="OUTCAR*", required=True)
otxt = outcar.read_text(errors="ignore")

# ---- read INCAR for parallelization keys ----
incar = resolve_configured_path("PERF_INCAR_PATH", "INCAR")
itxt = incar.read_text(errors="ignore") if incar else ""

def grep(text, pat, default=None, cast=str):
    m = re.search(pat, text)
    if not m: return default
    try: return cast(m.group(1))
    except Exception: return default

def grep_incar(key, default=None, cast=int):
    return grep(itxt, rf"(?im)^\s*{key}\s*=\s*(\S+)", default, cast)

# OUTCAR-derived
natoms       = grep(otxt, r"NIONS\s*=\s*(\d+)", 0, int)
nbands       = grep(otxt, r"NBANDS\s*=\s*(\d+)", 0, int)
nkpts_irr    = grep(otxt, r"NKPTS\s*=\s*(\d+)", 0, int)
encut_ev     = grep(otxt, r"ENCUT\s*=\s*([\d.]+)", None, float)
total_cpu    = grep(otxt, r"Total CPU time used \(sec\):\s*([\d.]+)", None, float)
elapsed_real = grep(otxt, r"Elapsed time \(sec\):\s*([\d.]+)", None, float)
# count SCF iterations
scf_iter = len(re.findall(r"^-+ Iteration\s+\d+\(\s*\d+\)", otxt, re.M)) or None

# INCAR-derived
kpar  = grep_incar("KPAR", 1, int)
ncore = grep_incar("NCORE", 1, int)

# ---- stage_times.tsv ----
stage_real = {}
stages_path = resolve_configured_path("PERF_STAGES_PATH", "stage_times.tsv")
if stages_path and stages_path.exists():
    for line in stages_path.read_text().strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            name, start, end, status = parts[0], parts[1], parts[2], parts[3]
            try:
                elapsed = float(end) - float(start)
                stage_real[name] = {
                    "elapsed_sec": round(elapsed, 3),
                    "exit": int(status),
                }
            except Exception:
                pass
total_pipeline_sec = round(sum(s["elapsed_sec"] for s in stage_real.values()), 3) or None

rec = {
    "job_id":             os.environ.get("SLURM_JOB_ID", ""),
    "system":             os.environ.get("FL_SYSTEM_TAG", "unknown"),
    "natoms":             natoms,
    "nkpts_irr":          nkpts_irr,
    "nbands":             nbands,
    "encut_ev":           encut_ev,
    "cpus":               int(os.environ.get("SLURM_CPUS_PER_TASK", 0)),
    "kpar":               kpar,
    "ncore":              ncore,
    "scf_iter":           scf_iter,
    "total_cpu_sec":      total_cpu,
    "elapsed_real_sec":   elapsed_real,
    "stages":             stage_real or None,
    "total_pipeline_sec": total_pipeline_sec,
    "ts":                 datetime.datetime.now().isoformat(timespec="seconds"),
    "outcar":             None,
    "project":            cwd.name,
}
try:
    rec["outcar"] = str(outcar.relative_to(cwd))
except ValueError:
    rec["outcar"] = str(outcar)

log = Path.home() / "fermilink/vasp-demo/perf_log.jsonl"
log.parent.mkdir(parents=True, exist_ok=True)
with log.open("a") as f:
    f.write(json.dumps(rec) + "\n")
print(f"[perf] {rec['system']} cpus={rec['cpus']} kpar={kpar} ncore={ncore} elapsed={elapsed_real}s")
