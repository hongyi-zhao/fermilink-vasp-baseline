# FermiLink Unified Memory

- schema_version: 1
- started_at_utc: 2026-05-01T02:36:16.103963Z
- last_updated_utc: 2026-05-01T02:51:50Z
- prompt_source: /home/werner/fermilink/vasp-demo/goal.md

## Original request
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

## Short-Term Memory (Operational)

### Plan
- [x] Inspect VASP package skills, QE comparator, modules, pseudopotential path, and prior perf log.
- [x] Create `projects/2026-05-01-si-bands-vasp/` and generate SCF/band inputs plus helper scripts.
- [x] Review generated VASP inputs against package guidance and requested settings.
- [x] Submit the single-node SLURM chain job and record the job id.
- [x] Monitor job completion and collect SCF/band artifacts.
- [x] Postprocess band structure, create `band_analysis.json` and `bands.png`.
- [x] Cross-validate VASP gap/topology against the QE baseline and acceptance window.
- [x] Append VASP perf log entry and finalize `summary.md`.
- [x] Update persistent memory with file map, parameter provenance, uncertainties, and results.

### Progress log
- initialized
- 2026-05-01T02:46:18Z: Prepared `projects/2026-05-01-si-bands-vasp/` with VASP SCF/band inputs, generator, postprocessor, SLURM chain script, copied Si POTCAR, and `_perf_append.py` symlink.
- 2026-05-01T02:51:50Z: Completed SLURM job `26534`, generated `band_analysis.json` and `bands.png`, appended VASP perf log, and finalized `summary.md`.

## Long-Term Memory (Persistent)

### File map
- (path | purpose | notes)
- `projects/2026-05-01-si-bands-vasp/generate_inputs.py` | generates Si diamond POSCAR, INCAR/KPOINTS files, copies Si PAW PBE POTCAR, and creates `_perf_append.py` symlink | uses direct FCC `L-G-X-W-K-G` line-mode path with 36 points/segment.
- `projects/2026-05-01-si-bands-vasp/run.sh` | single-node SLURM chain for prepare, SCF, band, postprocess, and perf append | job profile: `batch`, `--nodes=1 --ntasks=1 --cpus-per-task=8`, `oneapi/2024.2.0`, `vasp/6.6.0-oneapi.2024.2.0`.
- `projects/2026-05-01-si-bands-vasp/postprocess_bands.py` | parses `vasprun_band.xml` with pymatgen `BSVasprun` when available and direct `EIGENVAL`, writes `band_analysis.json` and `bands.png` | records VBM/CBM path locations and QE comparison.

### Simulation history
- (run_id | objective | status | artifacts | notes)
- `2026-05-01-si-bands-vasp` | VASP PBE Si diamond band parity check vs QE baseline | done, SLURM job `26534` exit `0:0` | `OUTCAR_scf`, `OUTCAR_band`, `vasprun_scf.xml`, `vasprun_band.xml`, `EIGENVAL`, `band_analysis.json`, `bands.png`, `stage_times.tsv`, `module_list.txt` | earlier jobs `26532` and `26533` exposed script environment issues before final clean rerun.

### Key results
- (result_id | metric | value | conditions | evidence_path)
- `2026-05-01-si-bands-vasp-gap` | indirect gap | `0.572503 eV` | VASP 6.6.0 PBE, Si standard PAW PBE, `ENCUT=400 eV`, Gamma-centered `8x8x8` SCF, line-mode `L-G-X-W-K-G` band path | `projects/2026-05-01-si-bands-vasp/band_analysis.json`
- `2026-05-01-si-bands-vasp-topology` | VBM/CBM location | VBM at Gamma; CBM on Gamma-X at fraction `0.828571`; QE gap delta `0.002497 eV` | direct EIGENVAL parser and pymatgen `BSVasprun` agree | `projects/2026-05-01-si-bands-vasp/band_analysis.json`
- `2026-05-01-si-bands-vasp-scf` | SCF convergence | 13 electronic iterations, within 30-iteration criterion | final clean job `26534`; `EDIFF=1e-6` reached | `projects/2026-05-01-si-bands-vasp/OUTCAR_scf`

