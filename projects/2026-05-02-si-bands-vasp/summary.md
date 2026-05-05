- prompt: Compute the electronic band structure of bulk silicon diamond with PBE in VASP 6.6.0 along L-G-X-W-K-G and cross-validate against the QE baseline.
-procedures: Generated VASP inputs in inputs/ for SCF (`8x8x8` Gamma-centered, `ENCUT=400 eV`, `EDIFF=1e-6`, `ISMEAR=0`, `SIGMA=0.05`, `LCHARG=.TRUE.`, `KPAR=2`, `NCORE=4`) and non-SCF band calculation (`ICHARG=11`, `NBANDS=12`, 36 points/segment line-mode `L-G-X-W-K-G` path). Stages run in scf/ and bands/ subdirs with symlinked inputs. Single-node SLURM chain with `oneapi/2024.2.0`, `vasp/6.6.0-oneapi.2024.2.0`, `--nodes=1 --ntasks=1 --cpus-per-task=8`, and Intel MPI `mpirun -np "${SLURM_CPUS_PER_TASK}"`.
- generated data: `scf/OUTCAR`, `bands/OUTCAR`, `scf/vasprun.xml`, `bands/vasprun.xml`, `bands/EIGENVAL`, `analysis/band_analysis.json`, `logs/stage_times.tsv`, `analysis/module_list.txt`; SCF electronic iterations = 14, indirect gap = 0.572568 eV.
- generated figure: `analysis/bands.png`
- key result: VBM at Gamma; CBM on G-X at fraction 0.828571; QE reference gap = 0.575 eV, VASP-QE gap delta = -0.002432 eV.
- status: done
cleanup_decision: kept WAVECAR
