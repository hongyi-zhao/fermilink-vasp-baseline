# FermiLink Unified Memory

- schema_version: 1
- started_at_utc: 2026-05-02T09:08:18.602360Z
- last_updated_utc: 2026-05-02T09:43:44Z
- prompt_source: /home/werner/fermilink/vasp-demo/goal.md

## Original request
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

Site shell quirk: ~/.bashrc has nvm with unbound vars; sbatch
must wrap module load with set +u ... set -u.

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
- [x] Read project memory, package docs/skills, perf log, and site prerequisites.
- [x] Generate `projects/2026-05-02-si-bands-vasp/` inputs and helper scripts using PBE `.64` Si POTCAR.
- [x] Review generated INCAR/KPOINTS/POTCAR/run script against requested settings and site SLURM rules.
- [x] Submit the single-node SLURM run chaining prepare, SCF, band, and postprocess stages.
- [x] Monitor SLURM completion and inspect logs/stage timings.
- [x] Validate parsed band gap, VBM/CBM locations, SCF iterations, and plot artifact.
- [x] Finalize `summary.md`, cleanup WAVECAR according to `goal.md`, and record perf/memory results.
- [x] Verify deliverables are present and close the loop.
- [x] Re-checked the current `python` interpreter in `/home/werner/fermilink/vasp-demo`.

### Progress log
- initialized
- 2026-05-02T09:10:31Z: Preflight checked empty `skills/`, README, existing perf log, SLURM commands, module availability, `.64` Si POTCAR ENMAX, and datasci Python imports; no project files created yet.
- 2026-05-02T09:17:44Z: Created and reviewed `projects/2026-05-02-si-bands-vasp/` generator, postprocessor, SLURM script, POSCAR, INCARs, KPOINTS, POTCAR, and initial summary; no job submitted yet.
- 2026-05-02T09:20:19Z: Submitted job `26536`, observed immediate failure because `run.sh` used `BASH_SOURCE[0]` under `sbatch` spool context, then patched it to prefer `SLURM_SUBMIT_DIR` before resubmission.
- 2026-05-02T09:22:46Z: Submitted job `26537`; module and prepare stages succeeded, SCF failed because Open MPI saw one SLURM slot under `--ntasks=1 --cpus-per-task=8`; patched `mpirun --oversubscribe -np ${SLURM_CPUS_PER_TASK}`.
- 2026-05-02T09:27:06Z: Submitted job `26538`; SCF still failed because the wrong MPI launcher could not resolve `vasp_std`; patched `run.sh` to call absolute Intel MPI `/opt/intel/oneapi/2024.2.0/mpi/2021.13/bin/mpirun` and absolute `vasp_std`.
- 2026-05-02T09:29:33Z: Submitted job `26539`; SCF failed because module/path variables set inside a subshell stage were lost; patched `stage()` to preserve environment and added explicit command-failure returns.
- 2026-05-02T09:36:52Z: Completed job `26540` but the result missed physics targets (`gap=0.2517 eV`, VBM off-Gamma) because the band run used default `NBANDS=8` and the lightweight postprocess path was inadequate; regenerated inputs with `NBANDS=12`, direct `EIGENVAL` analysis, and submitted corrected job `26541`.
- 2026-05-02T09:43:44Z: Job `26541` met physics acceptance (`gap=0.572568 eV`, VBM at Gamma, CBM at 0.828571 along G-X); reran once as `26542` with `LWAVE=True` to keep a non-empty `WAVECAR`, refreshed `band_analysis.json`, appended perf logging, and finalized `summary.md`.
- 2026-05-05T08:28:18Z: Re-checked `python` in `cwd=/home/werner/fermilink/vasp-demo`; `bash -ic 'which python'` resolved to `/home/werner/.pyenv/versions/datasci/bin/python`. Touched `projects/memory.md`.

## Long-Term Memory (Persistent)

