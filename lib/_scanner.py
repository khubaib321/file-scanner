import json as _json
import os as _os
import pathlib as _pathlib
import queue as _q
import threading as _threading

from . import _helpers

_MAX_WORKERS = 32
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

    if should_ignore:
        return True
    
    if not scan_file_extensions:
        return should_ignore

    for ext in scan_file_extensions:
        if name.lower().endswith("." + ext.lower()):
            return False
    
    return True


class _TaskManager:
    def __init__(self, params: dict) -> None:
        self._work_q = _q.Queue()
        self._workers_to_deploy: int = 0

        self._path: str = params["path"]
        self._ignore_dirs: set[str] = params["ignore_dirs"]
        self._scan_hidden_dirs: bool = params["scan_hidden_dirs"]
        self._scan_hidden_files: bool = params["scan_hidden_files"]
        self._scan_file_extensions: set[str] | None = params["scan_file_extensions"]
    
    def skim_dir(self, path: str) -> dict:
        result: dict = {
            "__path__": str(path),
            "__files__": [],
        }

        try:
            with _os.scandir(path) as it:
                for entry in it:
                    if (
                        entry.is_file(follow_symlinks=False)
                        and not _ignore_file(entry.name, self._scan_hidden_files, self._scan_file_extensions)
                    ):
                        result["__files__"].append(entry.name)
                    
                    elif (
                        entry.is_dir(follow_symlinks=False)
                        and not _ignore_dir(entry.path, entry.name, self._ignore_dirs, self._scan_hidden_dirs)
                    ):
                        result[entry.name] = {
                            "__path__": str(entry.path),
                            "__files__": []
                        }
        
        except OSError as e:
            result["__error__"] = str(e)
            
        return result
    
    def _crawl_dir(self, out_bucket: dict) -> None:
        assert "__path__" in out_bucket, "Provided bucket has no '__path__'"
        assert "__files__" in out_bucket, "Provided bucket has no '__files__'"

        crawl_targets = [(out_bucket["__path__"], out_bucket)]
        while crawl_targets:
            target_path, target_bucket = crawl_targets.pop(0)

            try:
                with _os.scandir(target_path) as it:
                    for entry in it:
                        if (
                            entry.is_file(follow_symlinks=False)
                            and not _ignore_file(entry.name, self._scan_hidden_files, self._scan_file_extensions)
                        ):
                            target_bucket["__files__"].append(entry.name)
                        
                        elif (
                            entry.is_dir(follow_symlinks=False)
                            and not _ignore_dir(entry.path, entry.name, self._ignore_dirs, self._scan_hidden_dirs)
                        ):
                            target_bucket[entry.name] = {
                                "__path__": entry.path,
                                "__files__": []
                            }
                            crawl_targets.append(
                                (entry.path, target_bucket[entry.name])
                            )

            except OSError as e:
                target_bucket["__error__"] = str(e)

    
    def _worker(self, work_q: _q.Queue):
        while True:
            try:
                params = work_q.get(timeout=1)
            except _q.Empty:
                continue

            if not params["path"]:
                work_q.task_done()
                return
            
            path = params["path"]
            params["bucket"]["__path__"] = path
            params["bucket"]["__files__"] = []

            self._crawl_dir(params["bucket"])

            work_q.task_done()
    
    @property
    def workers_deployed(self) -> int:
        return self._workers_to_deploy
    
    def begin_scan(self) -> dict:
        result_bucket: dict = self.skim_dir(self._path)

        if "__error__" in result_bucket:
            return result_bucket

        root_width = 0
        for key, value in result_bucket.items():
            if key not in {"__path__", "__files__"}:
                self._work_q.put(
                    {
                        "path": value["__path__"],
                        "bucket": result_bucket[key],
                    },
                )
                root_width += 1

        self._workers_to_deploy = min(root_width, _MAX_WORKERS)
        threads = [
            _threading.Thread(target=self._worker, args=(self._work_q,), daemon=True)
            for _ in range(self._workers_to_deploy)
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
    def __init__(self, directory: str, config: dict) -> None:
        if not directory.startswith("~"):
            if not directory.startswith("/"):
                directory = "~" + directory
            else:
                directory = "/" + directory

        self._root_path = _pathlib.Path(directory).expanduser()
        self._scan_result: dict[str, str | list[str] | dict] = {}

        self._gen_summary: bool = config.get("summarize", False)
        self._ignore_dirs: set[str] = config.get("ignore_dirs", _IGNORE_DIRS)
        self._output_file_name: str | None = config.get("output_file_name", None)
        self._scan_hidden_dirs: bool = config.get("scan_hidden_dirs", _SCAN_HIDDEN_DIRS)
        self._scan_hidden_files: bool = config.get("scan_hidden_files", _SCAN_HIDDEN_FILES)
        self._scan_file_extensions: set[str] | None = config.get("scan_file_extensions", None)

        self._task_man = _TaskManager(
            params={
                "path": str(self._root_path),
                "ignore_dirs": self._ignore_dirs,
                "scan_hidden_dirs": self._scan_hidden_dirs,
                "scan_hidden_files": self._scan_hidden_files,
                "scan_file_extensions": self._scan_file_extensions
            }   
        )
    
    @property
    def result(self) -> dict[str, str | list[str] | dict]:
        return self._scan_result
    
    @property
    def summary(self) -> dict[str, int]:
        error_count, dir_count, file_count = self._summarize()

        return {
            "dir_count": dir_count,
            "file_count": file_count,
            "error_count": error_count,
        }
    
    @property
    def workers_deployed(self) -> int:
        return self._task_man.workers_deployed

    @_helpers.time_it()
    def _scan_dir(self) -> None:
        if not (self._root_path.exists() and self._root_path.is_dir()):
            self._scan_result = {
                "__path__": str(self._root_path),
                "__files__": [],
                "__error__": f"Provided path '{self._root_path}' does not exist."
            }
            return

        self._scan_result = self._task_man.begin_scan()

    def _summarize(self, bucket: dict | None = None) -> tuple[int, int, int]:
        if bucket is None:
            bucket = self._scan_result

        if "__error__" in  bucket:
            return 1, 0, 0

        error_count = 0
        dir_count = len(bucket) - 2
        file_count = len(bucket["__files__"])

        for key, value in bucket.items():
            if key not in {"__path__", "__files__"}:
                ret = self._summarize(bucket=value)
                dir_count += ret[1]
                file_count += ret[2]
                error_count += ret[0]

        return error_count, dir_count, file_count
    
    def shallow_scan(self) -> dict[str, str | list[str]]:
        print("=============================================")
        print("⏳ Shallow scan", str(self._root_path), flush=True)
        scan_result = self._task_man.skim_dir(str(self._root_path))

        result: dict = {
            "path": "",
            "dirs": [],
            "files": [],
        }
        for key in scan_result:
            if key == "__path__":
                result["path"] = scan_result[key]

            elif key == "__files__":
                result["files"] = scan_result[key]
            
            elif key == "__error__":
                result["__error__"] = scan_result[key]

            elif isinstance(scan_result[key], dict):
                result["dirs"].append(key)
        
        print(_json.dumps(result, indent=2), flush=True)

        return result
    
    def deep_scan(self):
        print("=============================================")
        print("⏳ Deep scan", str(self._root_path), flush=True)
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

            print("")
            print("Scanned", str(self._root_path))
            print(" - Hidden dirs:", "✅" if self._scan_hidden_dirs else "❌")
            print(" - Hidden files:", "✅" if self._scan_hidden_files else "❌")
            print(" - Ignored dirs:", self._ignore_dirs or "None")
            print(" - File extensions:", self._scan_file_extensions or "All")
            print("")
            print(f"- Workers: {self.workers_deployed}")
            print(f"- Total dirs: {dirs_count:,}")
            print(f"- Total files: {files_count:,}")
            print(f"- Failed scans: {errors:,}")
        
        print("✅ Deep scan complete.", flush=True)
