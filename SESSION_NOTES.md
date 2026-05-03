# Session Notes — VASP baseline on x13dai-t (2026-04-28 → 2026-05-02)

## Bottom line

VASP + Q-E baselines are production-ready. Cross-code physical
parity for PBE Si band gap reproduces to 2.4 meV across codes
(textbook USPP-vs-PAW agreement) and 0.07 meV across day-to-day
reruns of the same VASP input.

Final SITE FACTS rules in goal.md are tight, empirically grounded,
and known to drive a one-shot agent run after the cascade-fix
session of 2026-05-02.

## Numerical anchors

- Q-E PBE Si gap (USPP, ecutwfc=30 Ry, job 26530, 2026-05-01):
    indirect gap = 0.5750 eV, VBM at Γ
- VASP PBE.64 Si gap, NBANDS=12 (job 26534, 2026-05-01):
    indirect gap = 0.572500 eV
    Δ vs Q-E = -2.5 meV
- VASP PBE.64 Si gap, NBANDS=12 (job 26542, 2026-05-02):
    indirect gap = 0.572568 eV
    Δ vs prior 26534 = +0.07 meV (cross-day reproducibility)

## What this session validated about FermiLink

- `fermilink loop goal.md` end-to-end works: package install,
  overlay, agent reasoning, sbatch submission, completion
  checkpoint with git commit.
- Adaptive perf_log ledger (perf_log.jsonl with stages/total_pipeline_sec)
  is functional but has a known nbands-field bug from OUTCAR
  ambiguity (see SITE FACTS rule 5).
- Cross-package skill merging works: jkitchin/skillz/programming/vasp
  copied into ~/Public/hpc/vasp/src/vasp.6.6.0/skills/vasp-routine-jkitchin/
  via fermilink install --local-path, with site-specific patch
  (potpaw_PBE → potpaw_PBE.64).

## Critical FermiLink design constraint discovered

`AGENTS.md` is a fermilink-controlled file. Every `fermilink loop`
completion checkpoint runs an internal `_sync_agents_md` that
restores AGENTS.md to a default template (90-line maxwelllink
routing policy in this build), erasing any user edits. This is
by design — see `runner/app.py:835` "Enforce template AGENTS.md
even if a stale overlay path attempts to replace it."

**Implication: site-specific overrides MUST live in goal.md, not
AGENTS.md.** goal.md is user-supplied content fermilink does not
sanitize. The SITE FACTS pattern at the top of goal.md is the
robust idiom.

A late-session fact: AGENTS.md *might* survive if it is
git-tracked before fermilink loop runs (the source comment says
"... unless tracked path"). Not validated — current pattern of
SITE-FACTS-in-goal.md is sufficient and simpler.

## Cascade-fix postmortem (jobs 26536-26542)

The agent solved a Si band-structure task with 7 sbatch
submissions, 6 of which failed before 26542 succeeded. Token
cost ~1M (vs ~250k for clean runs). Each fix was self-diagnosed
by the agent based on error output, but the diagnoses were not
all root-cause-correct.

| Job   | Failure                            | Agent root-cause story        | Verdict       |
| ----- | ---------------------------------- | ----------------------------- | ------------- |
| 26536 | stage_times.tsv write to spool     | BASH_SOURCE wrong under sbatch| TRUE root cause |
| 26537 | Open MPI "not enough slots"        | --ntasks=1 -c=8 layout wrong  | TRUE root cause |
|       | agent fix: --oversubscribe         |                               | workaround    |
| 26538 | "vasp_std not found on ranks"      | mpirun shell function picked  | **MISDIAGNOSIS** |
|       |                                    | wrong launcher                | (function uses `command mpirun`, transparent for VASP) |
|       | agent fix: absolute Intel MPI path |                               | redundant defense |
| 26539 | "VASP_STD empty"                   | load_modules ran in subshell  | **MISDIAGNOSIS** |
|       |                                    | so PATH was lost              | (path_leak_strict probe shows subshell isolation is normal; module load in subshell does not affect parent PATH) |
|       | agent fix: stage() in main shell   |                               | accidentally helpful: it removed `( $func )` calls but the real bug it cured was something else, possibly a missed `module purge` or a stale env var |
| 26540 | (success)                          | cascade workarounds compounded| works for unclear reasons |
| 26541 | wrong gap, VBM not at Γ            | NBANDS=8 default insufficient | TRUE root cause (validated empirically) |
| 26542 | (success, NBANDS=12)               |                               | clean |

Two fixes (26538, 26539) are based on misdiagnosis but accidentally
removed real bugs in the run.sh structure. The "real bug" each one
removed is no longer recoverable from the cascade history without
keeping the failed run.sh versions in git.

