## SITE FACTS — read first, override any conflicting skill defaults

This site has the FULL VASP POTCAR collection at
`~/Public/hpc/vasp/pot/`, including all releases:
  potpaw_LDA, potpaw_LDA.52, potpaw_LDA.54, potpaw_LDA.64
  potpaw_PBE, potpaw_PBE.52, potpaw_PBE.54, potpaw_PBE.64
  potUSPP_LDA, potUSPP_GGA

ALWAYS use the .64 release (PBE_64 in pymatgen, the latest
VASP 5.4.4+ PAW dataset with SHA256 hashes and COPYR fields).
The unsuffixed potpaw_PBE/ is the outdated 2010 release that
VASP officially marks as "not supported".

Required POTCAR path:
    ~/Public/hpc/vasp/pot/potpaw_PBE.64/<E>/POTCAR
    e.g. ~/Public/hpc/vasp/pot/potpaw_PBE.64/Si/POTCAR

In run.sh use:
    export VASP_PP=~/Public/hpc/vasp/pot
    cat $VASP_PP/potpaw_PBE.64/Si/POTCAR > POTCAR

In generate_inputs.py:
    pp_root = os.environ.get("VASP_PP", "/home/werner/Public/hpc/vasp/pot")
    potcar_src = Path(pp_root) / "potpaw_PBE.64" / "Si" / "POTCAR"
DO NOT hardcode potpaw_PBE/ (without .64) anywhere.

VASP module:  vasp/6.6.0-oneapi.2024.2.0
              (load oneapi/2024.2.0 first)

Site shell behavior — informational only, NOT pitfalls:
- ~/.bashrc has nvm-style lazy module loaders. The mpirun symbol is
  a shell function that lazy-loads modules for special args (e.g.
  `vampire-parallel`), then falls through to `command mpirun "$@"`.
  For VASP args this is transparent.
- BASH_ENV=/usr/local/lmod/lmod/init/bash is set system-wide, so
  bare `#!/bin/bash` shebang gets full Lmod inside sbatch workers
  without needing -l or -i flags.
- ~/.bashrc applies ulimit fixes BEFORE the interactive-shell
  return guard, so the fixes take effect for subprocess shells too.
  But sbatch workers do NOT source ~/.bashrc unless `-l` shebang
  is used; defensive practice is to repeat the ulimit calls in
  the sbatch script (see template below).

Python interpreter for postprocessing:
    /home/werner/.pyenv/versions/datasci/bin/python

Cleanup convention: after summary.md is finalized, the agent must
mechanically grep this goal.md for any of:
    nscf bands wannier fat-band projwfc restart kpoints_opt
        wannier90 irvsp vasp2trace continuation hse hybrid
If matched: keep WAVECAR. If not matched: rm -f WAVECAR.
ALWAYS keep CHGCAR, OUTCAR, vasprun.xml, EIGENVAL.
Append to summary.md a line:
    cleanup_decision: <kept WAVECAR | pruned WAVECAR>

SLURM script rules (validated by direct probe; see SESSION_NOTES.md
for the empirical evidence and the cascade-fix postmortem):

1. sbatch spool context — Use ${SLURM_SUBMIT_DIR} for project root,
   NEVER ${BASH_SOURCE[0]} or $0 (those point to /var/spool/slurmd
   under sbatch). Validated by direct test (job 26536 cascade).

2. SLURM resource layout for VASP (pure MPI, no OpenMP in default
   oneapi build) — STRONGLY PREFER:
       #SBATCH --nodes=1
       #SBATCH --ntasks=N            ← MPI ranks (e.g. 8)
       #SBATCH --cpus-per-task=1     ← VASP default has no OpenMP
       mpirun -np "${SLURM_NTASKS}" vasp_std
   The alternative `--ntasks=1 --cpus-per-task=N` requires Open MPI
   `--oversubscribe` to bypass slot detection (job 26537 cascade).
   Default to `--ntasks=N --cpus-per-task=1`.

3. Module load in main shell, NOT in subshells —
   `module load X` inside `( ... )` works (subshell isolation is
   standard, validated by path_leak_strict probe), but its effect
   is lost on subshell exit. Put `module load` calls at the top
   of run.sh, not inside `stage() { ... }` wrappers if those use
   `( $func )` parentheses. Plain function calls (no parens) run
   in main shell and are fine.

