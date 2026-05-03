#!/usr/bin/env python3
"""Analyze VASP Si band output, write band_analysis.json, summary.md, and bands.png.

Reads from canonical subdir layout:
  inputs/KPOINTS_band, inputs/POTCAR
  scf/OUTCAR
  bands/EIGENVAL, bands/OUTCAR, bands/vasprun.xml
  logs/stage_times.tsv
Writes:
  analysis/band_analysis.json, analysis/bands.png
  ../summary.md (project root)
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SCRIPTS = Path(__file__).resolve().parent
PROJECT = SCRIPTS.parent
INPUTS = PROJECT / "inputs"
SCF = PROJECT / "scf"
BANDS = PROJECT / "bands"
ANALYSIS = PROJECT / "analysis"
LOGS = PROJECT / "logs"
ANALYSIS.mkdir(exist_ok=True)

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
    text = (INPUTS / "KPOINTS_band").read_text().splitlines()
    points_per_segment = int(text[1].strip())
    raw: list[np.ndarray] = []
    labels: list[str] = []
    for line in text[4:]:
        clean = line.strip()
        if not clean:
            continue
        before, _bang, after = clean.partition("!")
        raw.append(np.array([float(x) for x in before.split()[:3]], dtype=float))
        labels.append(after.strip() if after else "")

    points: list[np.ndarray] = []
    point_labels: list[str] = []
    for idx in range(0, len(raw), 2):
        start, end = raw[idx], raw[idx + 1]
        start_label, end_label = labels[idx], labels[idx + 1]
        for i in range(points_per_segment):
            t = i / (points_per_segment - 1)
            points.append((1.0 - t) * start + t * end)
            if i == 0:
                point_labels.append(start_label)
            elif i == points_per_segment - 1:
                point_labels.append(end_label)
            else:
                point_labels.append("")
    return points, point_labels, points_per_segment


def cumulative_distances(points: list[np.ndarray]) -> np.ndarray:
    x = [0.0]
    for prev, cur in zip(points[:-1], points[1:]):
        x.append(x[-1] + float(np.linalg.norm(cur - prev)))
    return np.array(x)


def segment_position(k_index: int, points_per_segment: int) -> dict[str, object]:
    seg_index = min(k_index // points_per_segment, len(K_LABELS) - 2)
    within = k_index - seg_index * points_per_segment
    fraction = within / max(points_per_segment - 1, 1)
    start_label = K_LABELS[seg_index][0]
    end_label = K_LABELS[seg_index + 1][0]
    return {"segment": f"{start_label}-{end_label}", "fraction": float(fraction)}


def parse_eigenval() -> tuple[np.ndarray, np.ndarray, int, int, int]:
    lines = (BANDS / "EIGENVAL").read_text(errors="ignore").splitlines()
    nelect, nkpts, nbands = [int(float(v)) for v in lines[5].split()[:3]]
    kpoints: list[list[float]] = []
    bands: list[list[float]] = []
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
    outcar = SCF / "OUTCAR"
    if not outcar.exists():
        return None
    matches = re.findall(
        r"^-+ Iteration\s+\d+\(\s*(\d+)\)",
        outcar.read_text(errors="ignore"),
        flags=re.M,
    )
    return max(int(m) for m in matches) if matches else None


def parse_elapsed(path: Path) -> float | None:
    if not path.exists():
        return None
    match = re.search(r"Elapsed time \(sec\):\s*([\d.]+)", path.read_text(errors="ignore"))
    return float(match.group(1)) if match else None


def parse_enmax() -> float | None:
    match = re.search(r"ENMAX\s*=\s*([\d.]+)", (INPUTS / "POTCAR").read_text(errors="ignore"))
    return float(match.group(1)) if match else None


def parse_stage_times() -> dict[str, dict[str, float | int]]:
    path = LOGS / "stage_times.tsv"
    stages: dict[str, dict[str, float | int]] = {}
    if not path.exists():
        return stages
    for line in path.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name, start, end, status = parts[:4]
        try:
            stages[name] = {
                "elapsed_sec": round(float(end) - float(start), 3),
                "exit": int(status),
            }
        except ValueError:
            pass
    return stages


def maybe_parse_vasprun_band() -> dict[str, object]:
    path = BANDS / "vasprun.xml"
    if not path.exists():
        return {"available": False}
    try:
        root = ET.parse(path).getroot()
        gen = root.find("./generator/i[@name='version']")
        return {
            "available": True,
            "vasp_version": gen.text.strip() if gen is not None and gen.text else None,
        }
    except Exception as exc:
        return {"available": True, "parse_warning": str(exc)}


def maybe_pymatgen_bsvasprun() -> dict[str, object]:
    path = BANDS / "vasprun.xml"
    if not path.exists():
        return {"available": False, "reason": "bands/vasprun.xml not present"}
    try:
        from pymatgen.io.vasp.outputs import BSVasprun

        vr = BSVasprun(str(path), parse_projected_eigen=False)
        bs = vr.get_band_structure(kpoints_filename=str(INPUTS / "KPOINTS_band"), line_mode=True)
        gap = bs.get_band_gap()
        vbm = bs.get_vbm()
        cbm = bs.get_cbm()
        return {
            "available": True,
            "backend": "pymatgen.io.vasp.outputs.BSVasprun",
            "band_gap": gap,
            "vbm_energy_ev": float(vbm["energy"]),
            "cbm_energy_ev": float(cbm["energy"]),
            "vbm_kpoint_label": vbm.get("kpoint").label if vbm.get("kpoint") is not None else None,
            "cbm_kpoint_label": cbm.get("kpoint").label if cbm.get("kpoint") is not None else None,
        }
    except Exception as exc:
        return {"available": False, "reason": f"BSVasprun parse failed: {exc}"}


def write_plot(
    x: np.ndarray,
    energies: np.ndarray,
    labels: list[str],
    vbm_idx: int,
    cbm_idx: int,
    vbm: float,
    gap: float,
    nbands: int,
) -> None:
    tick_positions: list[float] = []
    tick_labels: list[str] = []
    for i, label in enumerate(labels):
        if not label:
            continue
        pretty = r"$\Gamma$" if label == "G" else label
        if tick_positions and abs(float(x[i]) - tick_positions[-1]) < 1e-10:
            if tick_labels[-1] != pretty:
                tick_labels[-1] = f"{tick_labels[-1]}/{pretty}"
        else:
            tick_positions.append(float(x[i]))
            tick_labels.append(pretty)

    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=180)
    for band_idx in range(nbands):
        ax.plot(x, energies[:, band_idx] - vbm, color="#1b4f72", lw=1.0)
    ax.axhline(0.0, color="#2c3e50", lw=0.8, ls="--")
    for xpos in tick_positions:
        ax.axvline(xpos, color="#a6acaf", lw=0.6)
    ax.scatter([x[vbm_idx]], [0.0], s=26, color="#117a65", zorder=5, label="VBM")
    ax.scatter([x[cbm_idx]], [gap], s=26, color="#b03a2e", zorder=5, label="CBM")
    ax.set_xlim(float(x[0]), float(x[-1]))
    ax.set_ylim(-13.0, 10.0)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Energy - VBM (eV)")
    ax.set_title(f"Si diamond PBE VASP band structure, indirect gap = {gap:.3f} eV")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(ANALYSIS / "bands.png")
    plt.close(fig)


def write_summary(analysis: dict[str, object]) -> None:
    vbm = analysis["vbm"]
    cbm = analysis["cbm"]
    status = "done" if analysis["success_criteria_met"] else "failed"
    summary = f"""
