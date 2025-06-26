import re as _re
import pathlib as _pathlib
import pydantic as _pydantic


class FileContentsResult(_pydantic.BaseModel):
    lines: list[str] = []
    error: str | None = None


_ansi_escape = _re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')


def _strip_ansi(text: str) -> str:
    return _ansi_escape.sub('', text).strip()


def get_file_contents(path: str) -> FileContentsResult:
    print("=============================================")
    abs_path = _pathlib.Path(path).expanduser()
    print("⏳ Get file contents", str(abs_path), flush=True)

    result = FileContentsResult()

    try:
        with open(str(abs_path)) as file:
            lines = file.readlines()
            result.lines = [
                _strip_ansi(line) for line in lines
            ]

    except OSError as e:
        result.error = str(e)
        print(str(e), flush=True)
    
    return result
