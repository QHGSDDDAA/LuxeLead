import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

UPDATE_PROGRESS_ENV = "LUXELEAD_UPDATE_PROGRESS"


def _run_update_progress_if_requested() -> bool:
    update_dir = os.environ.get(UPDATE_PROGRESS_ENV, "").strip()
    if not update_dir and len(sys.argv) >= 3 and sys.argv[1] == "--luxelead-update-progress":
        update_dir = sys.argv[2].strip()
    if not update_dir:
        return False
    from luxelead.update_progress import run_update_progress_monitor

    run_update_progress_monitor(update_dir)
    return True


if __name__ == "__main__":
    if _run_update_progress_if_requested():
        sys.exit(0)

    from luxelead.gui import main

    main()
