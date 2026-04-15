"""ViewModel for PlyFileToCavePlan.

Contains point-manipulation logic (add/remove/move/undo) and length calculations.
This is intentionally UI-agnostic: it manages an ordered list of (x,y) points
and a removal history for undo.
"""

from typing import List, Tuple, Dict, Optional


class ViewModel:
    """Simple in-memory viewmodel for point operations.

    Data shape:
      - points: list[dict] each {'x': float, 'y': float}
      - remove_history: list of lists of tuples (index, point)
    """

    def __init__(self) -> None:
        self.points: List[Dict[str, float]] = []
        self.remove_history: List[List[Tuple[int, Dict[str, float]]]] = []

    def get_points(self) -> List[Dict[str, float]]:
        return list(self.points)

    def set_points(self, pts: List[Dict[str, float]]) -> None:
        self.points = [dict(p) for p in pts]

    def append_point(self, x: float, y: float) -> int:
        """Append point and return its index."""
        self.points.append({"x": float(x), "y": float(y)})
        return len(self.points) - 1

    def insert_point_at(self, index: int, x: float, y: float) -> None:
        if index < 0:
            index = 0
        if index >= len(self.points):
            self.points.append({"x": float(x), "y": float(y)})
        else:
            self.points.insert(index, {"x": float(x), "y": float(y)})

    def remove_points_by_indices(self, indices: List[int]) -> List[Tuple[int, Dict[str, float]]]:
        """Remove points at the given indices (indices must be sorted ascending).

        Returns list of removed (index, point) tuples and records them to history.
        """
        if not indices:
            return []
        removed: List[Tuple[int, Dict[str, float]]] = []
        # remove from highest index to lowest to avoid shifting
        for idx in sorted(indices, reverse=True):
            if 0 <= idx < len(self.points):
                pt = self.points.pop(idx)
                removed.append((idx, pt))
        # store in history as ascending-order list for easier undo
        removed = list(reversed(removed))
        if removed:
            self.remove_history.append(removed)
        return removed

    def undo_remove(self) -> Optional[List[Tuple[int, Dict[str, float]]]]:
        """Undo the last removal. Returns list of reinserted (index, point) tuples or None."""
        if not self.remove_history:
            return None
        last = self.remove_history.pop()
        # last is list of (index, point) in ascending index order; insert in order
        for idx, pt in last:
            if idx >= len(self.points):
                self.points.append(pt)
            else:
                self.points.insert(idx, pt)
        return last

    def move_indices_up(self, indices: List[int]) -> None:
        """Move selected indices up by one position (in-place)."""
        if not indices:
            return
        children = list(range(len(self.points)))
        for i in sorted(indices):
            if i <= 0 or i >= len(self.points):
                continue
            # swap i with i-1
            self.points[i - 1], self.points[i] = self.points[i], self.points[i - 1]

    def move_indices_down(self, indices: List[int]) -> None:
        """Move selected indices down by one position (in-place)."""
        if not indices:
            return
        for i in sorted(indices, reverse=True):
            if i < 0 or i >= len(self.points) - 1:
                continue
            self.points[i + 1], self.points[i] = self.points[i], self.points[i + 1]

    def compute_lengths(self) -> Tuple[List[float], float]:
        """Compute per-segment lengths and total horizontal distance.

        Returns (lengths, total) where lengths is a list of length N with
        lengths[0] == 0.0 and lengths[i] is distance between points i-1 and i.
        """
        n = len(self.points)
        if n == 0:
            return [], 0.0
        lens = [0.0] * n
        total = 0.0
        for i in range(1, n):
            dx = self.points[i]["x"] - self.points[i - 1]["x"]
            dy = self.points[i]["y"] - self.points[i - 1]["y"]
            d = (dx * dx + dy * dy) ** 0.5
            lens[i] = d
            total += d
        return lens, total
