import os as _os
import lib as _lib


def main():
    ignore_dirs = set([
        # "tmp",
        # "bin", 
        # "sbin", 
        # "venv", 
        # "dist",
        # "Volumes",
        # "__pycache__",
        # "virtualenvs",
        # "node_modules",
    ])
    scan_file_extensions = set([
        ".png",
        ".jpg",
        ".jpeg",
    ])

    max_workers = 8
    if cpu_count := _os.cpu_count():
        max_workers = cpu_count * 2

    scanner = _lib.Scanner(
        dir="~",
        config={
            "summarize": True,
            "max_workers": max_workers,
            "ignore_dirs": ignore_dirs,
            "scan_hidden_dirs": False,
            "scan_hidden_files": False,
            "output_file_name": "files",
            "scan_file_extensions": scan_file_extensions,
        },
    )
    scanner.start()


if __name__ == "__main__":
    main()
