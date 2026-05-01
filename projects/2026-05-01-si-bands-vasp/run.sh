#!/bin/bash
#SBATCH --job-name=si-bands-vasp
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=24:00:00
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err

set -eo pipefail
ulimit -Sn $(ulimit -Hn) 2>/dev/null || true
ulimit -s unlimited 2>/dev/null || true

export FL_SYSTEM_TAG=Si_diamond_PBE_band_vasp
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export VASP_PP="${VASP_PP:-/home/werner/Public/hpc/vasp/pot}"
PYTHON_BIN="${PYTHON_BIN:-/home/werner/.pyenv/versions/datasci/bin/python}"

stage_times="stage_times.tsv"
: > "${stage_times}"

stage() {
  local name="$1"
  shift
  local start end rc
  start=$(date +%s.%N)
  set +e
  "$@"
  rc=$?
  set -e
  end=$(date +%s.%N)
  printf "%s\t%s\t%s\t%s\n" "${name}" "${start}" "${end}" "${rc}" >> "${stage_times}"
  return "${rc}"
}

set +u
module purge
module load oneapi/2024.2.0 > module_load_oneapi.log 2>&1
module load vasp/6.6.0-oneapi.2024.2.0 > module_load_vasp.log 2>&1
module list > module_list.txt 2>&1
set -u

if [[ ! -f "${VASP_PP}/potpaw_PBE/Si/POTCAR" ]]; then
  echo "Missing ${VASP_PP}/potpaw_PBE/Si/POTCAR" >&2
  exit 2
fi

stage prepare "${PYTHON_BIN}" generate_inputs.py | tee generate_inputs.out
grep ENMAX POTCAR | tee potcar_enmax.txt

stage scf bash -c '
  cp INCAR_scf INCAR
  cp KPOINTS_scf KPOINTS
  mpirun -np "${SLURM_CPUS_PER_TASK}" vasp_std > vasp_scf.out 2> vasp_scf.err
  cp OUTCAR OUTCAR_scf
  cp vasprun.xml vasprun_scf.xml
'

stage band bash -c '
  cp INCAR_band INCAR
  cp KPOINTS_band KPOINTS
  mpirun -np "${SLURM_CPUS_PER_TASK}" vasp_std > vasp_band.out 2> vasp_band.err
  cp OUTCAR OUTCAR_band
  cp vasprun.xml vasprun_band.xml
'

stage postprocess "${PYTHON_BIN}" postprocess_bands.py > postprocess.out 2> postprocess.err

if [[ -L _perf_append.py || -f _perf_append.py ]]; then
  cp INCAR_scf INCAR
  cp OUTCAR_scf OUTCAR
  stage perf "${PYTHON_BIN}" _perf_append.py > perf_append.out 2> perf_append.err || true
fi
