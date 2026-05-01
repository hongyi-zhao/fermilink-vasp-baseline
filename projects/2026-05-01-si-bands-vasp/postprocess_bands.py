#!/usr/bin/env python3
"""Parse VASP Si band outputs, report gap metrics, and plot bands."""
from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT = Path(__file__).resolve().parent
NELECT = 8
OCC_BANDS = NELECT // 2
QE_GAP_EV = 0.575

K_LABELS = [
    ("L", np.array([0.5, 0.5, 0.5])),
    ("G", np.array([0.0, 0.0, 0.0])),
    ("X", np.array([0.5, 0.0, 0.5])),
    ("W", np.array([0.5, 0.25, 0.75])),
    ("K", np.array([0.375, 0.375, 0.75])),
    ("G", np.array([0.0, 0.0, 0.0])),
]


def read_kpoints_band() -> tuple[list[np.ndarray], list[str], int]:
    text = (PROJECT / "KPOINTS_band").read_text().splitlines()
    n_per_segment = int(text[1].strip())
    raw = []
    labels = []
    for line in text[4:]:
        clean = line.strip()
        if not clean:
            continue
        before, _, after = clean.partition("!")
        vals = [float(x) for x in before.split()[:3]]
        raw.append(np.array(vals, dtype=float))
        labels.append(after.strip() if after else "")
    points = []
    point_labels = []
    for idx in range(0, len(raw), 2):
        start, end = raw[idx], raw[idx + 1]
        lab_start, lab_end = labels[idx], labels[idx + 1]
        for i in range(n_per_segment):
            t = i / (n_per_segment - 1)
            points.append((1.0 - t) * start + t * end)
            if i == 0:
                point_labels.append(lab_start)
            elif i == n_per_segment - 1:
                point_labels.append(lab_end)
            else:
                point_labels.append("")
    return points, point_labels, n_per_segment


def cumulative_distances(points: list[np.ndarray]) -> np.ndarray:
    x = [0.0]
    for prev, cur in zip(points[:-1], points[1:]):
        step = float(np.linalg.norm(cur - prev))
        x.append(x[-1] + step)
    return np.array(x)


