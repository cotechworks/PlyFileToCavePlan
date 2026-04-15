import sys
sys.path.insert(0, r'D:\SynologyDrive\Document\SoftwareDevelopment\Python\PlyFileToCavePlan')
from tests import test_viewmodel as tv

if __name__ == '__main__':
    try:
        tv.test_append_and_lengths()
        tv.test_remove_and_undo_restore_positions()
        print('ALL TESTS PASSED')
    except Exception:
        import traceback

        traceback.print_exc()
        raise
