import src.scanner as _scanner


def main():
    ignore_dirs = set(
        # "tmp",
        # "bin", 
        # "sbin", 
        # "venv", 
        # "dist",
        # "Volumes",
        # "__pycache__",
        # "virtualenvs",
        # "node_modules",
    )
    _scanner.start(
        dir="/",
        config={
            "summarize": True,
            "max_workers": 16,
            "ignore_dirs": ignore_dirs,
            "scan_hidden_dirs": False,
            "scan_hidden_files": False,
            # "output_file_name": None,
        },
    )


if __name__ == "__main__":
    main()
