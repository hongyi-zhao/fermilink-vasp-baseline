# IrRep TQC Handoff

## Completed Si Reference

- Project: `/home/werner/fermilink/vasp-demo/projects/2026-05-03-si-irrep-topology`
- Source WAVECAR: `/home/werner/fermilink/vasp-demo/projects/2026-05-02-si-bands-vasp/scf/WAVECAR`
- Source POSCAR: `/home/werner/fermilink/vasp-demo/projects/2026-05-02-si-bands-vasp/inputs/POSCAR`
- Environment: `PYENV_VERSION=datasci`, IrRep `2.6.3`, no package install.
- Final replay command: `./scripts/run_irrep.sh`
- Main outputs:
  - `analysis/irrep_output.json`
  - `analysis/irrep_stdout.txt`
  - `analysis/irrep_ebr_stdout.txt`
  - `analysis/topology_summary.json`

## Si Result

The existing non-SOC Si WAVECAR is readable by IrRep. The clean IR/SI pass exits 0 when using explicit WAVECAR k-point indices:

```bash
cd /home/werner/fermilink/vasp-demo/projects/2026-05-03-si-irrep-topology/analysis
PYENV_VERSION=datasci irrep \
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
```

Spinless occupied valence irreps:

```json
{
  "GM": ["GM1+", "GM5+"],
  "X": ["X1", "X3"],
  "L": ["L2-", "L1+", "L3-"]
}
```

The summary verdict is `trivial`; the projected EBR evidence is `atomic-limit` for the available `GM/X/L` irreps. Spinful `z2/z4` indicators are not applicable to this existing non-SOC, non-spinor WAVECAR. A full SOC topological-insulator classification requires an `LSORBIT = T` spinor WAVECAR.

The IrRep `--ebr-decomposition` CLI path reaches the useful classification boundary, then fails while printing because this environment lacks OR-Tools and IrRep 2.6.3 does not populate `BandStructure.classification` in that branch:

```text
There exists integer-valued solutions to the EBR decomposition problem, so the set of bands is TRIVIAL or displays FRAGILE TOPOLOGY. Install OR-Tools to compute decompositions.
AttributeError: 'BandStructure' object has no attribute 'classification'
```

This is preserved in `analysis/irrep_ebr_stdout.txt` and is not a WAVECAR-read failure.

## Future Nontrivial Reference: Bi SG 166

Use the same workflow on a spinor SOC WAVECAR for rhombohedral Bi, SG 166, where the expected literature sanity check is `z4 = 2` HOTI. Do not install packages in the site environment; use the preconfigured `datasci` IrRep if available.

Copy this as `scripts/run_irrep_bi.sh` in a future Bi project and edit only the path and k-point variables at the top:

```bash
#!/usr/bin/env bash
set -euo pipefail

project_root="/path/to/bi-irrep-project"
wavecar="/path/to/bi/scf/WAVECAR"
poscar="/path/to/bi/inputs/POSCAR"
fermi_energy_eV="<read-from-Bi-OUTCAR>"

# For SG 166, use the complete SOC high-symmetry/TRIM set present in the WAVECAR.
# Common BCS labels for the rhombohedral setting include GM, T, L, and F, but
# confirm labels and exact WAVECAR indices from an IrRep probe before final use.
kpoints="<comma-separated-WAVECAR-indices>"
kpnames="GM,T,L,F"

mkdir -p "$project_root/inputs" "$project_root/analysis" "$project_root/logs"
ln -sfn "$wavecar" "$project_root/inputs/WAVECAR"
ln -sfn "$poscar" "$project_root/inputs/POSCAR"

cd "$project_root/analysis"
export PYENV_VERSION=datasci
command -v irrep >/dev/null
irrep --help | head -10 > irrep_cli_help.txt

irrep \
  -code=vasp \
  -fWAV=../inputs/WAVECAR \
  -fPOS=../inputs/POSCAR \
  -EF="$fermi_energy_eV" \
  -IBend=<occupied-plus-low-empty-band-count> \
  -kpoints="$kpoints" \
  -kpnames="$kpnames" \
  --time-reversal \
  --symmetry-indicators \
  --ebr-decomposition \
  -json_file=irrep_output.json \
  -v \
  > irrep_stdout.txt 2>&1
```

Before trusting a Bi `z4` result, verify:

- `LSORBIT = T` and the WAVECAR is spinor/noncollinear as expected.
- The chosen `-kpoints` cover the complete symmetry-indicator and EBR-constrained high-symmetry set, not only a visually familiar subset.
- `irrep_output.json` reports SG 166 and spinor irreps.
- The parsed indicator table contains `z4 = 2` for the expected HOTI sanity check.
