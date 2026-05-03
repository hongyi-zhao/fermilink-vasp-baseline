#!/bin/bash
# Reorganize a flat VASP project dir into canonical subdirs.
# Usage:
#   reorganize-project.sh dry-run <project-dir>
#   reorganize-project.sh execute <project-dir>
#
# Layout produced:
#   inputs/   POSCAR, POTCAR, INCAR_*, KPOINTS_*
#   scf/      OUTCAR_scf -> OUTCAR, vasprun_scf.xml -> vasprun.xml, etc.
#   bands/    OUTCAR_band -> OUTCAR, vasprun_band.xml -> vasprun.xml, etc.
#             (note: bands/ ICHARG=11 reads scf/CHGCAR)
#   analysis/ band_analysis.json, bands.png, module_list.txt
#   logs/     slurm-*.{out,err}, *.tsv, *.log
#   scripts/  generate_inputs.py, postprocess_bands.py, run.sh
#   .backup-*/ kept as-is (historical)

set -euo pipefail

MODE="${1:-}"
PROJECT="${2:-}"

usage() {
    echo "Usage: $0 {dry-run|execute} <project-dir>"
    exit 1
}

[[ -z "$MODE" || -z "$PROJECT" ]] && usage
[[ "$MODE" != "dry-run" && "$MODE" != "execute" ]] && usage
[[ ! -d "$PROJECT" ]] && { echo "ERROR: $PROJECT is not a directory" >&2; exit 2; }

PROJECT="$(cd "$PROJECT" && pwd)"   # absolute path
echo "===== Reorganize: $PROJECT ====="
echo "===== Mode: $MODE ====="
echo ""

# --- helper ---
do_cmd() {
    if [[ "$MODE" == "dry-run" ]]; then
        echo "  [dry-run] $*"
    else
        echo "  [exec] $*"
        eval "$@"
    fi
}

cd "$PROJECT"

# === Step 1: Create subdirs ===
echo "--- Step 1: Create subdirs ---"
for d in inputs scf bands analysis logs scripts; do
    if [[ -d "$d" ]]; then
        echo "  $d/ already exists, skip"
    else
        do_cmd "mkdir -p -- $d"
    fi
done
echo ""

# === Step 2: inputs/ ===
echo "--- Step 2: Move canonical inputs to inputs/ ---"
for f in POSCAR POTCAR INCAR_scf INCAR_band INCAR_nscf KPOINTS_scf KPOINTS_band KPOINTS_nscf; do
    if [[ -f "$f" ]]; then
        do_cmd "mv -- $f inputs/"
    fi
done
echo ""

# === Step 3: scf/ ===
echo "--- Step 3: Move SCF stage outputs to scf/ ---"
declare -A scf_renames=(
    [OUTCAR_scf]=OUTCAR
    [vasprun_scf.xml]=vasprun.xml
    [OSZICAR_scf]=OSZICAR
    [EIGENVAL_scf]=EIGENVAL
)
for src in "${!scf_renames[@]}"; do
    dst="${scf_renames[$src]}"
    if [[ -f "$src" ]]; then
        do_cmd "mv -- $src scf/$dst"
    fi
done
# CHGCAR is the SCF output (band stage reads it)
if [[ -f CHGCAR ]]; then
    do_cmd "mv -- CHGCAR scf/CHGCAR"
fi
# WAVECAR also from SCF (large file, keep here for HSE/SOC restart use)
if [[ -f WAVECAR ]]; then
    do_cmd "mv -- WAVECAR scf/WAVECAR"
fi
# CHG (small, less used) -> scf/
if [[ -f CHG ]]; then
    do_cmd "mv -- CHG scf/CHG"
fi
echo ""

# === Step 4: bands/ ===
echo "--- Step 4: Move bands stage outputs to bands/ ---"
declare -A bands_renames=(
    [OUTCAR_band]=OUTCAR
    [vasprun_band.xml]=vasprun.xml
    [OSZICAR_band]=OSZICAR
    [EIGENVAL_band]=EIGENVAL
)
for src in "${!bands_renames[@]}"; do
    dst="${bands_renames[$src]}"
    if [[ -f "$src" ]]; then
        do_cmd "mv -- $src bands/$dst"
    fi
