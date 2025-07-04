import lib as _lib
import aiohttp as _aiohttp
import asyncio as _asyncio
import fastapi as _fastapi
import fastapi.middleware.gzip as _gzip_middleware
import pydantic as _pydantic
import uvicorn as _uvicorn

PATH = "/fs"
PORT = 10000

app = _fastapi.FastAPI(docs_url=None, redoc_url=None, root_path=PATH)
app.add_middleware(_gzip_middleware.GZipMiddleware, minimum_size=1_000)


_IGNORE_DIRS = set([
    ".ssh",
    ".git",
    "venv",
    "cache",
    ".venv",
    "__pycache__",
    "credintials",
    "_credintials",
    "legacy_credentials",
])
_LAN_FILE_SYSTEM_SERVERS: set[str] = set()


class ScanConfig(_pydantic.BaseModel):
    path: str
    scan_hidden_dirs: bool = False
    scan_hidden_files: bool = True


class SearchScanConfig(ScanConfig):
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


class SearchScanLanResponse(_pydantic.BaseModel):
    results: dict[str, SearchScanResponse]


class GetFileContentsResponse(_pydantic.BaseModel):
    error: str | None
    lines: list[str]


class LANFileSystemAPI:
    deep_scan: str = "/deep_scan/"
    shallow_scan: str = "/shallow_scan/"
    search_directory: str = "/search-directory/"
    get_file_contents: str = "/get-file-contents/"

    @classmethod
    def _base_url(cls, target: str) -> str:
        return (
            "http://" + target + f":{PORT}" + PATH
        )

    @classmethod
    def search_directory_url(cls, target: str) -> str:
        return cls._base_url(target) + cls.search_directory
    
    @classmethod
    def get_file_contents_url(cls, target: str) -> str:
        return cls._base_url(target) + cls.get_file_contents


@app.get("/health/")
async def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/deep-scan/",
    status_code=_fastapi.status.HTTP_200_OK,
)
async def deep_scan(data: ScanConfig) -> DeepScanResponse:
    """
    Run a deep scan on the given directory and all sub-directories.
    Returns scan results as a mapping of directory name(s) to its contents.
    A quick summary of the scan is also included in the returned dictionary.

    Note: To avoid username related issues, relative paths starting with "~" should be used.
    Use with caution. This method can return substantially large amount of nested contents when 
    called on directories high up in the hierarchy. The response may not fit in the model's context window.
    """
    print("=============================================")
    print("deep_scan:", data.path, flush=True)

    scanner = _lib.Scanner(
        directory=data.path,
        config={
            "summarize": True,
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": data.scan_hidden_dirs,
            "scan_hidden_files": data.scan_hidden_files,
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


@app.post(
    "/shallow-scan/",
    status_code=_fastapi.status.HTTP_200_OK,
)
async def shallow_scan(data: ScanConfig) -> ShallowScanResponse:
    """
    Run a shallow scan only on the given directory.
    Simply lists files and folder names found under the given directory.

    Note: To avoid username related issues, relative paths starting with "~" should be used.
    """
    print("=============================================")
    print("shallow_scan:", data.path, flush=True)

    scanner = _lib.Scanner(
        directory=data.path,
        config={
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": data.scan_hidden_dirs,
            "scan_hidden_files": data.scan_hidden_files,
        },
    )

    return ShallowScanResponse(
        result=scanner.shallow_scan()
    )


@app.post(
    "/search-directory/",
    status_code=_fastapi.status.HTTP_200_OK,
)
async def search_directory(data: SearchScanConfig):
    """
    Search for files with names and/or extensions in the target directory.

    Note: To avoid username related issues, relative paths starting with "~" should be used.
    """
    print("=============================================")
    print("search_directory:", data.path, flush=True)

    scanner = _lib.Scanner(
        directory=data.path,
        config={
            "summarize": True,
            "ignore_dirs": _IGNORE_DIRS,
            "scan_hidden_dirs": data.scan_hidden_dirs,
            "scan_hidden_files": data.scan_hidden_files,
            "search_file_names": data.search_file_names,
            "search_file_extensions": data.search_file_extensions,
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


@app.post(
    "/search-directory-lan/",
    status_code=_fastapi.status.HTTP_200_OK,
)
async def search_directory_lan(config: ScanConfig) -> SearchScanLanResponse:
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


@app.post(
    "/get-file-contents/",
    status_code=_fastapi.status.HTTP_200_OK,
)
async def get_file_contents(path: str) -> GetFileContentsResponse:
    """
    Read the given file and return its content.

    Note: To avoid username related issues, relative paths starting with "~" should be used.
    """
    print("=============================================")
    print("get_file_contents:", path, flush=True)

    result = _lib.get_file_contents(path)

    return GetFileContentsResponse(
        lines=result.lines,
        error=result.error,
    )


@app.get("/docs", include_in_schema=False)
async def api_docs(request: _fastapi.Request):
    return _fastapi.responses.HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
            <title>Elements in HTML</title>

            <script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
            <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css">
        </head>
        <body>

            <elements-api
            apiDescriptionUrl="openapi.json"
            router="hash"
            />

        </body>
        </html>
        """
    )


if __name__ == "__main__":
    _LAN_FILE_SYSTEM_SERVERS = _lib.discover_lan_file_system_servers()

    _uvicorn.run(
        app=app,
        port=PORT,
        host="0.0.0.0",
    )