- prompt: Compute the electronic band structure of bulk silicon diamond with PBE in VASP 6.6.0 along L-G-X-W-K-G and cross-validate against the QE baseline.
-procedures: Generated VASP inputs in inputs/ for SCF (`8x8x8` Gamma-centered, `ENCUT=400 eV`, `EDIFF=1e-6`, `ISMEAR=0`, `SIGMA=0.05`, `LCHARG=.TRUE.`, `KPAR=2`, `NCORE=4`) and non-SCF band calculation (`ICHARG=11`, `NBANDS=24`, 36 points/segment line-mode `L-G-X-W-K-G` path). Stages run in scf/ and bands/ subdirs with symlinked inputs. Single-node SLURM chain with `oneapi/2024.2.0`, `vasp/6.6.0-oneapi.2024.2.0`, `--nodes=1 --ntasks=8 --cpus-per-task=1`, and Intel MPI `mpirun -np "${{SLURM_NTASKS}}"`.
- generated data: `scf/OUTCAR`, `bands/OUTCAR`, `scf/vasprun.xml`, `bands/vasprun.xml`, `bands/EIGENVAL`, `analysis/band_analysis.json`, `logs/stage_times.tsv`, `analysis/module_list.txt`; SCF electronic iterations = {analysis["scf_iter"]}, indirect gap = {analysis["indirect_gap_ev"]:.6f} eV.
- generated figure: `analysis/bands.png`
- key result: VBM at {vbm["expected_location"] if vbm["is_gamma"] else vbm["path_location"]["segment"]}; CBM on {cbm["path_location"]["segment"]} at fraction {cbm["path_location"]["fraction"]:.6f}; QE reference gap = {QE_GAP_EV:.3f} eV, VASP-QE gap delta = {analysis["gap_delta_vs_qe_ev"]:.6f} eV.
- status: {status}
""".strip()
    if not analysis["success_criteria_met"]:
        summary += (
            f"\n-debugging clue: success criteria failed; gap_in_acceptance_window={analysis['gap_in_acceptance_window']}, "
            f"qualitative_topology_matches_qe={analysis['qualitative_topology_matches_qe']}, "
            f"scf_converged_within_30={analysis['scf_converged_within_30']}."
            "\n-suggested skills updates: add an automatic convergence investigation branch when Si PBE gap falls outside 0.5-0.8 eV or differs from QE by more than 0.1 eV."
        )
    (PROJECT / "summary.md").write_text(summary + "\n")


def main() -> None:
    intended_kpoints, labels, points_per_segment = read_kpoints_band()
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
    vbm_energy = float(vbm_by_k[vbm_idx])
    cbm_energy = float(cbm_by_k[cbm_idx])
    gap = cbm_energy - vbm_energy

    write_plot(x, energies, labels, vbm_idx, cbm_idx, vbm_energy, gap, nbands)
    scf_iter = parse_scf_iterations()
    enmax = parse_enmax()
    cbm_path = segment_position(cbm_idx, points_per_segment)
    vbm_path = segment_position(vbm_idx, points_per_segment)
    vbm_is_gamma = bool(np.linalg.norm(eigen_kpoints[vbm_idx]) < 1e-6)
    gap_in_window = bool(0.5 <= gap <= 0.8)
    topology_matches = bool(vbm_is_gamma and cbm_path["segment"] == "G-X" and 0.70 <= cbm_path["fraction"] <= 0.95)

    analysis = {
        "parsed_source": "EIGENVAL",
        "vasprun_band": maybe_parse_vasprun_band(),
        "pymatgen_bsvasprun": maybe_pymatgen_bsvasprun(),
        "n_kpoints": int(nkpts),
        "n_bands": int(nbands),
        "nelect": int(nelect),
        "occupied_bands_assumed": OCC_BANDS,
        "points_per_segment": points_per_segment,
        "vbm": {
            "energy_ev": vbm_energy,
            "band_index_1based": vband + 1,
            "k_index_1based": vbm_idx + 1,
            "x": float(x[vbm_idx]),
            "fractional_kpoint": [float(v) for v in eigen_kpoints[vbm_idx]],
            "expected_location": "Gamma",
            "is_gamma": vbm_is_gamma,
            "path_location": vbm_path,
        },
        "cbm": {
            "energy_ev": cbm_energy,
            "band_index_1based": cband + 1,
            "k_index_1based": cbm_idx + 1,
            "x": float(x[cbm_idx]),
            "fractional_kpoint": [float(v) for v in eigen_kpoints[cbm_idx]],
            "expected_location": "near 0.85 of Gamma-X",
            "path_location": cbm_path,
        },
        "indirect_gap_ev": gap,
        "acceptance_window_ev": [0.5, 0.8],
        "gap_in_acceptance_window": gap_in_window,
        "qe_baseline_gap_ev": QE_GAP_EV,
        "gap_delta_vs_qe_ev": gap - QE_GAP_EV,
        "gap_delta_abs_vs_qe_ev": abs(gap - QE_GAP_EV),
        "qualitative_topology_matches_qe": topology_matches,
        "scf_iter": scf_iter,
        "scf_converged_within_30": scf_iter is not None and scf_iter <= 30,
        "walltime_sec": {
            "stage_times": parse_stage_times(),
            "scf_outcar_elapsed": parse_elapsed(SCF / "OUTCAR"),
            "band_outcar_elapsed": parse_elapsed(BANDS / "OUTCAR"),
        },
        "encut_ev": 400.0,
        "potcar_enmax_ev": enmax,
        "encut_over_enmax": 400.0 / enmax if enmax else None,
        "plot": "analysis/bands.png",
    }
    analysis["success_criteria_met"] = bool(
        analysis["gap_in_acceptance_window"]
        and analysis["qualitative_topology_matches_qe"]
        and analysis["scf_converged_within_30"]
    )
    (ANALYSIS / "band_analysis.json").write_text(json.dumps(analysis, indent=2) + "\n")
    write_summary(analysis)
    print(json.dumps(analysis, indent=2))
    if not analysis["success_criteria_met"]:
        raise SystemExit("VASP Si band success criteria were not met")


if __name__ == "__main__":
    main()
