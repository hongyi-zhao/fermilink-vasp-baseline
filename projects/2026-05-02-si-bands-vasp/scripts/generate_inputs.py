#!/usr/bin/env python3
"""Generate VASP inputs for primitive diamond Si PBE band structure.

Writes all canonical inputs to ../inputs/ relative to scripts/.
"""
import os
import shutil
from pathlib import Path

from pymatgen.core import Lattice, Structure
from pymatgen.io.vasp.inputs import Incar, Kpoints, Poscar
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.symmetry.bandstructure import HighSymmKpath


SCRIPTS = Path(__file__).resolve().parent
PROJECT = SCRIPTS.parent
INPUTS = PROJECT / "inputs"
INPUTS.mkdir(exist_ok=True)
PP_ROOT = Path(os.environ.get("VASP_PP", "/home/werner/Public/hpc/vasp/pot")).expanduser()
POTCAR_SRC = PP_ROOT / "potpaw_PBE.64" / "Si" / "POTCAR"


def primitive_si() -> Structure:
    conventional = Structure.from_spacegroup(
        "Fd-3m",
        Lattice.cubic(5.43),
        ["Si"],
        [[0.0, 0.0, 0.0]],
    )
    return SpacegroupAnalyzer(conventional, symprec=1e-3).get_primitive_standard_structure()


def write_incar_files() -> None:
    common = {
        "SYSTEM": "Si_diamond_PBE_band_vasp",
        "GGA": "PE",
        "ENCUT": 400,
        "EDIFF": 1e-6,
        "NELM": 100,
        "ISMEAR": 0,
        "SIGMA": 0.05,
        "NSW": 0,
        "IBRION": -1,
        "PREC": "Accurate",
        "ALGO": "Fast",
        "LREAL": False,
        "LWAVE": True,
        "KPAR": 2,
        "NCORE": 4,
    }
    scf = dict(common)
    scf.update(
        {
            "ISTART": 0,
            "ICHARG": 2,
            "LCHARG": True,
        }
    )
    band = dict(common)
    band.update(
        {
            "ISTART": 1,
            "ICHARG": 11,
            "ISYM": 0,
            "LCHARG": False,
            "LORBIT": 11,
            "NBANDS": 24,
        }
    )
    Incar(scf).write_file(INPUTS / "INCAR_scf")
    Incar(band).write_file(INPUTS / "INCAR_band")


def write_kpoints_band(structure: Structure) -> None:
    kpath = HighSymmKpath(structure, path_type="setyawan_curtarolo")
    coords = kpath.kpath["kpoints"]
    requested = [
        ("L", coords["L"]),
        ("G", coords["\\Gamma"]),
        ("X", coords["X"]),
        ("W", coords["W"]),
        ("K", coords["K"]),
        ("G", coords["\\Gamma"]),
    ]
    points_per_segment = 36
    with (INPUTS / "KPOINTS_band").open("w") as handle:
        handle.write("Si band path L-G-X-W-K-G, 36 points per segment\n")
        handle.write(f"{points_per_segment}\n")
        handle.write("Line-mode\n")
        handle.write("reciprocal\n")
        for (start_label, start), (end_label, end) in zip(requested[:-1], requested[1:]):
            handle.write(
                f"{start[0]:.10f} {start[1]:.10f} {start[2]:.10f} ! {start_label}\n"
            )
            handle.write(
                f"{end[0]:.10f} {end[1]:.10f} {end[2]:.10f} ! {end_label}\n\n"
            )


def main() -> None:
    if not POTCAR_SRC.exists():
        raise FileNotFoundError(f"Required POTCAR not found: {POTCAR_SRC}")
    structure = primitive_si()
    Poscar(structure, comment="Si diamond primitive cell, a=5.43 Angstrom").write_file(
        INPUTS / "POSCAR"
    )
    Kpoints.gamma_automatic(kpts=(8, 8, 8), shift=(0, 0, 0)).write_file(
        INPUTS / "KPOINTS_scf"
    )
    write_kpoints_band(structure)
    write_incar_files()
    shutil.copyfile(POTCAR_SRC, INPUTS / "POTCAR")
    print(f"Generated VASP inputs in {INPUTS}")
    print(f"POTCAR source: {POTCAR_SRC}")


if __name__ == "__main__":
    main()
