import lib as _lib
import fastmcp as _fastmcp
import pydantic as _pydantic
import asyncio as _asyncio


_IGNORE_DIRS = set([
    "cache",
    "__pycache__",
    "credintials",
    "_credintials",
    "legacy_credentials",
])


class ScanConfig(_pydantic.BaseModel):
    path: str
    scan_hidden_dirs: bool = False
    scan_hidden_files: bool = True


class _ScanSummary(_pydantic.BaseModel):
    dir_count: int
    file_count: int
    error_count: int


class ScanResponse(_pydantic.BaseModel):
    summary: _ScanSummary
    result: dict[str, str | list[str] | dict]


mcp = _fastmcp.FastMCP("File system")


@mcp.tool
def scan_directory(config: ScanConfig) -> ScanResponse:
    """
    Scans a directory and all its sub-directories. 
    Returns scan results as a mapping of directory name(s) to its contents.
    A quick summary of the scan is also included in the returned dictionary.

    Returns: ScanResponse

    Example usage:
    ```
    scan_directory(
        ScanConfig(
            path="~/Pictures",
            scan_hidden_dirs=True,
            scan_hidden_files=True,
        )
    )
    ```

    Example response:
    ```
    {
        "summary": {
            "dir_count": 2,
            "file_count: 4,
            "error_count": 0,
        },
        "scan_result": {
            "Pictures": {
                "__path__": "/Users/currentuser/Pictures",
                "__files__": [
                    "IMG_0695.jpeg",
                    "A cute dog.png",
                    "82737F58-705F-46D8-8F37-95F09366601B.JPG"
                ],
                "Screenshots": {
                    "__path__": "/Users/currentuser/Pictures/Screenshots",
                    "__files__": [
                        "Screenshot 2022-02-28 at 3.20.48 PM.png"
                    ]
                }
            }
        }
    }
    ```
    """
    
    scanner = _lib.Scanner(
        directory=config.path,
        config={
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": config.scan_hidden_dirs,
            "scan_hidden_files": config.scan_hidden_files,
        },
    )
    scanner.start()

    return ScanResponse(
        result=scanner.result,
        summary=_ScanSummary(
            dir_count=scanner.summary["dir_count"],
            file_count=scanner.summary["file_count"],
            error_count=scanner.summary["error_count"],
        )
    )

if __name__ == "__main__":
    mcp.run()
    # mcp.run("streamable-http")
    # _asyncio.run(mcp.run_http_async(transport="sse"))
