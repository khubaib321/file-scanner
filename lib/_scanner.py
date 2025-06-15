import json as _json
import os as _os
import pathlib as _pathlib
import queue as _q
import threading as _threading

from . import _helpers

_MAX_WORKERS = 48
_IGNORE_DIRS = set()
_SCAN_HIDDEN_DIRS = True
_SCAN_HIDDEN_FILES = True


def _ignore_dir(path: str, name: str, ignore_dirs: set[str], scan_hidden: bool) -> bool:
    return (
        name in ignore_dirs or 
        path in ignore_dirs or (
            not scan_hidden and name.startswith('.')
        )
    )


def _ignore_file(name: str, scan_hidden: bool, scan_file_extensions: set[str] | None) -> bool:
    should_ignore = not scan_hidden and name.startswith(".")

    if scan_file_extensions is None:
        return should_ignore

    extension_matched = False
    for ext in scan_file_extensions:
        if name.endswith(ext):
            extension_matched = True
    
    return should_ignore or not extension_matched


class _CrewManager:
    def __init__(self, params: dict) -> None:
        self._work_q = _q.Queue()

        self._path: str = params["path"]
        self._max_workers: int = params["max_workers"]
        self._ignore_dirs: set[str] = params["ignore_dirs"]
        self._scan_hidden_dirs: bool = params["scan_hidden_dirs"]
        self._scan_hidden_files: bool = params["scan_hidden_files"]
        self._scan_file_extensions: set[str] | None = params["scan_file_extensions"]
    
    def _worker(self, work_q: _q.Queue):
        while True:
            try:
                params = work_q.get(timeout=3)
            except _q.Empty:
                continue

            if not params["path"]:
                break
            
            path = params["path"]
            params["bucket"]["__files__"] = []

            try:
                with _os.scandir(path) as it:
                    for entry in it:
                        if (
                            entry.is_file(follow_symlinks=False)
                            and not _ignore_file(entry.name, self._scan_hidden_files, self._scan_file_extensions)
                        ):
                            params["bucket"]["__files__"].append(entry.name)

                        elif (
                            entry.is_dir(follow_symlinks=False)
                            and not _ignore_dir(entry.path, entry.name, self._ignore_dirs, self._scan_hidden_dirs)
                        ):

                            sub_bucket = {}
                            params["bucket"][entry.name] = sub_bucket
                            work_q.put({
                                "path": entry.path,
                                "bucket": sub_bucket,
                            })

            except OSError as e:
                params["bucket"]["__error__"] = str(e)

            finally:
                work_q.task_done()
    
    def begin(self, result_bucket: dict) -> dict:
        self._work_q.put(
            {
                "path": self._path,
                "bucket": result_bucket,
            },
        )
        threads = [
            _threading.Thread(target=self._worker, args=(self._work_q,), daemon=True)
            for _ in range(self._max_workers)
        ]
        for t in threads:
            t.start()

        self._work_q.join()

        # trigger kill switch so the workers exit
        for _ in threads:
            self._work_q.put({"path": None})
        for t in threads:
            t.join()

        return result_bucket


class Scanner:
    def __init__(self, dir: str, config: dict) -> None:
        self._root_path = _pathlib.Path(dir).expanduser()
        self._scan_result: dict = {}

        self._gen_summary: bool = config.get("summarize", False)
        self._max_workers: int = config.get("max_workers", _MAX_WORKERS)
        self._ignore_dirs: set[str] = config.get("ignore_dirs", _IGNORE_DIRS)
        self._output_file_name: str | None = config.get("output_file_name", None)
        self._scan_hidden_dirs: bool = config.get("scan_hidden_dirs", _SCAN_HIDDEN_DIRS)
        self._scan_hidden_files: bool = config.get("scan_hidden_files", _SCAN_HIDDEN_FILES)
        self._scan_file_extensions: set[str] | None = config.get("scan_file_extensions", None)

    @_helpers.time_it()
    def _scan_dir(self) -> None:
        if not (self._root_path.exists() and self._root_path.is_dir()):
            return None

        out_bucket: dict = {}
        crew_man = _CrewManager(
            params={
                "path": str(self._root_path),
                "max_workers": self._max_workers,
                "ignore_dirs": self._ignore_dirs,
                "scan_hidden_dirs": self._scan_hidden_dirs,
                "scan_hidden_files": self._scan_hidden_files,
                "scan_file_extensions": self._scan_file_extensions
            }   
        )

        self._scan_result = crew_man.begin(out_bucket)

    def _summarize(self, bucket: dict = {}) -> tuple[int, int, int]:
        if not bucket:
            bucket = self._scan_result

        if "__error__" in  bucket:
            return 1, 0, 0

        error = 0
        dir_count = len(bucket) - 1
        file_count = len(bucket["__files__"])

        for key, value in bucket.items():
            if key != "__files__":
                ret = self._summarize(bucket=value)
                error += ret[0]
                dir_count += ret[1]
                file_count += ret[2]

        return error, dir_count, file_count
    
    def start(self):
        print("⏳ Scanning", str(self._root_path))
        self._scan_dir()

        if self._output_file_name:
            _os.makedirs("outputs", exist_ok=True)
            out_file_path = f"outputs/{self._output_file_name}.json"
            print(f"✍️   Writing '{out_file_path}' ... ", end="", flush=True)
            with open(out_file_path, "w") as fh:
                _json.dump(self._scan_result, fh, indent=4)
            print("✅")

        if self._gen_summary:
            print("🔍   Summarizing... ", end="", flush=True)
            errors, dirs_count, files_count = self._summarize()
            print("✅")

            print("-------------- Summary --------------")
            print("Scanned", str(self._root_path))
            print(" - Hidden dirs:", "✅" * self._scan_hidden_dirs or "❌")
            print(" - Hidden files:", "✅" * self._scan_hidden_files or "❌")
            print(" - File extensions:", *self._scan_file_extensions or "All")
            print(f"Workers: {self._max_workers}")
            print(f"Total dirs: {dirs_count:,}")
            print(f"Total files: {files_count:,}")
            print(f"Failed scans: {errors:,}")
        
        print("✅ Scan complete.")
