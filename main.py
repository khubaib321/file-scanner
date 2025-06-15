import os as _os
import lib as _lib


def main():
    ignore_dirs = set([
        "credintials",
        "_credintials",
        "legacy_credentials",
    ])
    scan_file_extensions = set([
        "png",
        "jpg",
        "jpeg",
    ])

    max_workers = 8
    if cpu_count := _os.cpu_count():
        max_workers = cpu_count * 2

    scanner = _lib.Scanner(
        directory="~",
        config={
            "summarize": True,
            "max_workers": max_workers,
            "ignore_dirs": ignore_dirs,
            "scan_hidden_dirs": True,
            "scan_hidden_files": True,
            "output_file_name": "files",
            "scan_file_extensions": scan_file_extensions,
        },
    )
    scanner.start()


if __name__ == "__main__":
    main()