4. NBANDS for non-SCF band runs — Default NBANDS = NELECT/2 + small
   buffer is just enough for occupied states. For band runs that
   need unoccupied bands (CBM), set NBANDS >= 1.5 × default
   explicitly (Si: NBANDS=12, not the default 8). Mechanism: with
   NBANDS=8 = exactly NELECT/2 in a 2-atom Si cell, BSVasprun's
   gap finder sees no unoccupied band above the highest occupied
   eigenvalue at each k-point and reports wrong VBM/CBM.

5. perf_logger OUTCAR ambiguity — When a project produces both
   OUTCAR_scf and OUTCAR_band, _perf_append.py picks one by mtime
   fallback, which is unreliable (mtime can tie at 1-second
   resolution). DO NOT rely on `cp OUTCAR_band OUTCAR` to
   disambiguate. Instead, set explicit env var before calling
   logger:
       export PERF_OUTCAR_PATH=OUTCAR_band   # or OUTCAR_scf
       python3 _perf_append.py
   Without this, perf_log nbands/encut fields may reflect SCF
   defaults instead of band-specific values.

6. perf_logger ordering in sbatch — Always run _perf_append.py
   AFTER all VASP stages complete (typically as the last stage
   inside postprocess), not interleaved with stage execution.
   In particular, run logger AFTER any cp/mv that determines
   which OUTCAR is in cwd at logger time.

Canonical run.sh skeleton matching all rules above:

    #!/bin/bash
    #SBATCH --job-name=...
    #SBATCH --partition=batch
    #SBATCH --nodes=1
    #SBATCH --ntasks=8
    #SBATCH --cpus-per-task=1
    #SBATCH --time=01:00:00
    #SBATCH --output=slurm-%j.out
    #SBATCH --error=slurm-%j.err

    set -euo pipefail
    ulimit -Sn "$(ulimit -Hn)" 2>/dev/null || true
    ulimit -s unlimited        2>/dev/null || true

    cd "${SLURM_SUBMIT_DIR}"
    export OMP_NUM_THREADS=1
    export VASP_PP=~/Public/hpc/vasp/pot
    export FL_SYSTEM_TAG="..."

    # rule 3: module load at top, in main shell scope
    module purge
    module load oneapi/2024.2.0
    module load vasp/6.6.0-oneapi.2024.2.0
    module list > module_list.txt 2>&1
    which vasp_std

    # ... computation stages ...

    # rule 5+6: explicit OUTCAR + logger at end
    export PERF_OUTCAR_PATH=OUTCAR_band
    python3 _perf_append.py > perf_append.log 2>&1 || true

---

# Goal: Si band structure with PBE using VASP (parity check vs Q-E)

Compute the electronic band structure of bulk silicon (diamond,
a=5.43 Å, 2 atoms / primitive cell) along L–Γ–X–W–K–Γ using
VASP 6.6.0 with PBE. This baseline mirrors the Q-E calculation
done in `~/fermilink/qe-demo/projects/2026-05-01-si-bands-qe/`
so results can be cross-validated.

System tag: `FL_SYSTEM_TAG=Si_diamond_PBE_band_vasp`

## What to compute
1. **SCF** (with `LCHARG=.TRUE.`): Γ-centered 8×8×8 k-mesh,
   ENCUT=400 eV, EDIFF=1e-6, ISMEAR=0 (Gaussian), SIGMA=0.05.
   Use `vasp_std`.
2. **Non-SCF band run** reading CHGCAR (ICHARG=11) along L–Γ–X–W–K–Γ
   with 36 points/segment, ISYM=0, NBANDS=12 (per SITE FACTS rule 4
   — default NBANDS=8 for Si shifts apparent VBM/CBM positions).
   Use pymatgen `HighSymmKpath` to generate KPOINTS_band; or vaspkit
   option 303 if pymatgen path not viable. Use `vasp_std`.
3. Parse vasprun_band.xml with pymatgen `BSVasprun`. Identify
   VBM (at Γ) and CBM (≈ 0.83·Γ→X). Report indirect gap.
