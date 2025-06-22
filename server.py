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


class _DeepScanSummary(_pydantic.BaseModel):
    dir_count: int
    file_count: int
    error_count: int


class DeepScanResponse(_pydantic.BaseModel):
    summary: _DeepScanSummary
    result: dict[str, str | list[str] | dict]


class ShallowScanResponse(_pydantic.BaseModel):
    result: dict[str, str | list[str]]


mcp = _fastmcp.FastMCP("File system")


@mcp.tool
def deep_scan(config: ScanConfig) -> DeepScanResponse:
    """
    Run a deep scan on the given directory and all sub-directories.
    Returns scan results as a mapping of directory name(s) to its contents.
    A quick summary of the scan is also included in the returned dictionary.
    """
    
    scanner = _lib.Scanner(
        directory=config.path,
        config={
            "summarize": True,
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": config.scan_hidden_dirs,
            "scan_hidden_files": config.scan_hidden_files,
        },
    )
    scanner.deep_scan()

    return DeepScanResponse(
        result=scanner.result,
        summary=_DeepScanSummary(
            dir_count=scanner.summary["dir_count"],
            file_count=scanner.summary["file_count"],
            error_count=scanner.summary["error_count"],
        )
    )


@mcp.tool
def shallow_scan(config: ScanConfig) -> ShallowScanResponse:
    """
    Run a shallow scan only on the given directory.
    Simply lists files and folder names found under the given directory.
    """

    scanner = _lib.Scanner(
        directory=config.path,
        config={
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": config.scan_hidden_dirs,
            "scan_hidden_files": config.scan_hidden_files,
        },
    )

    return ShallowScanResponse(
        result=scanner.shallow_scan()
    )


if __name__ == "__main__":
    # mcp.run()
    # mcp.run("streamable-http")
    _asyncio.run(mcp.run_http_async(transport="sse", port=8001))