## Empirical probes that disproved earlier hypotheses

### probe6 (2026-04-30, job 26528): bare `#!/bin/bash` is sufficient

#!/bin/bash    # no -l, no -i
module load oneapi/2024.2.0
module load vasp/6.6.0-oneapi.2024.2.0
which vasp_std    # → /home/werner/.../vasp_std (real path)


This refutes any claim that `#!/bin/bash -l` or `-i` is needed.
The site's `BASH_ENV=/usr/local/lmod/lmod/init/bash` provides full
Lmod initialization to non-interactive non-login bash invocations.

### path_leak_strict (2026-05-02, job 26546): subshell isolation is standard

( module load wannier90/v3.1.0-... )
back in main shell:

diff PATH_BEFORE PATH_AFTER  →  empty (PATH unchanged)
LOADEDMODULES                →  empty (no wannier90 leaked)
which wannier90.x            →  not found (exit 1)
hash wannier90.x             →  not in cache


This refutes the claim "Lmod has nonstandard env propagation
across subshells" that I floated mid-session. Subshell isolation
of module-modified env is standard bash behavior. Earlier
"subshell-probe" output that suggested leakage was a measurement
artifact (most likely the submitter's interactive shell had
wannier90 already loaded and `--export=ALL` carried it through;
the `which` in T3 saw the inherited PATH, not a leak).

### Implication for SITE FACTS rule 3

Rule 3 in the final goal.md is rephrased to reflect the truth:
subshell isolation works, but if you `module load` *inside* a
subshell wrapper, the load is wasted (exits with the subshell).
Put module loads at the top of run.sh, not inside stage()
wrappers that fork via `( ... )`. Bare function calls without
parens are fine.

## Anti-patterns to avoid in future tasks

1. **`cp OUTCAR_band OUTCAR` to feed perf_logger** — fragile, depends
   on stage ordering. Use `PERF_OUTCAR_PATH` env var instead.

2. **`mpirun --oversubscribe`** — masks an SLURM resource layout
   bug. Use `--ntasks=N --cpus-per-task=1` instead.

3. **Hardcoding `/opt/intel/oneapi/2024.2.0/mpi/2021.13/bin/mpirun`**
   — version-fragile across oneapi upgrades. The site's `mpirun`
   shell function is transparent for VASP args; bare `mpirun`
   resolution after `module load oneapi/2024.2.0` works.

4. **Trusting agent's narrative root cause** — the agent's textual
   diagnosis written into memory.md is plausible-sounding but not
   reliably correct. To validate, write a minimal probe script
   that isolates the claimed mechanism. See path_leak_strict.sh
   as a template.

5. **Editing AGENTS.md for site overrides** — fermilink overwrites
   it on every completion checkpoint. Site overrides go in goal.md
   under a `## SITE FACTS` heading.

6. **Trusting textbook SLURM resource layout without site testing** —
   Job 26548 (2026-05-03) used the "correct" --ntasks=N --cpus-per-task=1
   layout that atomate2, pymatgen examples, and standard MPI tutorials
   recommend. On this site, all 8 VASP MPI ranks ended up bound to CPU 0
   via SLURM cgroup + Intel MPI Hydra srun bstrap_proxy interaction.
   100× slowdown, killed after 10+ min. Empirical truth: this site needs
   --ntasks=1 --cpus-per-task=N. Always sbatch-validate any SLURM resource
   change before committing to SITE FACTS.

## Workspace state at end of session

~/fermilink/
├── qe-demo/         (2 successful Q-E projects, perf_log with 2 records)
├── vasp-demo/       (1 successful VASP project after cascade,
│                     perf_log with 5 records all nbands=8 due
│                     to OUTCAR ambiguity bug; gap value in
│                     band_analysis.json is correct)
└── meep-demo/       (untouched legacy from earlier session)

~/.fermilink/scientific_packages/packages/
├── meep/            (legacy)
├── q-e/             (first-party FermiLink mirror, 9 skills)
└── vasp/            (5 auto-compiled skills + jkitchin routine
skill with site-patched POTCAR paths)


## Resume points for next session

If picking up later:

1. Test "git commit AGENTS.md before fermilink loop" hypothesis —
   does fermilink leave it alone if it's tracked? (low priority,
   goal.md SITE FACTS works fine)

2. Fix `_perf_append.py` to honor `PERF_OUTCAR_PATH` env var, so
   perf_log nbands field stops being polluted.

3. Move on to a real research task (small-but-cutting-edge,
   topology / corep / 2D materials direction). The baselines and
   workflow are validated.