done
# PROCAR is from bands (LORBIT=11)
if [[ -f PROCAR ]]; then
    do_cmd "mv -- PROCAR bands/PROCAR"
fi
echo ""

# === Step 5: analysis/ ===
echo "--- Step 5: Move analysis artifacts ---"
for f in band_analysis.json bands.png module_list.txt; do
    if [[ -f "$f" ]]; then
        do_cmd "mv -- $f analysis/"
    fi
done
echo ""

# === Step 6: logs/ ===
echo "--- Step 6: Move logs ---"
# slurm logs (glob)
for f in slurm-*.out slurm-*.err; do
    [[ -f "$f" ]] && do_cmd "mv -- $f logs/"
done
# logger logs
for f in stage_times.tsv perf_append.log postprocess.log postprocess_manual.log module_load.log vasp_band.out vasp_band.err vasp_scf.out vasp_scf.err; do
    [[ -f "$f" ]] && do_cmd "mv -- $f logs/"
done
# debug artifacts
for f in mpirun.path mpirun.version vasp_std.path potcar_enmax.txt; do
    [[ -f "$f" ]] && do_cmd "mv -- $f logs/"
done
echo ""

# === Step 7: scripts/ ===
echo "--- Step 7: Move scripts ---"
for f in generate_inputs.py postprocess_bands.py run.sh; do
    if [[ -f "$f" ]]; then
        do_cmd "mv -- $f scripts/"
    fi
done
# _perf_append.py is typically a symlink to ../../_perf_append.py, move into scripts/
if [[ -L _perf_append.py || -f _perf_append.py ]]; then
    do_cmd "mv -- _perf_append.py scripts/"
fi
echo ""

# === Step 8: cleanup transient garbage ===
echo "--- Step 8: Remove transient garbage from cwd ---"
# These are outputs that get overwritten on each sbatch run; keep none in cwd
for f in OUTCAR EIGENVAL OSZICAR vasprun.xml IBZKPT PCDAT REPORT XDATCAR CONTCAR DOSCAR vaspout.h5; do
    if [[ -f "$f" ]]; then
        do_cmd "rm -f -- $f"
    fi
done
# INCAR / KPOINTS / POSCAR / POTCAR in cwd are stage-cycle remnants (real ones in inputs/)
for f in INCAR KPOINTS POSCAR POTCAR; do
    if [[ -f "$f" && ! -L "$f" ]]; then
        do_cmd "rm -f -- $f"
    fi
done
# EIGENVAL_scf.saved is a cascade-fix leftover
if [[ -f EIGENVAL_scf.saved ]]; then
    do_cmd "rm -f -- EIGENVAL_scf.saved"
fi
# fcitx/rime input method log leak
for f in rime.fcitx-rime.*.log rime.fcitx-rime.INFO; do
    if [[ -f "$f" ]]; then
        do_cmd "rm -f -- $f"
    fi
done
# python cache
if [[ -d __pycache__ ]]; then
    do_cmd "rm -rf -- __pycache__"
fi
echo ""

# === Step 9: Show final layout ===
echo "--- Step 9: Final state ---"
if [[ "$MODE" == "execute" ]]; then
    echo ""
    echo "===== Final layout ====="
    if command -v tree &>/dev/null; then
        tree -L 2 -a "$PROJECT" | head -50
    else
        ls -la "$PROJECT"
        for d in inputs scf bands analysis logs scripts; do
            echo ""
            echo "--- $d/ ---"
            ls -la "$PROJECT/$d/" 2>/dev/null || echo "  (does not exist)"
        done
    fi
    echo ""
    echo "===== Done. Working tree state vs git: ====="
    echo "  cd $PROJECT && git status --short  (run separately)"
    echo ""
    echo "===== Next steps ====="
    echo "  1. Update scripts/run.sh to use stage subdirs (manual)"
    echo "  2. Update scripts/generate_inputs.py to write to ../inputs/"
    echo "  3. Update scripts/postprocess_bands.py to read ../bands/vasprun.xml"
    echo "  4. Test: cd $PROJECT && sbatch scripts/run.sh"
    echo "  5. Verify gap unchanged at 0.572568 eV"
else
    echo "  (dry-run: no changes made)"
    echo ""
    echo "  To actually reorganize, run:"
    echo "    $0 execute $PROJECT"
fi
