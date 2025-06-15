import os as _os
import pathlib as _pathlib
import json as _json
import threading as _threading
from queue import Queue, Empty

import helpers as _helpers

_MAX_WORKERS = 48
_IGNORE_DIRS = {
    # "tmp",
    # "bin", 
    # "sbin", 
    # "venv", 
    # "dist",
    # "Volumes",
    # "__pycache__",
    # "virtualenvs",
    # "node_modules",
}
_IGNORE_HIDDEN_DIRS = True
_IGNORE_HIDDEN_FILES = True


def _should_ignore_dir(name: str) -> bool:
    return name in _IGNORE_DIRS or (name.startswith('.') and _IGNORE_HIDDEN_DIRS)


def _should_ignore_file(name: str) -> bool:
    return name.startswith(".") and _IGNORE_HIDDEN_FILES


def _worker(work_q: Queue):
    while True:
        try:
            path, bucket = work_q.get(timeout=3)
        except Empty:
            continue

        if path is None:
            break

        bucket["__files__"] = []

        try:
            with _os.scandir(path) as it:
                for entry in it:
                    if (
                        entry.is_file(follow_symlinks=False)
                        and not _should_ignore_file(entry.name)
                    ):
                        bucket["__files__"].append(entry.name)

                    elif (
                        entry.is_dir(follow_symlinks=False)
                        and not _should_ignore_dir(entry.name)
                    ):

                        sub_bucket = {}
                        bucket[entry.name] = sub_bucket
                        work_q.put((entry.path, sub_bucket))

        except OSError as e:
            bucket["__error__"] = str(e)

        finally:
            work_q.task_done()


@_helpers.time_it()
def scan_directory(root_dir: str) -> dict:
    root_path = _pathlib.Path(root_dir).expanduser()
    if not (root_path.exists() and root_path.is_dir()):
        return {}

    work_q: Queue = Queue()
    result: dict = {}
    work_q.put((str(root_path), result))

    threads = [
        _threading.Thread(target=_worker, args=(work_q,), daemon=True)
        for _ in range(_MAX_WORKERS)
    ]
    for t in threads:
        t.start()

    work_q.join()

    # trigger kill switch so the workers exit
    for _ in threads:
        work_q.put((None, None))
    for t in threads:
        t.join()

    return result


def _summarize(*, scan_result: dict) -> tuple[int, int, int]:
    if "__error__" in  scan_result:
        return 1, 0, 0

    error = 0
    dir_count = len(scan_result) - 1
    file_count = len(scan_result["__files__"])

    for key, value in scan_result.items():
        if key != "__files__":
            ret = _summarize(scan_result=value)
            error += ret[0]
            dir_count += ret[1]
            file_count += ret[2]

    return error, dir_count, file_count


def main():
    root = _os.path.expanduser("/")
    scan_result = scan_directory(root)

    print("✍️ Writing to file... ", end="", flush=True)
    _os.makedirs("outputs", exist_ok=True)
    with open("outputs/file_structure.json", "w") as fh:
        _json.dump(scan_result, fh, indent=4)
    print("✅")

    print("+ Summarizing... ", end="", flush=True)
    errors, total_dirs, total_files = _summarize(scan_result=scan_result)
    print("✅")

    print("-------------- Summary --------------")
    print(f"Scanned: '{str(root)}'")
    print(f"Workers used: {_MAX_WORKERS}")
    print("Hidden dirs considered:", "❌" * _IGNORE_HIDDEN_DIRS or "✅")
    print("Hidden files considered:", "❌" * _IGNORE_HIDDEN_FILES or "✅")
    print(f"Total dirs: {total_dirs:,}")
    print(f"Total files: {total_files:,}")
    print(f"Failed scans: {errors:,}")
    print("-------------- Summary --------------")


if __name__ == "__main__":
    main()
