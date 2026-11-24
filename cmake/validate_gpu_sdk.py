import argparse
import ctypes
from enum import Enum
from pathlib import Path
import re
import sys


class Component(Enum):
    CUDNN = "cuDNN"
    TENSORRT = "TensorRT"


def decode_version(component: Component, encoded: int) -> str:
    """Decode the library API's major/minor/patch integer, excluding NVIDIA build numbers."""
    modern_major = 9 if component is Component.CUDNN else 10
    if encoded >= modern_major * 10000:
        return f"{encoded // 10000}.{encoded // 100 % 100}.{encoded % 100}"
    if 1000 <= encoded < modern_major * 1000:
        return f"{encoded // 1000}.{encoded // 100 % 10}.{encoded % 100}"
    raise ValueError(f"unverifiable version integer {encoded}")


def header_version(component: Component, path: Path) -> str:
    """Read the version from the selected cuDNN or TensorRT version header."""
    content = path.read_text(encoding="utf-8")
    if component is Component.CUDNN:
        macros = ("CUDNN_MAJOR", "CUDNN_MINOR", "CUDNN_PATCHLEVEL")
    elif re.search(r"^\s*#\s*define\s+TRT_MAJOR_ENTERPRISE\b", content, re.MULTILINE):
        macros = ("TRT_MAJOR_ENTERPRISE", "TRT_MINOR_ENTERPRISE", "TRT_PATCH_ENTERPRISE")
    else:
        macros = ("NV_TENSORRT_MAJOR", "NV_TENSORRT_MINOR", "NV_TENSORRT_PATCH")
    values: list[str] = []
    for macro in macros:
        matches = re.findall(
            rf"^[ \t]*#[ \t]*define[ \t]+{macro}[ \t]+([0-9]+)"
            rf"[ \t]*(?://[^\n]*|/\*[^\n]*\*/[ \t]*)?\r?$",
            content, re.MULTILINE,
        )
        if len(matches) != 1:
            raise ValueError(f"unverifiable header macro {macro} in {path}")
        values.append(str(int(matches[0])))
    return ".".join(values)


def validate_library(component: Component, expected: str, library_path: Path, header_path: Path) -> None:
    """Require both selected header and absolute shared library versions to equal the expectation."""
    description = (
        f"{component.value}: expected {expected}; "
        f"selected library {library_path}; selected header {header_path}"
    )
    if not library_path.is_absolute() or not header_path.is_absolute():
        raise ValueError(f"{description}; verification requires absolute paths")
    actual_header = "unverifiable"
    try:
        actual_header = header_version(component, header_path)
        library = ctypes.CDLL(str(library_path))
        if component is Component.CUDNN:
            function = library["cudnnGetVersion"]
            function.restype = ctypes.c_size_t
        else:
            function = library["getInferLibVersion"]
            function.restype = ctypes.c_int32
        function.argtypes = []
        actual_library = decode_version(component, int(function()))
    except (OSError, AttributeError, ValueError) as error:
        raise ValueError(
            f"{description}; actual headers {actual_header}; library unverifiable: {error}"
        ) from error
    actual = (
        f"{component.value}: expected {expected}; actual headers {actual_header} ({header_path}); "
        f"library {actual_library} ({library_path})"
    )
    if actual_header != expected or actual_library != expected:
        raise ValueError(actual)
    print(actual)


def main() -> int:
    """Validate selected SDK paths passed by CMake, returning a diagnostic on failure."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", choices=[component.value for component in Component], required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--header", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        validate_library(
            Component(arguments.component), arguments.expected, arguments.library, arguments.header
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
