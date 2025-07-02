import lib as _lib
import fastapi as _fastapi
import fastapi.middleware.gzip as _gzip_middleware
import pydantic as _pydantic
import uvicorn as _uvicorn

app = _fastapi.FastAPI()
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


@app.post(
    "/fs/deep-scan/",
    status_code=_fastapi.status.HTTP_200_OK,
)
async def deep_scan(data: ScanConfig) -> DeepScanResponse:
    """
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
    "/fs/shallow-scan/",
    status_code=_fastapi.status.HTTP_200_OK,
)
async def shallow_scan(data: ScanConfig) -> ShallowScanResponse:
    """
    Run a shallow scan only on the given directory.
    Simply lists files and folder names found under the given directory.

    Note: To avoid unknown username related issues, relative paths starting with "~" can be used.
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


if __name__ == "__main__":
    _uvicorn.run(
        app=app,
        port=10000,
        host="0.0.0.0",
    )
