- prompt: Compute the electronic band structure of bulk silicon diamond with PBE in VASP 6.6.0 along L-G-X-W-K-G and cross-validate against the QE baseline.
-procedures: Generated VASP inputs for SCF (`8x8x8` Gamma-centered, `ENCUT=400 eV`, `EDIFF=1e-6`, `ISMEAR=0`, `SIGMA=0.05`, `LCHARG=.TRUE.`, `KPAR=2`, `NCORE=4`) and non-SCF band calculation (`ICHARG=11`, `NBANDS=12`, 36 points/segment line-mode `L-G-X-W-K-G` path). Ran the single-node SLURM chain with `oneapi/2024.2.0`, `vasp/6.6.0-oneapi.2024.2.0`, `--nodes=1 --ntasks=1 --cpus-per-task=8`, and Intel MPI `mpirun -np "${SLURM_CPUS_PER_TASK}"`.
- generated data: `OUTCAR_scf`, `OUTCAR_band`, `vasprun_scf.xml`, `vasprun_band.xml`, `EIGENVAL`, `band_analysis.json`, `stage_times.tsv`, `module_list.txt`; SCF electronic iterations = 14, indirect gap = 0.572568 eV.
- generated figure: `bands.png`
- key result: VBM at Gamma; CBM on G-X at fraction 0.828571; QE reference gap = 0.575 eV, VASP-QE gap delta = -0.002432 eV.
- status: done
cleanup_decision: kept WAVECAR
