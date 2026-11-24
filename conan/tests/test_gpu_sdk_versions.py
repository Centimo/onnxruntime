import ctypes
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cmake"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conan.errors import ConanException, ConanInvalidConfiguration
from conanfile import OnnxRuntimeConan
from validate_gpu_sdk import Component, decode_version, header_version, validate_library


class SourceVersionTest(unittest.TestCase):
    def test_rejects_sources_for_older_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cmake").mkdir()
            (root / "cmake" / "CMakeLists.txt").touch()
            (root / "VERSION_NUMBER").write_text("1.23.2\n", encoding="utf-8")
            recipe = OnnxRuntimeConan()
            recipe.folders.set_base_source(directory)
            with patch.object(recipe, "_patch_sources") as patch_sources:
                with self.assertRaisesRegex(ConanException, r"1\.23\.2\.1.*1\.23\.2"):
                    recipe.source()
                patch_sources.assert_not_called()


class GpuSdkVersionsTest(unittest.TestCase):
    def test_cuda_build_rejects_sources_without_sdk_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recipe = OnnxRuntimeConan()
            recipe.options.with_cuda = True
            recipe.folders.set_base_source(directory)
            with patch("conanfile.CMake") as cmake:
                with self.assertRaisesRegex(ConanInvalidConfiguration, "GPU SDK version checks"):
                    recipe.build()
                cmake.assert_not_called()

    def test_canonical_option_versions(self) -> None:
        for option in ("cuda_version", "cudnn_version", "tensorrt_version"):
            for version in ("0.0.0", "12.6.77", "9.5.0", "10.5.0"):
                with self.subTest(option=option, version=version):
                    recipe = OnnxRuntimeConan()
                    setattr(recipe.options, option, version)
                    recipe._validate_gpu_version(option)
                    self.assertEqual(str(recipe.options.get_safe(option)), version)

    def test_noncanonical_option_versions(self) -> None:
        for option in ("cuda_version", "cudnn_version", "tensorrt_version"):
            for version in (
                None, "", "legacy", "12", "12.6", "10.5.0.18", "09.5.0", "9.05.0",
                "9.5.00", "+9.5.0", " 9.5.0", "9.5.0 ", "9.5.0\n", "9.5.0-rc1", "\uff19.5.0",
            ):
                with self.subTest(option=option, version=version):
                    recipe = OnnxRuntimeConan()
                    setattr(recipe.options, option, version)
                    with self.assertRaisesRegex(ConanInvalidConfiguration, option):
                        recipe._validate_gpu_version(option)

    def test_library_version_encoding(self) -> None:
        for component, encoded, expected in (
            (Component.CUDNN, 90500, "9.5.0"),
            (Component.CUDNN, 8910, "8.9.10"),
            (Component.TENSORRT, 100500, "10.5.0"),
            (Component.TENSORRT, 101100, "10.11.0"),
            (Component.TENSORRT, 8601, "8.6.1"),
        ):
            with self.subTest(component=component, encoded=encoded):
                self.assertEqual(decode_version(component, encoded), expected)

    def test_invalid_library_version(self) -> None:
        for component in Component:
            for encoded in (0, -1, 50000):
                with self.subTest(component=component, encoded=encoded):
                    with self.assertRaises(ValueError):
                        decode_version(component, encoded)

    def test_header_versions(self) -> None:
        for component, content, expected in (
            (
                Component.CUDNN,
                "#define CUDNN_MAJOR 9\n#define CUDNN_MINOR 5\n#define CUDNN_PATCHLEVEL 0\n",
                "9.5.0",
            ),
            (
                Component.TENSORRT,
                "#define NV_TENSORRT_MAJOR 10\n#define NV_TENSORRT_MINOR 5\n"
                "#define NV_TENSORRT_PATCH 0\n#define NV_TENSORRT_BUILD 18\n",
                "10.5.0",
            ),
            (
                Component.TENSORRT,
                "#define TRT_MAJOR_ENTERPRISE 10\n#define TRT_MINOR_ENTERPRISE 11\n"
                "#define TRT_PATCH_ENTERPRISE 0\n#define TRT_BUILD_ENTERPRISE 33\n"
                "#define NV_TENSORRT_MAJOR TRT_MAJOR_ENTERPRISE\n"
                "#define NV_TENSORRT_MINOR TRT_MINOR_ENTERPRISE\n"
                "#define NV_TENSORRT_PATCH TRT_PATCH_ENTERPRISE\n",
                "10.11.0",
            ),
        ):
            with self.subTest(component=component, expected=expected):
                with tempfile.TemporaryDirectory() as directory:
                    header = Path(directory) / "version.h"
                    header.write_text(content, encoding="utf-8")
                    self.assertEqual(header_version(component, header), expected)

    def test_unverifiable_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            header = Path(directory) / "version.h"
            header.write_text("#define CUDNN_MAJOR 9\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CUDNN_MINOR"):
                header_version(Component.CUDNN, header)

    def test_header_expression_is_not_misread_as_a_literal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            header = Path(directory) / "version.h"
            header.write_text(
                "#define CUDNN_MAJOR 9\n#define CUDNN_MINOR 5 + 1\n#define CUDNN_PATCHLEVEL 0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "CUDNN_MINOR"):
                header_version(Component.CUDNN, header)

    def test_selected_library_and_signatures(self) -> None:
        for component, prefix, encoded, expected, symbol, result_type in (
            (Component.CUDNN, "CUDNN", 90500, "9.5.0", "cudnnGetVersion", ctypes.c_size_t),
            (Component.TENSORRT, "NV_TENSORRT", 100500, "10.5.0", "getInferLibVersion", ctypes.c_int32),
        ):
            with self.subTest(component=component):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    header = root / "version.h"
                    major, minor, patch_version = expected.split(".")
                    patch_macro = "PATCHLEVEL" if component is Component.CUDNN else "PATCH"
                    header.write_text(
                        f"#define {prefix}_MAJOR {major}\n#define {prefix}_MINOR {minor}\n"
                        f"#define {prefix}_{patch_macro} {patch_version}\n",
                        encoding="utf-8",
                    )
                    library_path = root / "selected.so"
                    with patch("validate_gpu_sdk.ctypes.CDLL") as load:
                        function = load.return_value.__getitem__.return_value
                        function.return_value = encoded
                        validate_library(component, expected, library_path, header)
                        load.assert_called_once_with(str(library_path))
                        load.return_value.__getitem__.assert_called_once_with(symbol)
                        self.assertEqual(function.argtypes, [])
                        self.assertIs(function.restype, result_type)

    def test_header_library_mismatch_is_not_hidden_by_matching_expectation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = root / "cudnn_version.h"
            header.write_text(
                "#define CUDNN_MAJOR 9\n#define CUDNN_MINOR 4\n#define CUDNN_PATCHLEVEL 0\n",
                encoding="utf-8",
            )
            library_path = root / "libcudnn.so"
            with patch("validate_gpu_sdk.ctypes.CDLL") as load:
                load.return_value.__getitem__.return_value.return_value = 90500
                with self.assertRaisesRegex(
                    ValueError, r"cuDNN: expected 9.5.0; actual headers 9.4.0.*library 9.5.0"
                ) as failure:
                    validate_library(Component.CUDNN, "9.5.0", library_path, header)
                self.assertIn(str(library_path), str(failure.exception))
                self.assertIn(str(header), str(failure.exception))

    def test_library_mismatch_is_not_hidden_by_matching_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = root / "cudnn_version.h"
            header.write_text(
                "#define CUDNN_MAJOR 9\n#define CUDNN_MINOR 5\n#define CUDNN_PATCHLEVEL 0\n",
                encoding="utf-8",
            )
            with patch("validate_gpu_sdk.ctypes.CDLL") as load:
                load.return_value.__getitem__.return_value.return_value = 90400
                with self.assertRaisesRegex(ValueError, r"actual headers 9.5.0.*library 9.4.0"):
                    validate_library(Component.CUDNN, "9.5.0", root / "libcudnn.so", header)

    def test_missing_library_is_unverifiable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = root / "cudnn_version.h"
            header.write_text(
                "#define CUDNN_MAJOR 9\n#define CUDNN_MINOR 5\n#define CUDNN_PATCHLEVEL 0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, r"cuDNN: expected 9.5.0;.*unverifiable"):
                validate_library(Component.CUDNN, "9.5.0", root / "missing.so", header)

    def test_relative_library_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            validate_library(Component.CUDNN, "9.5.0", Path("libcudnn.so"), Path("cudnn_version.h"))

    def test_missing_version_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = root / "cudnn_version.h"
            header.write_text(
                "#define CUDNN_MAJOR 9\n#define CUDNN_MINOR 5\n#define CUDNN_PATCHLEVEL 0\n",
                encoding="utf-8",
            )
            with patch("validate_gpu_sdk.ctypes.CDLL") as load:
                load.return_value.__getitem__.side_effect = AttributeError("undefined symbol: cudnnGetVersion")
                with self.assertRaisesRegex(ValueError, r"expected 9.5.0;.*unverifiable.*cudnnGetVersion"):
                    validate_library(Component.CUDNN, "9.5.0", root / "selected.so", header)


class CMakeGpuSdkVersionsTest(unittest.TestCase):
    def configure(self, commands: str) -> subprocess.CompletedProcess[str]:
        module = Path(__file__).resolve().parents[2] / "cmake" / "onnxruntime_gpu_sdk_versions.cmake"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.28)\nproject(version_check NONE)\n'
                f'include("{module}")\n'
                'set(onnxruntime_EXPECTED_CUDA_VERSION "12.6.77")\n'
                'set(CUDAToolkit_FOUND TRUE)\nset(CUDAToolkit_VERSION "12.6.77")\n'
                'set(CUDAToolkit_BIN_DIR "/selected/cuda/bin")\n'
                + commands,
                encoding="utf-8",
            )
            return subprocess.run(
                ["cmake", "-S", str(root), "-B", str(root / "build")],
                capture_output=True, text=True, check=False,
            )

    def test_matching_cuda_toolkit(self) -> None:
        result = self.configure("onnxruntime_check_cuda_version()\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CUDA: expected 12.6.77; actual 12.6.77", result.stdout)

    def test_mismatching_later_cuda_toolkit(self) -> None:
        result = self.configure(
            'onnxruntime_check_cuda_version()\nset(CUDAToolkit_VERSION "1.2.3")\n'
            "onnxruntime_check_cuda_version()\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CUDA: expected 12.6.77; actual '1.2.3'", result.stderr)
        self.assertIn("/selected/cuda/bin", result.stderr)

    def test_mismatching_cuda_compiler(self) -> None:
        result = self.configure(
            'set(CMAKE_CUDA_COMPILER_VERSION "1.2.3")\n'
            'set(CMAKE_CUDA_COMPILER "/selected/cuda/nvcc")\n'
            "onnxruntime_check_cuda_version()\n"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CUDA compiler: expected 12.6.77; actual '1.2.3'", result.stderr)
        self.assertIn("/selected/cuda/nvcc", result.stderr)

    def test_missing_cuda_toolkit(self) -> None:
        result = self.configure("set(CUDAToolkit_FOUND FALSE)\nonnxruntime_check_cuda_version()\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CUDA: expected 12.6.77", result.stderr)
        self.assertIn("a verifiable matching CUDAToolkit is required", " ".join(result.stderr.split()))

    def test_cross_compilation_is_not_silently_accepted(self) -> None:
        result = self.configure("set(CMAKE_CROSSCOMPILING TRUE)\nonnxruntime_check_cuda_version()\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CUDA: expected 12.6.77; actual unverifiable", result.stderr)
        self.assertIn("requires native Linux", result.stderr)

    def test_missing_python_interpreter(self) -> None:
        result = self.configure(
            'onnxruntime_check_gpu_library("cuDNN" "9.5.0" "/selected/libcudnn.so" '
            '"/selected/cudnn_version.h")\n'
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cuDNN: expected 9.5.0; actual unverifiable", result.stderr)
        self.assertIn("missing recipe Python interpreter", " ".join(result.stderr.split()))
        self.assertIn("/selected/libcudnn.so", result.stderr)

    def test_python_probe_failure_is_fatal(self) -> None:
        result = self.configure(
            f'set(onnxruntime_GPU_VERSION_PYTHON_EXECUTABLE "{sys.executable}")\n'
            'onnxruntime_check_gpu_library("TensorRT" "10.5.0" "/selected/libnvinfer.so" '
            '"/selected/NvInferVersion.h")\n'
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TensorRT: expected 10.5.0; verification failed", result.stderr)
        self.assertIn("/selected/libnvinfer.so", result.stderr)
        self.assertIn("/selected/NvInferVersion.h", result.stderr)

    def test_module_without_expectations_does_not_probe(self) -> None:
        result = self.configure("unset(onnxruntime_EXPECTED_CUDA_VERSION)\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
