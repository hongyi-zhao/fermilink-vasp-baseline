#!/usr/bin/env python3
"""Generate VASP inputs for the Si diamond PBE band-structure baseline."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


A0 = 5.43
POTCAR_DEFAULT = Path("/home/werner/Public/hpc/vasp/pot/potpaw_PBE/Si/POTCAR")
NPOINTS_PER_SEGMENT = 36

PROJECT = Path(__file__).resolve().parent


def write(path: str, text: str) -> None:
    (PROJECT / path).write_text(text.strip() + "\n")


def main() -> None:
    potcar_src = Path(os.environ.get("VASP_SI_POTCAR", "")) if os.environ.get("VASP_SI_POTCAR") else None
    if potcar_src is None:
        vasp_pp = os.environ.get("VASP_PP")
        if vasp_pp:
            candidate = Path(vasp_pp) / "potpaw_PBE" / "Si" / "POTCAR"
            if candidate.exists():
                potcar_src = candidate
        if potcar_src is None:
            potcar_src = POTCAR_DEFAULT
    if not potcar_src.exists():
        raise FileNotFoundError(
            f"Si PAW PBE POTCAR not found at {potcar_src}. "
            "Set VASP_PP or VASP_SI_POTCAR before running."
        )

    write(
        "POSCAR",
        f"""
Si diamond primitive PBE a={A0:.2f} Angstrom
1.0
  0.000000000000  {A0/2:.12f}  {A0/2:.12f}
  {A0/2:.12f}  0.000000000000  {A0/2:.12f}
  {A0/2:.12f}  {A0/2:.12f}  0.000000000000
Si
2
Direct
  0.000000000000  0.000000000000  0.000000000000
  0.250000000000  0.250000000000  0.250000000000
""",
    )

    common = """
SYSTEM = Si_diamond_PBE_band_vasp
GGA = PE
ENCUT = 400
EDIFF = 1E-6
NELM = 100
PREC = Accurate
ALGO = Fast
LREAL = .FALSE.
IBRION = -1
NSW = 0
ISMEAR = 0
SIGMA = 0.05
LWAVE = .FALSE.
KPAR = 2
NCORE = 4
"""
    write(
        "INCAR_scf",
        common
        + """
ICHARG = 2
LCHARG = .TRUE.
""",
    )
    write(
        "INCAR_band",
        common
        + """
ICHARG = 11
LCHARG = .FALSE.
LORBIT = 11
NBANDS = 12
""",
    )
    write(
        "KPOINTS_scf",
        """
Si diamond SCF Gamma-centered 8x8x8
0
Gamma
  8  8  8
  0  0  0
""",
    )

    # FCC primitive reciprocal-coordinate labels, Setyawan/Curtarolo convention.
    # The requested path is L-Gamma-X-W-K-Gamma with 36 points per segment.
    labels = [
        ("L", (0.5, 0.5, 0.5)),
        ("G", (0.0, 0.0, 0.0)),
        ("X", (0.5, 0.0, 0.5)),
        ("W", (0.5, 0.25, 0.75)),
        ("K", (0.375, 0.375, 0.75)),
        ("G", (0.0, 0.0, 0.0)),
    ]
    lines = [
        f"Si diamond band path L-G-X-W-K-G, {NPOINTS_PER_SEGMENT} points per segment",
        str(NPOINTS_PER_SEGMENT),
        "Line-mode",
        "Reciprocal",
    ]
    for (lab1, k1), (lab2, k2) in zip(labels[:-1], labels[1:]):
        lines.append(f"  {k1[0]:.12f}  {k1[1]:.12f}  {k1[2]:.12f}  ! {lab1}")
        lines.append(f"  {k2[0]:.12f}  {k2[1]:.12f}  {k2[2]:.12f}  ! {lab2}")
        lines.append("")
    write("KPOINTS_band", "\n".join(lines))

    shutil.copyfile(potcar_src, PROJECT / "POTCAR")

    target = PROJECT / "_perf_append.py"
    if not target.exists():
        target.symlink_to(Path("../../_perf_append.py"))

    enmax_lines = [
        line.strip()
        for line in (PROJECT / "POTCAR").read_text(errors="ignore").splitlines()
        if "ENMAX" in line
    ]
    print(f"Wrote VASP inputs in {PROJECT}")
    print(f"POTCAR source: {potcar_src}")
    print("ENMAX lines:")
    for line in enmax_lines[:4]:
        print(line)


if __name__ == "__main__":
    main()
