import os as _os
import lib as _lib
import fastmcp as _fastmcp
import pydantic as _pydantic
import asyncio as _asyncio


_IGNORE_DIRS = set([
    "credintials",
    "_credintials",
    "legacy_credentials",
])


class ScanConfig(_pydantic.BaseModel):
    absolute_path: str
    scan_hidden_dirs: bool
    scan_hidden_files: bool


mcp = _fastmcp.FastMCP("File system")


@mcp.tool
def scan_directory(config: ScanConfig) -> dict:
    """
    Scans a directory and all its sub-directories. 
    Returns a dictionary containing directory names and file names inside the directory.
    The directory contents are returned in the key "scan_result" and a quick summary count of directories, files and errors.

    Returns: dict
    {
        "dir_count": int,
        "file_count: int,
        "error_count": int,
        "scan_result": dict
    }

    Example return:
    {
        "dir_count": 2,
        "file_count: 4,
        "error_count": 0,
        "scan_result": {
            "Pictures": {
                "__files__": [
                    "IMG_0695.jpeg",
                    "82737F58-705F-46D8-8F37-95F09366601B.JPG",
                    "Screenshot 2022-02-28 at 3.20.48 AM.png"
                ],
                "Screenshots": {
                    "__files__": [
                        "A cute dog.png"
                    ]
                }
            }
        }
    }
    """
    max_workers = 8
    if cpu_count := _os.cpu_count():
        max_workers = cpu_count * 2
    
    scanner = _lib.Scanner(
        directory=config.absolute_path,
        config={
            "summarize": True,
            "max_workers": max_workers,
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": config.scan_hidden_dirs,
            "scan_hidden_files": config.scan_hidden_files,
        },
    )
    scanner.start()

    scan_result = scanner.result
    scan_summary = scanner.summary

    return {
        "dir_count": scan_summary["dir_count"],
        "file_count": scan_summary["file_count"],
        "error_count": scan_summary["error_count"],
        "scan_result": scan_result,
    }

if __name__ == "__main__":
    # mcp.run("streamable-http")
    _asyncio.run(mcp.run_http_async(transport="sse"))
