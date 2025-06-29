import lib as _lib
import fastmcp as _fastmcp
import pydantic as _pydantic
import asyncio as _asyncio


_IGNORE_DIRS = set([
    ".ssh",
    ".git",
    "cache",
    ".venv",
    "__pycache__",
    "credintials",
    "_credintials",
    "legacy_credentials",
])


class ScanConfig(_pydantic.BaseModel):
    path: str
    scan_hidden_dirs: bool = False
    scan_hidden_files: bool = True
    search_file_names: set[str] | None = None
    search_file_extensions: set[str] | None = None


class _DeepScanSummary(_pydantic.BaseModel):
    dir_count: int
    file_count: int
    error_count: int


class DeepScanResponse(_pydantic.BaseModel):
    summary: _DeepScanSummary
    result: dict[str, str | list[str] | dict]


class ShallowScanResponse(_pydantic.BaseModel):
    result: dict[str, str | list[str]]


class SearchScanResponse(_pydantic.BaseModel):
    count: int
    result: dict[str, list[str]]


class GetFileContentsResponse(_pydantic.BaseModel):
    error: str | None
    lines: list[str]


mcp = _fastmcp.FastMCP("MacOS file system tools")


@mcp.tool(
    name="deep-scan",
    description="""
    Run a deep scan on the given directory and all sub-directories.
    Returns scan results as a mapping of directory name(s) to its contents.
    A quick summary of the scan is also included in the returned dictionary.

    Usage:
    deep_scan(
        ScanConfig(
            path="~",
            scan_hidden_dirs=True,
            scan_hidden_files=True,
            search_file_names=set(["dog"]),
            search_file_extensions=set(["png"]),
        )
    )

    Note: To avoid unknown username related issues, relative paths starting with "~" can be used.
    Use with caution. This method can return substantially large amount of nested contents when 
    called on directories high up in the hierarchy. The response may not fit in the model's context window.
    """,
    enabled=False,
)
def deep_scan(config: ScanConfig) -> DeepScanResponse:
    print("=============================================")
    print("deep_scan:", config.path, flush=True)

    scanner = _lib.Scanner(
        directory=config.path,
        config={
            "summarize": True,
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": config.scan_hidden_dirs,
            "scan_hidden_files": config.scan_hidden_files,
            "search_file_names": config.search_file_names,
            "search_file_extensions": config.search_file_extensions,
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


@mcp.tool(
    name="shallow-scan",
    description="""
    Run a shallow scan only on the given directory.
    Simply lists files and folder names found under the given directory.

    Note: To avoid unknown username related issues, relative paths starting with "~" can be used.
    """
)
def shallow_scan(config: ScanConfig) -> ShallowScanResponse:
    print("=============================================")
    print("shallow_scan:", config.path, flush=True)

    scanner = _lib.Scanner(
        directory=config.path,
        config={
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": config.scan_hidden_dirs,
            "scan_hidden_files": config.scan_hidden_files,
            "search_file_names": config.search_file_names,
            "search_file_extensions": config.search_file_extensions,
        },
    )

    return ShallowScanResponse(
        result=scanner.shallow_scan()
    )


@mcp.tool(
    name="search-directory",
    description="""
    Run a deep scan on the given directory and return files with given names or extensions.

    Usage:
    search_directory(
        ScanConfig(
            path="~",
            scan_hidden_dirs=True,
            scan_hidden_files=True,
            search_file_names=set(["dog"]),
            search_file_extensions=set(["png"]),
        )
    )
    """
)
def search_directory(config: ScanConfig):
    print("=============================================")
    print("search_directory:", config.path, flush=True)

    scanner = _lib.Scanner(
        directory=config.path,
        config={
            "summarize": True,
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": config.scan_hidden_dirs,
            "scan_hidden_files": config.scan_hidden_files,
            "search_file_names": config.search_file_names,
            "search_file_extensions": config.search_file_extensions,
        },
    )

    count: int = 0
    search_result = scanner.search_scan()

    for files in search_result.values():
        count += len(files)
    
    return SearchScanResponse(
        count=count,
        result=search_result
    )



@mcp.tool(
    name="get-file-contents",
    description="""
    Read the given file and return its content.

    Note: To avoid unknown username related issues, relative paths starting with "~" can be used.
    """
)
def get_file_contents(path: str) -> GetFileContentsResponse:
    print("=============================================")
    print("get_file_contents:", path, flush=True)

    result = _lib.get_file_contents(path)

    return GetFileContentsResponse(
        lines=result.lines,
        error=result.error,
    )


if __name__ == "__main__":
    # mcp.run()
    # mcp.run("streamable-http")
    _asyncio.run(mcp.run_http_async(transport="sse", port=8001))
