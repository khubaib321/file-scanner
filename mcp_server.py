import lib as _lib
import aiohttp as _aiohttp
import asyncio as _asyncio
import fastmcp as _fastmcp
import pydantic as _pydantic
import server as _server


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
_LAN_FILE_SYSTEM_SERVERS: set[str] = _lib.discover_lan_file_system_servers()


mcp = _fastmcp.FastMCP("MacOS file system tools")


class LANFileSystemAPI:
    deep_scan: str = "/deep_scan/"
    shallow_scan: str = "/shallow_scan/"
    search_directory: str = "/search-directory/"
    get_file_contents: str = "/get-file-contents/"

    @classmethod
    def _base_url(cls, target: str) -> str:
        return (
            "http://" + target + f":{_server.PORT}" + _server.PATH
        )

    @classmethod
    def search_directory_url(cls, target: str) -> str:
        return cls._base_url(target) + cls.search_directory
    
    @classmethod
    def get_file_contents_url(cls, target: str) -> str:
        return cls._base_url(target) + cls.get_file_contents


class SearchScanConfig(_pydantic.BaseModel):
    path: str
    scan_hidden_dirs: bool = False
    scan_hidden_files: bool = True
    search_file_names: set[str] | None = None
    search_file_extensions: set[str] | None = None


class SearchScanResponse(_pydantic.BaseModel):
    count: int
    result: dict[str, list[str]]


class SearchScanLanResponse(_pydantic.BaseModel):
    results: dict[str, SearchScanResponse]


class GetFileContentsResponse(_pydantic.BaseModel):
    lines: list[str]
    error: str | None


@mcp.tool(
    name="search-directory",
    description="""
    Search for files with names and/or extensions in the target directory.

    Note: To avoid username related issues, relative paths starting with "~" should be used.
    """
)
def search_directory(config: SearchScanConfig):
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
    name="search-directory-lan",
    description="""
    Search for files with names and/or extensions in connected LAN systems.

    Note: To avoid username related issues, relative paths starting with "~" should be used.
    """
)
async def search_directory_lan(config: SearchScanConfig) -> SearchScanLanResponse:
    print("=============================================")
    print("search_directory_lan:", config.path, flush=True)

    payload = config.model_dump(mode="json")
    host_results: dict[str, SearchScanResponse] = {}

    async with _aiohttp.ClientSession() as session:
        async def _fetch(server: str) -> tuple[str, SearchScanResponse]:
            url = LANFileSystemAPI.search_directory_url(server)

            try:
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()
                    return (
                        server,
                        SearchScanResponse(count=data["count"], result=data["result"])
                    )

            except Exception as exc:
                return (
                    server,
                    SearchScanResponse(count=0, result={"__error__": [str(exc)]})
                )

        results = await _asyncio.gather(
            *(_fetch(s) for s in _LAN_FILE_SYSTEM_SERVERS),
            return_exceptions=True
        )

    for item in results:
        if isinstance(item, BaseException):
            continue

        server, response = item
        host_results[server] = response

    return SearchScanLanResponse(results=host_results)


@mcp.tool(
    name="get-file-contents",
    description="""
    Read the given file and return its content.

    Note: To avoid username related issues, relative paths starting with "~" should be used.
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