### File map
- (path | purpose | notes)
- projects/2026-05-02-si-bands-vasp/generate_inputs.py | reproducible input generator | writes primitive 2-atom Si POSCAR, 8x8x8 Gamma KPOINTS, L-G-X-W-K-G line-mode KPOINTS, INCARs, and `.64` Si POTCAR.
- projects/2026-05-02-si-bands-vasp/run.sh | single-node SLURM pipeline | loads oneapi then VASP 6.6.0, runs prepare/SCF/band/postprocess stages with 8 CPUs, KPAR=2, NCORE=4.
- projects/2026-05-02-si-bands-vasp/postprocess_bands.py | result parser/plotter | parses `vasprun_band.xml` with pymatgen, writes `band_analysis.json` and `bands.png`.

### Simulation history
- (run_id | objective | status | artifacts | notes)
- 26536 | Si PBE band structure smoke test | failed before stage start | projects/2026-05-02-si-bands-vasp/slurm-26536.err | `stage_times.tsv` write failed in `/var/spool/slurmd/...`; fixed by switching project root detection to `SLURM_SUBMIT_DIR`.
- 26537 | Si PBE band structure smoke test | failed at SCF launch | projects/2026-05-02-si-bands-vasp/vasp_scf.err | Open MPI reported not enough slots for 8 ranks with `--ntasks=1 --cpus-per-task=8`; `run.sh` patched to add `--oversubscribe`.
- 26538 | Si PBE band structure smoke test | failed at SCF launch | projects/2026-05-02-si-bands-vasp/vasp_scf.err | MPI reported `vasp_std` not found on ranks; host has an `mpirun` shell function and multiple MPI launchers, so `run.sh` now calls absolute Intel MPI and absolute VASP paths.
- 26539 | Si PBE band structure smoke test | failed at SCF launch | projects/2026-05-02-si-bands-vasp/vasp_scf.err | `VASP_STD` was empty because `load_modules` ran in a subshell; `stage()` now preserves environment and guarded functions return immediately on failed commands.
- 26540 | Si PBE band structure smoke test | completed but failed acceptance | projects/2026-05-02-si-bands-vasp/band_analysis.json | raw run succeeded; analysis showed `gap=0.2517 eV`, VBM off-Gamma, `NBANDS=8`; corrected inputs and postprocessing were prepared for rerun `26541`.
- 26541 | Si PBE band structure smoke test | completed and accepted | projects/2026-05-02-si-bands-vasp/band_analysis.json | `NBANDS=12` plus direct `EIGENVAL` path analysis restored expected Si indirect gap and QE parity.
- 26542 | Si PBE band structure smoke test final artifact pass | completed and accepted | projects/2026-05-02-si-bands-vasp/WAVECAR | repeated accepted run with `LWAVE=True` so cleanup rule could keep a real `WAVECAR`.

### Key results
- (result_id | metric | value | conditions | evidence_path)
- si-vasp-gap-2026-05-02 | indirect gap | 0.572568 eV | VASP 6.6.0 PBE, Si primitive cell, `.64` Si PAW PBE, `ENCUT=400 eV`, `8x8x8` Gamma SCF, `NBANDS=12`, 36-point/segment `L-G-X-W-K-G` line path | projects/2026-05-02-si-bands-vasp/band_analysis.json
- si-vasp-topology-2026-05-02 | VBM/CBM location | VBM at Gamma; CBM on `G-X` at fraction 0.828571 | same accepted run as above; direct `EIGENVAL` parser and pymatgen `BSVasprun` agree on the indirect topology | projects/2026-05-02-si-bands-vasp/band_analysis.json
- si-vasp-qe-parity-2026-05-02 | VASP minus QE gap delta | -0.002432 eV | QE reference gap 0.575 eV from paired Si baseline; within 0.1 eV acceptance by a wide margin | projects/2026-05-02-si-bands-vasp/band_analysis.json