### Parameter source mapping
- (run_id | parameter_or_setting | value | source | evidence_path | notes)
- `2026-05-01-si-bands-vasp` | lattice and basis | diamond Si primitive, `a=5.43 Angstrom`, 2 atoms | original request | `projects/2026-05-01-si-bands-vasp/POSCAR` | fixed input, no relaxation.
- `2026-05-01-si-bands-vasp` | VASP SCF settings | `ENCUT=400`, `EDIFF=1E-6`, `ISMEAR=0`, `SIGMA=0.05`, `LCHARG=.TRUE.`, Gamma `8x8x8` | original request plus VASP electronic-structure skill guidance | `projects/2026-05-01-si-bands-vasp/INCAR_scf`, `projects/2026-05-01-si-bands-vasp/KPOINTS_scf` | `ENCUT/ENMAX=1.630357`.
- `2026-05-01-si-bands-vasp` | band settings | `ICHARG=11`, `NBANDS=12`, 36 points/segment `L-G-X-W-K-G` | original request; direct FCC path fallback because pymatgen import was initially absent in interactive Python before job environment | `projects/2026-05-01-si-bands-vasp/INCAR_band`, `projects/2026-05-01-si-bands-vasp/KPOINTS_band` | final postprocess did have pymatgen available and used `BSVasprun`.
- `2026-05-01-si-bands-vasp` | pseudopotential | Si standard PAW PBE POTCAR, `ENMAX=245.345 eV` | `/home/werner/Public/hpc/vasp/pot/potpaw_PBE/Si/POTCAR` | `projects/2026-05-01-si-bands-vasp/POTCAR`, `projects/2026-05-01-si-bands-vasp/potcar_enmax.txt` | `$VASP_PP` was not set by module in interactive shell, so run script defaults it to `/home/werner/Public/hpc/vasp/pot`.
- `2026-05-01-si-bands-vasp` | performance settings | `--cpus-per-task=8`, `KPAR=2`, `NCORE=4` | original resource hint; no previous VASP perf log existed | `projects/2026-05-01-si-bands-vasp/run.sh`, `/home/werner/fermilink/vasp-demo/perf_log.jsonl` | perf log appended job `26534`.

### Simulation uncertainty
- (run_id | uncertainty_or_assumption | impact | mitigation_or_next_step | status)
- `2026-05-01-si-bands-vasp` | initial interactive Python lacked pymatgen, so the generated path used explicit FCC coordinates rather than `HighSymmKpath` | low; path is the standard FCC `L-G-X-W-K-G` path and final job environment had pymatgen for `BSVasprun` parsing | if future workflows require generated paths for lower-symmetry structures, pin the same Python env at generation time or use vaspkit 303 | closed for this cubic Si case.
- `2026-05-01-si-bands-vasp` | VASP module did not export `$VASP_PP` in interactive shell | run would fail to find POTCAR if relying only on `$VASP_PP` | `run.sh` sets default `VASP_PP=/home/werner/Public/hpc/vasp/pot` and generator allows `VASP_SI_POTCAR` override | mitigated.
- `2026-05-01-si-bands-vasp` | first job `26532` failed because `module` startup hit `nvm: unbound variable` under `set -u`; job `26533` failed postprocess due Python without matplotlib after module purge | could cause false failed jobs despite valid VASP inputs | final `run.sh` disables nounset during module calls and pins `/home/werner/.pyenv/versions/datasci/bin/python` for Python stages | fixed in final job `26534`.

### Suggested skills updates
- (<package_id> | issue_pattern | proposed_skill_update | evidence | status)
- `vasp` | site VASP module may not set `$VASP_PP` and `module purge/load` can interact badly with `set -u`/nvm | document a site-safe `run.sh` template: start with ulimit commands, use `set -eo pipefail`, wrap module calls with `set +u` then restore `set -u`, default `VASP_PP=/home/werner/Public/hpc/vasp/pot`, and pin a known Python with plotting/pymatgen for postprocessing | jobs `26532`, `26533`, final fixed job `26534` in `projects/2026-05-01-si-bands-vasp/` | proposed
- `vasp` | perf append should record SCF metrics in chained SCF+band workflows | before calling `_perf_append.py`, restore `INCAR_scf` to `INCAR` and `OUTCAR_scf` to `OUTCAR`; otherwise helper may read the final band OUTCAR | `projects/2026-05-01-si-bands-vasp/run.sh` | proposed
