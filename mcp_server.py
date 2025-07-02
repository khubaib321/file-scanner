import lib as _lib
import asyncio as _asyncio
import fastmcp as _fastmcp
import pydantic as _pydantic


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


mcp = _fastmcp.FastMCP("MacOS file system tools")


class ScanConfig(_pydantic.BaseModel):
    path: str
    scan_hidden_dirs: bool = False
    scan_hidden_files: bool = True
    search_file_names: set[str] | None = None
    search_file_extensions: set[str] | None = None


class SearchScanResponse(_pydantic.BaseModel):
    count: int
    result: dict[str, list[str]]


class GetFileContentsResponse(_pydantic.BaseModel):
    error: str | None
    lines: list[str]


@mcp.tool(
    name="search-directory",
    description="""
    Search for files with names and/or extensions in the target directory.

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
