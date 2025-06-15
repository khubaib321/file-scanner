import os as _os
import pathlib as _pathlib
import json as _json
import threading as _threading
import queue as _q
from typing import Any

from . import _helpers

_MAX_WORKERS = 48
_IGNORE_DIRS = set()
_SCAN_HIDDEN_DIRS = True
_SCAN_HIDDEN_FILES = True


def _should_ignore_dir(path: str, name: str, ignore_dirs: set[str], scan_hidden: bool) -> bool:
    return (
        name in ignore_dirs or 
        path in ignore_dirs or (
            not scan_hidden and name.startswith('.')
        )
    )


def _should_ignore_file(name: str, scan_hidden: bool) -> bool:
    return not scan_hidden and name.startswith(".")


def _worker(work_q: _q.Queue):
    while True:
        try:
            params = work_q.get(timeout=3)
        except _q.Empty:
            continue

        path = params["path"]
        if not path:
            break

        params["bucket"]["__files__"] = []
        ignore_dirs = params["ignore_dirs"]
        scan_hidden_dirs = params["scan_hidden_dirs"]
        scan_hidden_files = params["scan_hidden_files"]

        try:
            with _os.scandir(path) as it:
                for entry in it:
                    if (
                        entry.is_file(follow_symlinks=False)
                        and not _should_ignore_file(entry.name, scan_hidden_files)
                    ):
                        params["bucket"]["__files__"].append(entry.name)

                    elif (
                        entry.is_dir(follow_symlinks=False)
                        and not _should_ignore_dir(entry.path, entry.name, ignore_dirs, scan_hidden_dirs)
                    ):

                        sub_bucket = {}
                        params["bucket"][entry.name] = sub_bucket
                        work_q.put({
                            "path": entry.path,
                            "bucket": sub_bucket,
                            "ignore_dirs": ignore_dirs,
                            "scan_hidden_dirs": scan_hidden_dirs,
                            "scan_hidden_files": scan_hidden_files,
                        })

        except OSError as e:
            params["bucket"]["__error__"] = str(e)

        finally:
            work_q.task_done()


@_helpers.time_it()
def _scan_directory(
    *, 
    root_dir: str, 
    max_workers: int, 
    ignore_dirs: set[str],
    scan_hidden_dirs: bool, 
    scan_hidden_files: bool
) -> dict:
    root_path = _pathlib.Path(root_dir).expanduser()
    if not (root_path.exists() and root_path.is_dir()):
        return {}

    work_q = _q.Queue()
    result: dict = {}
    work_q.put(
        {
            "path": str(root_path),
            "bucket": result,
            "ignore_dirs": ignore_dirs,
            "scan_hidden_dirs": scan_hidden_dirs,
            "scan_hidden_files": scan_hidden_files,
        },
    )

    threads = [
        _threading.Thread(target=_worker, args=(work_q,), daemon=True)
        for _ in range(max_workers)
    ]
    for t in threads:
        t.start()

    work_q.join()

    # trigger kill switch so the workers exit
    for _ in threads:
        work_q.put({"path": None})
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


def start(*, dir: str, config: dict[str, Any]):
    root = _os.path.expanduser(dir)
    max_workers = config.get("max_workers", _MAX_WORKERS)
    ignore_dirs = config.get("ignore_dirs", _IGNORE_DIRS)
    scan_hidden_dirs = config.get("scan_hidden_dirs", _SCAN_HIDDEN_DIRS)
    scan_hidden_files = config.get("scan_hidden_files", _SCAN_HIDDEN_FILES)
    
    scan_result = _scan_directory(
        root_dir=root, 
        max_workers=max_workers,
        ignore_dirs=ignore_dirs,
        scan_hidden_dirs=scan_hidden_dirs,
        scan_hidden_files=scan_hidden_files,
    )

    if output_file := config.get("output_file_name"):
        _os.makedirs("outputs", exist_ok=True)
        output_file_path = f"outputs/{output_file}.json"
        print(f"✍️   Writing to '{output_file_path}' ... ", end="", flush=True)
        with open(output_file_path, "w") as fh:
            _json.dump(scan_result, fh, indent=4)
        print("✅")

    if config.get("summarize"):
        print("🔍   Summarizing... ", end="", flush=True)
        errors, total_dirs, total_files = _summarize(scan_result=scan_result)
        print("✅")

        print("-------------- Summary --------------")
        print(f"Scanned: '{str(root)}'")
        print(" - Hidden dirs:", "✅" * scan_hidden_dirs or "❌")
        print(" - Hidden files:", "✅" * scan_hidden_files or "❌")
        print(f"Workers: {max_workers}")
        print(f"Total dirs: {total_dirs:,}")
        print(f"Total files: {total_files:,}")
        print(f"Failed scans: {errors:,}")
        print("-------------- Summary --------------")
