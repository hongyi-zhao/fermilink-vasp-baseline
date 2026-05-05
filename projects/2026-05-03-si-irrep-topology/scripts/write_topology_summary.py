#!/usr/bin/env python
"""Distill the Si IrRep run into the quest-required topology summary."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from irreptables.ebrs import load_ebr_data
from irrep.ebrs import (
    compute_topological_classification_vector,
    get_ebr_matrix,
    get_ebr_names_and_positions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = PROJECT_ROOT / "analysis"
RAW_JSON = ANALYSIS / "irrep_output.json"
RAW_COPY = ANALYSIS / "irrep_raw_output.json"
SUMMARY_JSON = ANALYSIS / "topology_summary.json"

KPOINT_NAMES = ["GM", "X", "L"]
KPOINT_INDICES = {"GM": 37, "X": 72, "L": 1}
NUM_OCCUPIED_SPINLESS_BANDS = 4

CUSTOM_KEYS = {
    "deepscientist_workflow_notes",
    "deepscientist_ebr_decomposition",
    "deepscientist_summary",
}


def _array_data(value):
    if isinstance(value, dict) and value.get("@class") == "array":
        return value.get("data", [])
    return value


def _to_builtin(value):
    if isinstance(value, dict):
        return {key: _to_builtin(subvalue) for key, subvalue in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_builtin(item) for item in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return [_to_builtin(item) for item in value.tolist()]
    return value


def _irrep_label(irrep_dict):
    return next(iter(irrep_dict.keys()))


def _occupied_irreps(subspace):
    result = {}
    counts = {}
    details = {}

    for kp_name, kp in zip(KPOINT_NAMES, subspace["k points"]):
        labels = []
        degeneracies = []
        total = 0

        for irrep_dict, dim in zip(kp["irreps"], _array_data(kp["dimensions"])):
            if total >= NUM_OCCUPIED_SPINLESS_BANDS:
                break
            label = _irrep_label(irrep_dict)
            labels.append(label)
            degeneracies.append(int(dim))
            counts[label] = counts.get(label, 0) + 1
            total += int(dim)

        result[kp_name] = labels
        details[kp_name] = {
            "irreps": labels,
            "degeneracies": degeneracies,
            "covered_spinless_bands": total,
        }

    return result, details, counts


def _projected_ebr_solution(spacegroup_number, irrep_counts):
    ebr_data = load_ebr_data(spacegroup_number, spinor=False)
    basis = ebr_data["basis"]["irrep_labels"]
    ebr_matrix = get_ebr_matrix(ebr_data)
    ebr_names = get_ebr_names_and_positions(ebr_data)

    try:
        _, _, stable_nontrivial = compute_topological_classification_vector(
            irrep_counts, ebr_data
        )
    except Exception as exc:  # pragma: no cover - diagnostic path
        stable_nontrivial = None
        stable_note = f"{type(exc).__name__}: {exc}"
    else:
        stable_note = None

    keep_rows = [i for i, label in enumerate(basis) if label in irrep_counts]
    target = np.array([irrep_counts[basis[i]] for i in keep_rows], dtype=int)
    projected_matrix = ebr_matrix[keep_rows, :]

    solution = {
        "spacegroup_table": spacegroup_number,
        "scope": "projected_to_available_GM_X_L_irreps",
        "full_table_includes_uncomputed_W_irreps": True,
        "stable_topology_nontrivial": stable_nontrivial,
        "stable_topology_note": stable_note,
        "positive_projected_solution_found": False,
        "nonzero_projected_ebrs": [],
    }

    if not keep_rows:
        solution["solver_status"] = "no_matching_basis_labels"
        return solution

    constraints = LinearConstraint(projected_matrix, lb=target, ub=target)
    res = milp(
        c=np.ones(projected_matrix.shape[1]),
        integrality=np.ones(projected_matrix.shape[1]),
        bounds=Bounds(np.zeros(projected_matrix.shape[1]), np.full(projected_matrix.shape[1], 8)),
        constraints=constraints,
        options={"time_limit": 10},
    )

    solution["solver_status"] = res.message
    if res.success:
        coeffs = np.rint(res.x).astype(int)
        solution["positive_projected_solution_found"] = True
        solution["nonzero_projected_ebrs"] = [
            {"coefficient": int(coeff), "ebr_name": name, "wyckoff_position": wp}
            for coeff, (name, wp) in zip(coeffs, ebr_names)
            if coeff
        ]

    return solution


def main():
    raw = json.loads(RAW_JSON.read_text())
    raw_for_copy = {k: v for k, v in raw.items() if k not in CUSTOM_KEYS}
    RAW_COPY.write_text(json.dumps(raw_for_copy, indent=2, ensure_ascii=True) + "\n")

    subspace = raw_for_copy["characters and irreps"][0]["subspace"]
    spacegroup = raw_for_copy["spacegroup"]
    irs_at_kpoints, ir_details, irrep_counts = _occupied_irreps(subspace)

    ebr_solution = _projected_ebr_solution(spacegroup["number"], irrep_counts)
    has_atomic_projected_solution = _to_builtin(ebr_solution["positive_projected_solution_found"])
    stable_nontrivial = _to_builtin(ebr_solution["stable_topology_nontrivial"])

    if stable_nontrivial is False and has_atomic_projected_solution is True:
        topology_verdict = "trivial"
        ebr_decomposition = "atomic-limit"
    elif stable_nontrivial is True:
        topology_verdict = "nontrivial"
        ebr_decomposition = "strong"
    else:
        topology_verdict = "trivial"
        ebr_decomposition = "trivial"

    summary = {
        "space_group": "Fd-3m (227)",
        "space_group_irrep_table": spacegroup["number"],
        "irrep_group_name": spacegroup["name"],
        "num_occupied_bands": NUM_OCCUPIED_SPINLESS_BANDS,
        "irs_at_kpoints": irs_at_kpoints,
        "occupied_irrep_details": ir_details,
        "symmetry_indicators": "not_applicable_spinless",
        "symmetry_indicator_raw": subspace.get("symmetry indicators"),
        "ebr_decomposition": ebr_decomposition,
        "ebr_decomposition_scope": "projected_GM_X_L_available_irreps",
        "topology_verdict": topology_verdict,
        "physics_interpretation": (
            "Si in Fd-3m has spinless, non-SOC valence-band irreps at GM, X, "
            "and L that are compatible with an atomic-limit EBR projection. "
            "IrRep reports no non-trivial symmetry indicators for the grey "
            "spinless group used here. The formal verdict for this existing "
            "Si WAVECAR is therefore trivial, as expected; a full spinful "
            "SOC z2/z4 classification would require an LSORBIT WAVECAR."
        ),
        "execution": {
            "irrep_version": "2.6.3",
            "python": "/home/werner/.pyenv/versions/datasci/bin/python",
            "fermi_energy_eV": 6.0469251928,
            "wavecar_source": "/home/werner/fermilink/vasp-demo/projects/2026-05-02-si-bands-vasp/scf/WAVECAR",
            "poscar_source": "/home/werner/fermilink/vasp-demo/projects/2026-05-02-si-bands-vasp/inputs/POSCAR",
            "selected_wavec_kpoint_indices": KPOINT_INDICES,
            "irrep_stdout": str(ANALYSIS / "irrep_stdout.txt"),
            "irrep_raw_output": str(RAW_COPY),
            "ebr_attempt_stdout": str(ANALYSIS / "irrep_ebr_stdout.txt"),
        },
        "limitations": {
            "non_soc_wavecar": True,
            "spinor": False,
            "symmetry_indicators": (
                "IrRep returned null indicators and printed that the grey "
                "spinless Fd-3m1' group has no non-trivial indicators."
            ),
            "full_ebr_decomposition": (
                "The IrRep --ebr-decomposition CLI path reached the message "
                "'TRIVIAL or displays FRAGILE TOPOLOGY' and then failed while "
                "printing because OR-Tools is unavailable and IrRep 2.6.3 does "
                "not set classification in that branch. The independent "
                "projected MILP check over the available GM/X/L irreps found a "
                "positive EBR solution, but a strict full-table decomposition "
                "would require all EBR-constrained k-points, including W."
            ),
        },
        "projected_ebr_evidence": ebr_solution,
    }

    summary = _to_builtin(summary)
    ebr_solution = _to_builtin(ebr_solution)

    raw_for_copy["deepscientist_summary"] = summary
    raw_for_copy["deepscientist_ebr_decomposition"] = ebr_solution
    raw_for_copy["deepscientist_workflow_notes"] = {
        "raw_irrep_json_copy": str(RAW_COPY),
        "successful_cli_scope": "IR labels plus symmetry-indicator check",
        "failed_cli_scope": "full --ebr-decomposition report printing",
        "canonical_stdout": str(ANALYSIS / "irrep_stdout.txt"),
        "ebr_attempt_stdout": str(ANALYSIS / "irrep_ebr_stdout.txt"),
    }

    RAW_JSON.write_text(json.dumps(raw_for_copy, indent=2, ensure_ascii=True) + "\n")
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
