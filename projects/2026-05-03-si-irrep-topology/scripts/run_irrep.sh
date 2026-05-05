#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root/analysis"

export PYENV_VERSION=datasci
if ! command -v irrep >/dev/null 2>&1; then
  echo "ERROR: irrep console script not found in PYENV_VERSION=datasci" >&2
  exit 127
fi

set +e
irrep \
  -code=vasp \
  -fWAV=../inputs/WAVECAR \
  -fPOS=../inputs/POSCAR \
  -EF=6.0469251928 \
  -IBend=12 \
  -kpoints=37,72,1 \
  -kpnames="GM,X,L" \
  --time-reversal \
  --symmetry-indicators \
  --ebr-decomposition \
  -json_file=irrep_ebr_attempt.json \
  -v \
  > irrep_ebr_stdout.txt 2>&1
ebr_exit=$?
set -e
printf "%s\n" "$ebr_exit" > irrep_ebr_exit_status.txt

if [[ "$ebr_exit" -ne 0 ]] && ! grep -q "TRIVIAL or displays FRAGILE TOPOLOGY" irrep_ebr_stdout.txt; then
  echo "ERROR: IrRep EBR attempt failed before reaching a topology classification boundary." >&2
  exit "$ebr_exit"
fi

irrep \
  -code=vasp \
  -fWAV=../inputs/WAVECAR \
  -fPOS=../inputs/POSCAR \
  -EF=6.0469251928 \
  -IBend=12 \
  -kpoints=37,72,1 \
  -kpnames="GM,X,L" \
  --time-reversal \
  --symmetry-indicators \
  -json_file=irrep_output.json \
  -v \
  > irrep_stdout.txt 2>&1

PYENV_VERSION=datasci python "$project_root/scripts/write_topology_summary.py"
