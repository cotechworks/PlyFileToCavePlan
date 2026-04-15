"""View helpers for PlyFileToCavePlan.

Small UI-agnostic helpers used by the Tk view to keep `plyfile_gui.py`
smaller and to centralize common tree/overlay rebuild tasks.

These helpers intentionally operate on the public API of the tree
widget and the ViewModel so they remain easy to test and reuse.
"""
from typing import List, Dict


def populate_tree_from_vm(tree, vm) -> List[Dict[str, float]]:
    """Clear the given Treeview and populate rows from the ViewModel.

    Returns a list of dicts matching the GUI's `added_points` format:
      [{'x': float, 'y': float, 'item': <tree_item_id>}, ...]
    """
    # clear existing rows
    for item in list(tree.get_children()):
        try:
            tree.delete(item)
        except Exception:
            pass

    pts = vm.get_points() if vm is not None else []
    new_added = []
    for p in pts:
        try:
            item_id = tree.insert("", "end", values=(f"{p['x']:.6f}", f"{p['y']:.6f}", ""))
            new_added.append({"x": p["x"], "y": p["y"], "item": item_id})
        except Exception:
            pass
    return new_added


def points_from_tree(tree):
    """Produce a list of {'x':..., 'y':...} dicts from the Treeview rows.

    Useful when the user reorders rows in the UI and the ViewModel must
    be synchronized with the new ordering.
    """
    pts = []
    for cid in list(tree.get_children()):
        try:
            vals = tree.item(cid, "values")
            if vals and len(vals) >= 2:
                x = float(vals[0])
                y = float(vals[1])
                pts.append({"x": x, "y": y})
        except Exception:
            pass
    return pts
