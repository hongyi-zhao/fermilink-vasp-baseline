#!/bin/bash
#SBATCH --job-name=si-bands-vasp
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=24:00:00
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err

ulimit -Sn $(ulimit -Hn) 2>/dev/null; ulimit -s unlimited 2>/dev/null
set -euo pipefail

PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_DIR"

export FL_SYSTEM_TAG=Si_diamond_PBE_band_vasp
export VASP_PP=~/Public/hpc/vasp/pot
PYTHON=/home/werner/.pyenv/versions/datasci/bin/python
MPI_RUN=/opt/intel/oneapi/2024.2.0/mpi/2021.13/bin/mpirun
VASP_STD=

: > stage_times.tsv

stage() {
    local name="$1"
    shift
    local start end status
    start=$(date +%s)
    echo "[stage:${name}] start $(date -Is)"
    set +e
    "$@"
    status=$?
    set -e
    end=$(date +%s)
    printf "%s\t%s\t%s\t%s\n" "$name" "$start" "$end" "$status" >> stage_times.tsv
    echo "[stage:${name}] end $(date -Is) status=${status} elapsed=$((end-start))s"
    return "$status"
}

load_modules() {
    set +u
    module load oneapi/2024.2.0 > module_load.log 2>&1
    module load vasp/6.6.0-oneapi.2024.2.0 >> module_load.log 2>&1
    set -u
    module list > module_list.txt 2>&1
    VASP_STD="$(command -v vasp_std)"
    printf "%s\n" "$VASP_STD" > vasp_std.path
    printf "%s\n" "$MPI_RUN" > mpirun.path
    "$MPI_RUN" --version > mpirun.version 2>&1
}

prepare_inputs() {
    rm -f OUTCAR vasprun.xml OSZICAR EIGENVAL CHGCAR WAVECAR
    rm -f OUTCAR_scf OUTCAR_band vasprun_scf.xml vasprun_band.xml
    rm -f OSZICAR_scf OSZICAR_band EIGENVAL_scf EIGENVAL_band
    rm -f band_analysis.json bands.png postprocess.log perf_append.log
    "$PYTHON" generate_inputs.py
    grep ENMAX POTCAR > potcar_enmax.txt
    cp INCAR_scf INCAR
    cp KPOINTS_scf KPOINTS
}

run_scf() {
    cp INCAR_scf INCAR || return $?
    cp KPOINTS_scf KPOINTS || return $?
    cat "$VASP_PP"/potpaw_PBE.64/Si/POTCAR > POTCAR || return $?
    "$MPI_RUN" -np "${SLURM_CPUS_PER_TASK}" "$VASP_STD" > vasp_scf.out 2> vasp_scf.err || return $?
    cp OUTCAR OUTCAR_scf || return $?
    cp vasprun.xml vasprun_scf.xml || return $?
    cp OSZICAR OSZICAR_scf || return $?
    cp EIGENVAL EIGENVAL_scf || return $?
}

run_band() {
    cp INCAR_band INCAR || return $?
    cp KPOINTS_band KPOINTS || return $?
    cat "$VASP_PP"/potpaw_PBE.64/Si/POTCAR > POTCAR || return $?
    "$MPI_RUN" -np "${SLURM_CPUS_PER_TASK}" "$VASP_STD" > vasp_band.out 2> vasp_band.err || return $?
    cp OUTCAR OUTCAR_band || return $?
    cp vasprun.xml vasprun_band.xml || return $?
    cp OSZICAR OSZICAR_band || return $?
}

postprocess() {
    cp OUTCAR_scf OUTCAR || return $?
    cp INCAR_scf INCAR || return $?
    cp EIGENVAL_scf EIGENVAL_scf.saved || return $?
    cp EIGENVAL EIGENVAL_band || return $?
    "$PYTHON" postprocess_bands.py > postprocess.log 2>&1 || return $?
    ln -sfn ../../_perf_append.py _perf_append.py || return $?
    "$PYTHON" _perf_append.py > perf_append.log 2>&1 || return $?
    cp OUTCAR_band OUTCAR || return $?
}

stage module load_modules
stage prepare prepare_inputs
stage scf run_scf
stage band run_band
stage postprocess postprocess
