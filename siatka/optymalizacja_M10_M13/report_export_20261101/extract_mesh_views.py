"""Read existing CGNS files and export real mesh edges; never opens STAR.

Run on THINKPAD-LUCJAN with the existing Python 3.12 audit interpreter.
Only a new report-export folder is written. The original CGNS files are read-only.
"""
from __future__ import annotations
import argparse, base64, ctypes, datetime, gc, hashlib, io, json, os, sys, zipfile
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
sys.path.insert(0, r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\.deps")
import numpy as np
import h5py

parser = argparse.ArgumentParser()
parser.add_argument("--output", default=r"E:\ntnu_mesh_optimization_20261030\report_export_20261101\mesh_views")
parser.add_argument("--hash-sources", action="store_true")
args = parser.parse_args()
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)

if os.name == "nt":
    # Keep file-only post-processing subordinate to the external calculation.
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)

archive = Path(r"F:\ntnu\mesh_screening_20261028\quasi2d_012_20261029")
study = Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
sources = {f"M{i:02}": archive / f"M{i:02}" / "mesh.CGNS" for i in range(1, 10)}
sources.update({
    "M10": study / "handoff" / "mesh_star_export.CGNS",
    "M11": study / "G10_M" / "mesh.CGNS",
    "M12": study / "G10_F" / "mesh.CGNS",
    "M13": Path(r"E:\ntnu_mesh_optimization_20261030\M13_farfield15_20261031\geometry\mesh.CGNS"),
})

def atomic_bytes(path: Path, payload: bytes) -> None:
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def find_zone(f):
    zones = []
    f.visititems(lambda n, o: zones.append(o) if isinstance(o, h5py.Group) and "GridCoordinates" in o else None)
    if len(zones) != 1:
        raise ValueError(f"Expected one CGNS zone, received {len(zones)}")
    return zones[0]

def read_zone(source: Path):
    with h5py.File(source, "r") as f:
        zone = find_zone(f)
        coords = np.column_stack([zone[f"GridCoordinates/Coordinate{axis}/ data"][...] for axis in ("X", "Z")])
        group = zone["Q2D_span_source"]
        offsets = group["ElementStartOffset/ data"][...].astype(np.int64)
        connectivity = group["ElementConnectivity/ data"][...].astype(np.int64) - 1
        if offsets[0] != 0 or offsets[-1] != len(connectivity) or np.any(np.diff(offsets) < 3):
            raise ValueError("Invalid source-face polygon connectivity")
        wall_names = [n for n in zone if "HF_012" in n and "wall" in n.lower()]
        if "HF_012_wall" in zone:
            wall_names = ["HF_012_wall"]
        if len(wall_names) != 1:
            raise ValueError(f"Unambiguous physical foil wall not found: {wall_names}")
        wall = zone[wall_names[0]]["ElementConnectivity/ data"][...].astype(np.int64) - 1
        wall_points = coords[wall]
        bounds = np.r_[wall_points.min(axis=0), wall_points.max(axis=0)]
        return coords, offsets, connectivity, wall_points, bounds

# All crops are fixed by M10's actual physical foil bounds, then reused unchanged.
ref_coords, ref_offsets, ref_con, ref_wall, ref_bounds = read_zone(sources["M10"])
xlo, zlo, xhi, zhi = [float(v) for v in ref_bounds]
panels = {
    "near_foil": {"title": "Foil and near field", "bounds": [xlo - 0.15, xhi + 0.20, zlo - 0.15, zhi + 0.15]},
    "leading_edge": {"title": "Leading edge", "bounds": [xlo - 0.025, xlo + 0.12, zlo - 0.015, zhi + 0.015]},
    "trailing_edge": {"title": "Trailing edge", "bounds": [xhi - 0.12, xhi + 0.035, zlo - 0.015, zhi + 0.015]},
    "free_surface": {"title": "Free-surface band", "bounds": [-0.20, 0.20, 1.85, 2.15]},
    "domain": {"title": "Domain and local refinement", "bounds": [-40.0, 50.0, -25.0, 10.0]},
}
del ref_coords, ref_offsets, ref_con, ref_wall
gc.collect()

manifest = {
    "created_at": datetime.datetime.now().astimezone().isoformat(),
    "method": "Unmodified X/Z coordinates and actual Q2D_span_source CGNS polygon edges. Shared physical crops defined from M10. No interpolation or synthetic grid.",
    "panels": panels,
    "reference_foil_bounds_xz_min_max": ref_bounds.tolist(),
    "entries": [],
    "flow_steps": 0,
    "source_files_modified": False,
}

