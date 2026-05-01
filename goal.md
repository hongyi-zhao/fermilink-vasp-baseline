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
   with ~30-40 points/segment. Use pymatgen `HighSymmKpath` to
   generate KPOINTS_band; or vaspkit option 303 if pymatgen path
   not viable. Use `vasp_std`.
3. Parse vasprun.xml or EIGENVAL with pymatgen `BSVasprun`. Identify
   VBM (at Γ) and CBM (≈ 0.85·Γ→X). Report indirect gap.
4. Plot `bands.png` with matplotlib.

## Pseudopotential
Use Si standard PAW PBE: `$VASP_PP/potpaw_PBE/Si/POTCAR`.
Verify ENMAX with `grep ENMAX POTCAR`; ENCUT=400 eV should be
≥ 1.3 × ENMAX (Si standard ENMAX ~245 eV).

## Cross-validation against Q-E baseline
The Q-E run on the same system (PBE, 2-atom Si diamond, similar
k-mesh) gave:
- indirect gap = 0.575 eV (USPP, ecutwfc=30 Ry)
- VBM at Γ, CBM near 0.85·Γ→X

Expected VASP result:
- indirect gap should be in [0.5, 0.8] eV (PBE band gaps are
  USPP/PAW-implementation-dependent at ~50 meV level)
- band topology (VBM at Γ, indirect CBM along Γ-X) must match Q-E

If VASP gap differs from Q-E gap by > 0.1 eV, investigate:
ENCUT convergence, k-mesh density, smearing scheme, PAW vs USPP
difference. Document in summary.md `key result:`.

## Success criteria
- SCF converges within 30 iterations to EDIFF=1e-6.
- Indirect gap reported and in [0.5, 0.8] eV.
- bands.png clean, gap visible.
- VBM/CBM locations match Q-E (qualitative).

## Deliverables (in `projects/<date>-si-bands-vasp/`)
- `INCAR_scf`, `INCAR_band`, `KPOINTS_scf`, `KPOINTS_band`,
  `POSCAR`, `POTCAR`
- `generate_inputs.py`, `postprocess_bands.py`
- `run.sh` (single sbatch chaining SCF then band, using `stage()`
  function for per-stage timing)
- `OUTCAR_scf`, `OUTCAR_band`, `vasprun_scf.xml`,
  `vasprun_band.xml`, `EIGENVAL`
- `band_analysis.json` with VBM/CBM/gap/scf_iter/walltime
- `bands.png`
- `module_list.txt`, `stage_times.tsv`
- `summary.md` (standard format)
- One new line in `~/fermilink/vasp-demo/perf_log.jsonl`
- `_perf_append.py` symlink to `../../_perf_append.py`

## Resource hint
Si is tiny (2 atoms). Start with `--cpus-per-task=8`, KPAR=2, NCORE=4.
Total wall < 5 minutes. Before writing run.sh, read perf_log.jsonl
(if non-empty) and prefer best-performing prior config for similar
systems.

## Why this task
First VASP smoke test on x13dai-t with the merged skill set
(jkitchin routine + auto-compiled source navigation). Verifies:
(a) `vasp-routine-jkitchin` skill correctly drives a real
    INCAR/KPOINTS preparation.
(b) Site-specific overrides (POTCAR path via $VASP_PP, module load
    pattern, sbatch site rules) work.
(c) perf_log mechanism captures VASP-specific fields (KPAR, NCORE,
    ENCUT, scf_iter).
(d) Cross-code parity: PBE Si gap matches Q-E baseline within
    expected USPP-vs-PAW tolerance.
After this passes, next quest is FeTaSe2 HSE+SOC reproduction.
