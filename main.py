import src.scanner as _scanner


def main():
    _scanner.start(
        dir="~",
        config={
            "summarize": True,
            "max_workers": 24,
            "scan_hidden_dirs": True,
            "scan_hidden_files": True,
        },
    )


if __name__ == "__main__":
    main()