### Parameter source mapping
- (run_id | parameter_or_setting | value | source | evidence_path | notes)
- 2026-05-02-si-bands-vasp | POTCAR | `/home/werner/Public/hpc/vasp/pot/potpaw_PBE.64/Si/POTCAR` | site facts override | projects/2026-05-02-si-bands-vasp/generate_inputs.py | ENMAX checked as 245.345 eV, so ENCUT=400 eV is above 1.3x ENMAX.
- 2026-05-02-si-bands-vasp | SCF settings | ENCUT=400, EDIFF=1e-6, ISMEAR=0, SIGMA=0.05, 8x8x8 Gamma, LCHARG=True | original request | projects/2026-05-02-si-bands-vasp/INCAR_scf | generated and reviewed before submission.
- 2026-05-02-si-bands-vasp | band path | L-G-X-W-K-G, 36 points/segment, ICHARG=11 | original request plus pymatgen HighSymmKpath coordinates | projects/2026-05-02-si-bands-vasp/KPOINTS_band | band INCAR sets ISYM=0.
- 2026-05-02-si-bands-vasp | accepted band settings | `ICHARG=11`, `ISYM=0`, `NBANDS=12`, `LWAVE=True`, `LORBIT=11` | original request plus prior passing local recipe for Si parity | projects/2026-05-02-si-bands-vasp/INCAR_band | `NBANDS=12` was required to recover the expected indirect gap.
- 2026-05-02-si-bands-vasp | SLURM resources | partition=batch, nodes=1, ntasks=1, cpus-per-task=8, time=24:00:00 | execution target and prior perf log | projects/2026-05-02-si-bands-vasp/run.sh | prior same-system perf favored 8 CPUs, KPAR=2, NCORE=4.

### Simulation uncertainty
- (run_id | uncertainty_or_assumption | impact | mitigation_or_next_step | status)
- 2026-05-02-si-bands-vasp | `skills/` directory is absent in this checkout | no package-local VASP recipe beyond README and supplied site facts | used supplied request, README, prior perf log, and direct module/POTCAR checks | validated by accepted jobs 26541 and 26542.
- 2026-05-02-si-bands-vasp | `sbatch` executes a spooled script path, so `BASH_SOURCE[0]` is not the project directory | can break relative outputs before stage execution | patched `run.sh` to use `SLURM_SUBMIT_DIR` first | validated by accepted jobs 26541 and 26542.
- 2026-05-02-si-bands-vasp | Open MPI slot detection with single SLURM task exposes only 1 slot though 8 CPUs are allocated | can prevent `mpirun -np 8` launch | final script uses the absolute Intel MPI launcher with site-required `--ntasks=1 --cpus-per-task=8` | validated by accepted jobs 26541 and 26542.
- 2026-05-02-si-bands-vasp | `mpirun` name is a shell function with multiple external MPI candidates in PATH | can select an MPI launcher incompatible with the VASP build | call absolute Intel MPI launcher and absolute VASP binary in `run.sh` | validated by accepted jobs 26541 and 26542.
- 2026-05-02-si-bands-vasp | stage functions that load modules cannot run in subshells | module and executable variables vanish before SCF/band stages | patched `stage()` to call functions in the parent shell and added explicit failure guards | validated by accepted jobs 26541 and 26542.
- 2026-05-02-si-bands-vasp | a band run with default `NBANDS=8` underestimates the Si indirect gap and shifts the apparent VBM away from Gamma | invalidates QE parity and gap acceptance checks | resolved by accepted reruns with `NBANDS=12` and direct `EIGENVAL` path analysis | closed.

### Suggested skills updates
- (<package_id> | issue_pattern | proposed_skill_update | evidence | status)
- vasp-demo | single-node SLURM launcher ambiguity and Si band underfill | encode `SLURM_SUBMIT_DIR` usage, absolute Intel MPI launcher, and `NBANDS=12` for small Si band baselines in package guidance | jobs 26536-26540 failed or misanalyzed until these fixes were applied; jobs 26541-26542 passed | open