def overlaps(minima, maxima, bounds):
    xl, xh, zl, zh = bounds
    return (maxima[:, 0] >= xl) & (minima[:, 0] <= xh) & (maxima[:, 1] >= zl) & (minima[:, 1] <= zh)

for name, source in sources.items():
    entry = {"mesh": name, "source": str(source), "status": "pending"}
    try:
        stat_before = source.stat()
        coords, offsets, connectivity, wall_points, foil_bounds = read_zone(source)
        polygon_points = coords[connectivity]
        minima = np.minimum.reduceat(polygon_points, offsets[:-1], axis=0)
        maxima = np.maximum.reduceat(polygon_points, offsets[:-1], axis=0)
        del polygon_points
        mask = np.zeros(len(offsets) - 1, dtype=bool)
        for key, panel in panels.items():
            if key != "domain":
                mask |= overlaps(minima, maxima, panel["bounds"])
        ids = np.flatnonzero(mask)
        pair_chunks = []
        for i in ids:
            nodes = connectivity[offsets[i]:offsets[i + 1]]
            pair_chunks.append(np.column_stack((nodes, np.roll(nodes, -1))))
        pairs = np.concatenate(pair_chunks, axis=0)
        pairs.sort(axis=1)
        pairs = np.unique(pairs, axis=0)
        edges = coords[pairs]
        edge_min = edges.min(axis=1)
        edge_max = edges.max(axis=1)
        arrays = {"foil_wall_points": wall_points, "foil_bounds": foil_bounds}
        for key, panel in panels.items():
            if key != "domain":
                arrays[key + "_edges"] = edges[overlaps(edge_min, edge_max, panel["bounds"])]
        # A sparse selection is not a whole-domain mesh: omit rather than mislabel.
        buffer = io.BytesIO()
        np.savez_compressed(buffer, **arrays)
        output = out / f"{name}_actual_edges.npz"
        atomic_bytes(output, buffer.getvalue())
        stat_after = source.stat()
        if stat_before.st_size != stat_after.st_size or stat_before.st_mtime_ns != stat_after.st_mtime_ns:
            raise ValueError("CGNS source identity changed during read")
        entry.update({
            "status": "exported",
            "source_size_bytes": stat_before.st_size,
            "source_mtime_ns": stat_before.st_mtime_ns,
            "source_sha256": digest(source) if args.hash_sources else None,
            "source_identity_check": "Size and modification time unchanged during read",
            "cells": int(len(offsets) - 1),
            "foil_bounds_xz_min_max": foil_bounds.tolist(),
            "max_foil_bounds_difference_from_M10_m": float(np.max(np.abs(foil_bounds - ref_bounds))),
            "npz_file": output.name,
            "npz_sha256": digest(output),
            "unique_selected_edges": int(len(edges)),
            "panel_edge_counts": {k: int(len(v)) for k, v in arrays.items() if k.endswith("_edges")},
        })
        print(json.dumps({"mesh": name, "cells": entry["cells"], "npz_bytes": output.stat().st_size, "status": "exported"}), flush=True)
        del coords, offsets, connectivity, wall_points, minima, maxima, pairs, pair_chunks, edges, arrays
        gc.collect()
    except Exception as exc:
        entry.update(status="missing", error=f"{type(exc).__name__}: {exc}")
        print(json.dumps({"mesh": name, "status": "missing", "error": entry["error"]}), flush=True)
    manifest["entries"].append(entry)
    atomic_bytes(out / "mesh_edges_provenance.json", json.dumps(manifest, indent=2).encode())

zip_path = out / "mesh_actual_edges.zip"
tmp_zip = out / (zip_path.name + f".{os.getpid()}.tmp")
with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_STORED) as bundle:
    for entry in manifest["entries"]:
        if entry["status"] == "exported":
            bundle.write(out / entry["npz_file"], entry["npz_file"])
    bundle.write(out / "mesh_edges_provenance.json", "mesh_edges_provenance.json")
os.replace(tmp_zip, zip_path)
encoded = base64.b64encode(zip_path.read_bytes()).decode("ascii")
chunk_length = 48000
b64_path = out / "mesh_actual_edges.b64"
atomic_bytes(b64_path, ("\n".join(encoded[i:i + chunk_length] for i in range(0, len(encoded), chunk_length)) + "\n").encode("ascii"))
print(json.dumps({"zip_path": str(zip_path), "zip_bytes": zip_path.stat().st_size, "b64_path": str(b64_path), "b64_lines": (len(encoded) + chunk_length - 1) // chunk_length, "exported": sum(e["status"] == "exported" for e in manifest["entries"])}), flush=True)