def segment_position(k_index: int, n_per_segment: int) -> dict:
    seg_index = min(k_index // n_per_segment, len(K_LABELS) - 2)
    within = k_index - seg_index * n_per_segment
    denom = max(n_per_segment - 1, 1)
    start_label = K_LABELS[seg_index][0]
    end_label = K_LABELS[seg_index + 1][0]
    return {
        "segment": f"{start_label}-{end_label}",
        "fraction": float(within / denom),
    }


def parse_eigenval() -> tuple[np.ndarray, np.ndarray, int, int, int]:
    path = PROJECT / "EIGENVAL"
    lines = path.read_text(errors="ignore").splitlines()
    nelect, nkpts, nbands = [int(float(v)) for v in lines[5].split()[:3]]
    kpoints = []
    bands = []
    i = 6
    for _ in range(nkpts):
        while i < len(lines) and not lines[i].strip():
            i += 1
        fields = lines[i].split()
        kpoints.append([float(fields[0]), float(fields[1]), float(fields[2])])
        i += 1
        one_k = []
        for _band in range(nbands):
            parts = lines[i].split()
            one_k.append(float(parts[1]))
            i += 1
        bands.append(one_k)
    return np.array(kpoints), np.array(bands), nelect, nkpts, nbands


def parse_scf_iterations() -> int | None:
    outcar = PROJECT / "OUTCAR_scf"
    if not outcar.exists():
        return None
    text = outcar.read_text(errors="ignore")
    matches = re.findall(r"^-+ Iteration\s+\d+\(\s*(\d+)\)", text, flags=re.M)
    if not matches:
        return None
    return max(int(m) for m in matches)


def parse_elapsed(path: Path) -> float | None:
    if not path.exists():
        return None
    text = path.read_text(errors="ignore")
    m = re.search(r"Elapsed time \(sec\):\s*([\d.]+)", text)
    return float(m.group(1)) if m else None


def parse_enmax() -> float | None:
    potcar = PROJECT / "POTCAR"
    if not potcar.exists():
        return None
    m = re.search(r"ENMAX\s*=\s*([\d.]+)", potcar.read_text(errors="ignore"))
    return float(m.group(1)) if m else None


def maybe_parse_vasprun_band() -> dict:
    path = PROJECT / "vasprun_band.xml"
    if not path.exists():
        return {"available": False}
    try:
        root = ET.parse(path).getroot()
        gen = root.find("./generator/i[@name='version']")
        return {"available": True, "vasp_version": gen.text.strip() if gen is not None and gen.text else None}
    except Exception as exc:
        return {"available": True, "parse_warning": str(exc)}


def maybe_pymatgen_bsvasprun() -> dict:
    path = PROJECT / "vasprun_band.xml"
    if not path.exists():
        return {"available": False, "reason": "vasprun_band.xml not present"}
    try:
        from pymatgen.electronic_structure.core import Spin
        from pymatgen.io.vasp.outputs import BSVasprun
    except Exception as exc:
        return {"available": False, "reason": f"pymatgen import failed: {exc}"}
    try:
        vr = BSVasprun(str(path), parse_projected_eigen=False)
        bs = vr.get_band_structure(kpoints_filename=str(PROJECT / "KPOINTS_band"), line_mode=True)
        vbm = bs.get_vbm()
        cbm = bs.get_cbm()
        gap = bs.get_band_gap()
        return {
            "available": True,
            "backend": "pymatgen.io.vasp.outputs.BSVasprun",
            "vbm_energy_ev": float(vbm["energy"]),
            "cbm_energy_ev": float(cbm["energy"]),
            "band_gap": gap,
            "vbm_kpoint_label": vbm.get("kpoint").label if vbm.get("kpoint") is not None else None,
            "cbm_kpoint_label": cbm.get("kpoint").label if cbm.get("kpoint") is not None else None,
            "spin_channels": [str(spin) for spin in bs.bands.keys()] or [str(Spin.up)],
        }
    except Exception as exc:
        return {"available": False, "reason": f"BSVasprun parse failed: {exc}"}


def main() -> None:
    intended_kpoints, labels, n_per_segment = read_kpoints_band()
    eigen_kpoints, energies, nelect, nkpts, nbands = parse_eigenval()
    if nkpts != len(intended_kpoints):
        raise ValueError(f"KPOINTS_band implies {len(intended_kpoints)} k-points, EIGENVAL has {nkpts}")

    x = cumulative_distances(intended_kpoints)
    vband = OCC_BANDS - 1
    cband = OCC_BANDS
    vbm_by_k = energies[:, vband]
    cbm_by_k = energies[:, cband]
    vbm_idx = int(np.argmax(vbm_by_k))
    cbm_idx = int(np.argmin(cbm_by_k))
    vbm = float(vbm_by_k[vbm_idx])
    cbm = float(cbm_by_k[cbm_idx])
    gap = cbm - vbm

    tick_positions = []
    tick_labels = []
    for i, lab in enumerate(labels):
        if lab:
            pretty = r"$\Gamma$" if lab == "G" else lab
            if tick_positions and abs(x[i] - tick_positions[-1]) < 1e-10:
                if tick_labels[-1] != pretty:
                    tick_labels[-1] = tick_labels[-1] + "/" + pretty
            else:
                tick_positions.append(float(x[i]))
                tick_labels.append(pretty)

    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=180)
    for b in range(nbands):
        ax.plot(x, energies[:, b] - vbm, color="#1b4f72", lw=1.1)
    ax.axhline(0.0, color="#2c3e50", lw=0.8, ls="--")
    for xp in tick_positions:
        ax.axvline(xp, color="#a6acaf", lw=0.6)
    ax.scatter([x[vbm_idx]], [0.0], s=26, color="#117a65", zorder=5, label="VBM")
    ax.scatter([x[cbm_idx]], [gap], s=26, color="#b03a2e", zorder=5, label="CBM")
    ax.set_xlim(float(x[0]), float(x[-1]))
    ymin = max(-8.0, float(np.min(energies - vbm)) - 0.4)
    ymax = min(8.0, float(np.max(energies - vbm)) + 0.4)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Energy - VBM (eV)")
    ax.set_title(f"Si diamond PBE VASP band structure, indirect gap = {gap:.3f} eV")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(PROJECT / "bands.png")
    plt.close(fig)

    vbm_segment = segment_position(vbm_idx, n_per_segment)
    cbm_segment = segment_position(cbm_idx, n_per_segment)
    cbm_on_gamma_x = cbm_segment["segment"] == "G-X"
    cbm_near_expected_fraction = cbm_on_gamma_x and 0.70 <= cbm_segment["fraction"] <= 0.95

    analysis = {
        "parsed_source": "EIGENVAL",
        "pymatgen_bsvasprun": maybe_pymatgen_bsvasprun(),
        "vasprun_band": maybe_parse_vasprun_band(),
        "n_kpoints": int(nkpts),
        "n_bands": int(nbands),
        "nelect": int(nelect),
        "occupied_bands_assumed": OCC_BANDS,
        "points_per_segment": n_per_segment,
        "vbm": {
            "energy_ev": vbm,
            "band_index_1based": vband + 1,
            "k_index_1based": vbm_idx + 1,
            "x": float(x[vbm_idx]),
            "fractional_kpoint": [float(v) for v in eigen_kpoints[vbm_idx]],
            "path_segment": vbm_segment["segment"],
            "path_segment_fraction": vbm_segment["fraction"],
            "expected_location": "Gamma",
            "is_gamma": bool(np.linalg.norm(eigen_kpoints[vbm_idx]) < 1e-6),
        },
        "cbm": {
            "energy_ev": cbm,
            "band_index_1based": cband + 1,
            "k_index_1based": cbm_idx + 1,
            "x": float(x[cbm_idx]),
            "fractional_kpoint": [float(v) for v in eigen_kpoints[cbm_idx]],
            "path_segment": cbm_segment["segment"],
            "path_segment_fraction": cbm_segment["fraction"],
            "expected_location": "near 0.85 of Gamma-X",
            "on_gamma_x": bool(cbm_on_gamma_x),
            "near_expected_fraction": bool(cbm_near_expected_fraction),
        },
        "indirect_gap_ev": gap,
        "acceptance_window_ev": [0.5, 0.8],
        "gap_in_acceptance_window": bool(0.5 <= gap <= 0.8),
        "qe_baseline_gap_ev": QE_GAP_EV,
        "gap_delta_vs_qe_ev": gap - QE_GAP_EV,
        "gap_delta_abs_vs_qe_ev": abs(gap - QE_GAP_EV),
        "qualitative_topology_matches_qe": bool(
            np.linalg.norm(eigen_kpoints[vbm_idx]) < 1e-6
            and cbm_near_expected_fraction
            and abs(gap - QE_GAP_EV) <= 0.1
            and 0.5 <= gap <= 0.8
        ),
        "scf_iter": parse_scf_iterations(),
        "scf_converged_within_30": (
            parse_scf_iterations() is not None and parse_scf_iterations() <= 30
        ),
        "walltime_sec": {
            "scf_outcar_elapsed": parse_elapsed(PROJECT / "OUTCAR_scf"),
            "band_outcar_elapsed": parse_elapsed(PROJECT / "OUTCAR_band"),
        },
        "encut_ev": 400.0,
        "potcar_enmax_ev": parse_enmax(),
        "encut_over_enmax": 400.0 / parse_enmax() if parse_enmax() else None,
        "plot": "bands.png",
    }
    (PROJECT / "band_analysis.json").write_text(json.dumps(analysis, indent=2) + "\n")
    print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    main()
