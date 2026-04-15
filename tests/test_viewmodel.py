import math
from plyfile_viewmodel import ViewModel


def test_append_and_lengths():
    vm = ViewModel()
    vm.append_point(0.0, 0.0)
    vm.append_point(3.0, 4.0)
    vm.append_point(6.0, 8.0)

    lens, total = vm.compute_lengths()
    assert len(lens) == 3
    assert math.isclose(lens[0], 0.0, rel_tol=1e-9)
    assert math.isclose(lens[1], 5.0, rel_tol=1e-9)
    assert math.isclose(lens[2], 5.0, rel_tol=1e-9)
    assert math.isclose(total, 10.0, rel_tol=1e-9)


def test_remove_and_undo_restore_positions():
    vm = ViewModel()
    points = [(0, 0), (1, 0), (2, 0), (3, 0)]
    for x, y in points:
        vm.append_point(x, y)

    # remove middle two (indices 1 and 2)
    removed = vm.remove_points_by_indices([1, 2])
    # after removal only first and last remain
    pts_after = vm.get_points()
    assert len(pts_after) == 2
    assert pts_after[0]["x"] == 0 and pts_after[1]["x"] == 3

    # undo and expect original order restored
    restored = vm.undo_remove()
    pts_restored = vm.get_points()
    assert len(pts_restored) == 4
    assert [p["x"] for p in pts_restored] == [0, 1, 2, 3]