4. Plot `bands.png` with matplotlib.

## Pseudopotential
Use Si standard PAW PBE.64: `$VASP_PP/potpaw_PBE.64/Si/POTCAR`.
Verify ENMAX with `grep ENMAX POTCAR`; ENCUT=400 eV should be
≥ 1.3 × ENMAX (Si .64 ENMAX ~245.345 eV → ENCUT 400 eV passes).

## Cross-validation anchors
Prior runs of the same physical system on this site:

  Q-E (USPP, ecutwfc=30 Ry, job 26530, 2026-05-01):
      indirect gap = 0.5750 eV
      VBM at Γ, CBM at fraction 0.866 along path

  VASP (PAW.64, NBANDS=12, job 26534, 2026-05-01):
      indirect gap = 0.572500 eV
      VBM at Γ, CBM at fraction 0.829 along Γ-X
      Δ vs Q-E = -2.5 meV  (textbook USPP-vs-PAW agreement)

Expected new VASP result:
- indirect gap should reproduce 0.5725 eV within ±0.001 eV
  (cross-day reproducibility on identical input was 0.07 meV
  in prior testing)
- band topology: VBM at Γ, indirect CBM on Γ-X segment near
  fraction 0.83
- if Δ vs Q-E > 5 meV → investigate ENCUT convergence, NBANDS,
  k-path density, smearing. Document in summary.md key result:.

## Success criteria
- SCF converges within 30 iterations to EDIFF=1e-6.
- Indirect gap reported and in [0.570, 0.575] eV (tighter than
  prior [0.5, 0.8] now that we have two confirmed prior runs).
- bands.png clean, gap visible.
- VBM at Γ, CBM on Γ-X segment.

## Deliverables (in `projects/<date>-si-bands-vasp/`)
- `INCAR_scf`, `INCAR_band`, `KPOINTS_scf`, `KPOINTS_band`,
  `POSCAR`, `POTCAR`
- `generate_inputs.py`, `postprocess_bands.py`
- `run.sh` (single sbatch chaining SCF then band, using `stage()`
  function defined in main shell scope per SITE FACTS rule 3,
  with PERF_OUTCAR_PATH set per rule 6)
- `OUTCAR_scf`, `OUTCAR_band`, `vasprun_scf.xml`,
  `vasprun_band.xml`, `EIGENVAL`
- `band_analysis.json` with VBM/CBM/gap/scf_iter/walltime
- `bands.png`
- `module_list.txt`, `stage_times.tsv`
- `summary.md` (standard format with cleanup_decision line)
- One new line in `~/fermilink/vasp-demo/perf_log.jsonl`
  (must show nbands=12 not 8 — verify after run; if logger
  recorded 8, see SITE FACTS rule 6 and fix PERF_OUTCAR_PATH)
- `_perf_append.py` symlink to `../../_perf_append.py`

## Resource hint
Si is tiny (2 atoms). Use:
    --nodes=1 --ntasks=8 --cpus-per-task=1
    KPAR=2, NCORE=4
Total wall < 5 minutes (prior runs: SCF ~2s, band ~5s,
total pipeline ~13s on 8 cores).

Before writing run.sh, read perf_log.jsonl. Prior records for
this system tag exist (job_id 26534, 26535, 26540, 26541, 26542);
the conservative choice is to reuse cpus=8, kpar=2, ncore=4.

## Why this task
Smoke test for the FermiLink + VASP setup on x13dai-t with the
merged skill set (jkitchin routine + auto-compiled source nav).
Verifies:
(a) `vasp-routine-jkitchin` skill correctly drives INCAR/KPOINTS
    preparation under SITE FACTS overrides.
(b) Site-specific overrides (POTCAR .64 path via $VASP_PP, module
    load pattern, all 7 SLURM gotchas) work.
(c) perf_log captures VASP-specific fields (KPAR, NCORE, ENCUT,
    scf_iter, NBANDS) without ambiguity from multi-OUTCAR runs.
(d) Cross-code parity: PBE Si gap matches Q-E baseline within
    expected USPP-vs-PAW tolerance (target Δ ~2.5 meV).
(e) Cross-day reproducibility: this run vs prior 26534 should
    agree to < 0.1 meV on identical input.
