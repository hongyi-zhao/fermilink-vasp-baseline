#!/bin/bash
#SBATCH --job-name=si-bands-vasp
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=24:00:00
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err

ulimit -Sn $(ulimit -Hn) 2>/dev/null; ulimit -s unlimited 2>/dev/null
set -euo pipefail

# Project root: parent of scripts/ when sourced from sbatch (which uses SLURM_SUBMIT_DIR);
# also works when run manually as `bash scripts/run.sh` from project root.
PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$PROJECT_DIR"

mkdir -p inputs scf bands analysis logs

export FL_SYSTEM_TAG=Si_diamond_PBE_band_vasp
export VASP_PP=~/Public/hpc/vasp/pot
export OMP_NUM_THREADS=1
PYTHON=/home/werner/.pyenv/versions/datasci/bin/python
MPI_RUN=/opt/intel/oneapi/2024.2.0/mpi/2021.13/bin/mpirun
VASP_STD=

: > logs/stage_times.tsv

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
    printf "%s\t%s\t%s\t%s\n" "$name" "$start" "$end" "$status" >> logs/stage_times.tsv
    echo "[stage:${name}] end $(date -Is) status=${status} elapsed=$((end-start))s"
    return "$status"
}

load_modules() {
    set +u
    module purge > logs/module_load.log 2>&1
    module load oneapi/2024.2.0 > logs/module_load.log 2>&1
    module load vasp/6.6.0-oneapi.2024.2.0 >> logs/module_load.log 2>&1
    set -u
    module list > analysis/module_list.txt 2>&1
    VASP_STD="$(command -v vasp_std)"
    printf "%s\n" "$VASP_STD" > logs/vasp_std.path
    printf "%s\n" "$MPI_RUN" > logs/mpirun.path
    "$MPI_RUN" --version > logs/mpirun.version 2>&1
}

refresh_root_links() {
    ln -sfn inputs/INCAR_band INCAR
    ln -sfn inputs/INCAR_scf INCAR_scf
    ln -sfn inputs/INCAR_band INCAR_band
    ln -sfn inputs/KPOINTS_scf KPOINTS_scf
    ln -sfn inputs/KPOINTS_band KPOINTS_band
    ln -sfn inputs/POSCAR POSCAR
    ln -sfn inputs/POTCAR POTCAR
    ln -sfn scf/OUTCAR OUTCAR_scf
    ln -sfn bands/OUTCAR OUTCAR_band
    ln -sfn scf/vasprun.xml vasprun_scf.xml
    ln -sfn bands/vasprun.xml vasprun_band.xml
    ln -sfn bands/EIGENVAL EIGENVAL
    ln -sfn analysis/band_analysis.json band_analysis.json
    ln -sfn analysis/bands.png bands.png
    ln -sfn analysis/module_list.txt module_list.txt
    ln -sfn logs/stage_times.tsv stage_times.tsv
    ln -sfn scripts/generate_inputs.py generate_inputs.py
    ln -sfn scripts/postprocess_bands.py postprocess_bands.py
    ln -sfn scripts/run.sh run.sh
    ln -sfn ../../../_perf_append.py scripts/_perf_append.py
    ln -sfn ../../_perf_append.py _perf_append.py
}

prepare_inputs() {
    # Generate canonical inputs in inputs/
    "$PYTHON" scripts/generate_inputs.py
    grep ENMAX inputs/POTCAR > logs/potcar_enmax.txt
}

# Stage workdir setup helper: link canonical inputs from ../inputs/ as bare names
link_inputs() {
    local stage_dir="$1"   # scf or bands
    local incar_src="$2"   # INCAR_scf or INCAR_band
    local kpts_src="$3"    # KPOINTS_scf or KPOINTS_band
    cd "$stage_dir"
    ln -sfn ../inputs/POSCAR POSCAR
    ln -sfn ../inputs/POTCAR POTCAR
    ln -sfn "../inputs/${incar_src}" INCAR
    ln -sfn "../inputs/${kpts_src}" KPOINTS
    cd ..
}

run_scf() {
    link_inputs scf INCAR_scf KPOINTS_scf
    cd scf
    "$MPI_RUN" -np "${SLURM_CPUS_PER_TASK}" "$VASP_STD" > vasp.out 2> vasp.err
    cd ..
}

run_band() {
    link_inputs bands INCAR_band KPOINTS_band
    cd bands
    # ICHARG=11: read CHGCAR from SCF stage
    ln -sfn ../scf/CHGCAR CHGCAR
    # WAVECAR optional but harmless to link if present
    [ -f ../scf/WAVECAR ] && ln -sfn ../scf/WAVECAR WAVECAR
    "$MPI_RUN" -np "${SLURM_CPUS_PER_TASK}" "$VASP_STD" > vasp.out 2> vasp.err
    cd ..
}

postprocess() {
    "$PYTHON" scripts/postprocess_bands.py > logs/postprocess.log 2>&1
    refresh_root_links
    # Perf logger reads bands/OUTCAR explicitly via PERF_OUTCAR_PATH (SITE FACTS rule 5).
    export PERF_OUTCAR_PATH=bands/OUTCAR
    "$PYTHON" scripts/_perf_append.py > logs/perf_append.log 2>&1
}

stage module load_modules
stage prepare prepare_inputs
stage scf run_scf
stage band run_band
stage postprocess postprocess
