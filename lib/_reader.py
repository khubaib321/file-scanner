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
    if not path.startswith("~"):
        if not path.startswith("/"):
            path = "~/" + path

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
        error = str(e)
        error += "- Make sure the file path is correct and try again."
        result.error = error
        print(error, flush=True)
    
    return result
