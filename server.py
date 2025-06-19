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
    path: str
    scan_hidden_dirs: bool
    scan_hidden_files: bool


mcp = _fastmcp.FastMCP("File system")


@mcp.tool
def scan_directory(config: ScanConfig) -> dict:
    """
    Scans a directory and all its sub-directories. 
    Returns scan results as a mapping of directory name(s) to its contents.
    A quick summary of the scan is also included in the returned ductionary.

    Returns: dict
    {
        "summary": dict[str, int],
        "scan_result": dict[str, list[str] | dict]
    }

    Exanple usage:
    scan_directory(
        ScanConfig(
            path="~/Pictures",
            scan_hidden_dirs=True,
            scan_hidden_files=True,
        )
    )

    Example response:
    {
        "summary": {
            "dir_count": 2,
            "file_count: 4,
            "error_count": 0,
        },
        "scan_result": {
            "Pictures": {
                "__files__": [
                    "IMG_0695.jpeg",
                    "A cute dog.png",
                    "82737F58-705F-46D8-8F37-95F09366601B.JPG"
                ],
                "Screenshots": {
                    "__files__": [
                        "Screenshot 2022-02-28 at 3.20.48 PM.png"
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
        directory=config.path,
        config={
            "max_workers": max_workers,
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": config.scan_hidden_dirs,
            "scan_hidden_files": config.scan_hidden_files,
        },
    )
    scanner.start()

    return {
        "summary":  scanner.summary,
        "scan_result": scanner.result,
    }

if __name__ == "__main__":
    # mcp.run("streamable-http")
    _asyncio.run(mcp.run_http_async(transport="sse"))
