import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import is_apple_os
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get, rmdir, replace_in_file

required_conan_version = ">=2"


class OnnxRuntimeConan(ConanFile):
    name = "onnxruntime"
    version = "1.23.2"
    description = "ONNX Runtime: cross-platform, high performance ML inferencing and training accelerator"
    url = "https://github.com/Centimo/onnxruntime"
    license = "MIT"
    homepage = "https://onnxruntime.ai"
    topics = ("deep-learning", "onnx", "neural-networks", "machine-learning", "ai-framework", "hardware-acceleration")

    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_xnnpack": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_xnnpack": False,
        "date/*:use_system_tz_db": True,
    }
    short_paths = True

    def export_sources(self):
        export_conandata_patches(self)
        copy(self, "*", src=os.path.join(self.recipe_folder, ".."), dst=self.export_sources_folder,
             excludes=["conan/*", ".git/*"])

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        required_onnx_version = self.conan_data["onnx_version_map"][self.version]
        self.requires(f"onnx/{required_onnx_version}")
        self.requires("abseil/20250512.1")
        self.requires("protobuf/3.21.12")
        self.requires("date/3.0.1")
        self.requires("flatbuffers/23.5.26")
        self.requires("safeint/3.0.28")
        self.requires("nlohmann_json/3.11.3")
        self.requires("ms-gsl/4.0.0")
        if self.settings.os != "Windows":
            self.requires("nsync/1.26.0")
        else:
            self.requires("wil/1.0.230629.1")
        self.requires("re2/20251105")
        self.requires("cpuinfo/cci.20251210")
        if self.options.with_xnnpack:
            self.requires("xnnpack/cci.20220801")
            self.requires("pthreadpool/cci.20231129")
        # eigen, re2, cpuinfo, boost/mp11 have no matching conan version — fetched by cmake via FetchContent

    def package_id(self):
        _requires = [
            "onnx", "abseil", "protobuf", "date", "flatbuffers",
            "safeint", "nlohmann_json", "ms-gsl", "re2", "cpuinfo",
            # conditional:
            "nsync", "wil", "xnnpack", "pthreadpool",
        ]
        for name in _requires:
            if name in self.info.requires:
                self.info.requires[name].full_package_mode()

    def validate(self):
        check_min_cppstd(self, 17)
        onnx = self.dependencies["onnx"]
        if not onnx.options.disable_static_registration:
            raise ConanInvalidConfiguration(
                f"{self.ref} requires onnx compiled with `-o onnx:disable_static_registration=True`."
            )
        if onnx.options.get_safe("shared"):
            raise ConanInvalidConfiguration("There are link errors using 'onnx/*:shared=True',"
                                            " use '-o onnx/*:shared=False' instead.")

    def validate_build(self):
        if self.settings.os == "Windows" and self.dependencies["abseil"].options.shared:
            raise ConanInvalidConfiguration("Using abseil shared on Windows leads to link errors.")

    def source(self):
        if os.path.exists(os.path.join(self.source_folder, "cmake", "CMakeLists.txt")):
            self.output.info("Sources found in source_folder (from export_sources), skipping download")
        else:
            self.output.info(f"Sources not found in {self.source_folder}, downloading tarball")
            get(self, **self.conan_data["sources"][self.version], strip_root=True)
        self._patch_sources()

    @staticmethod
    def _conan_home():
        # Resolve the Conan home exactly as Conan does (CONAN_HOME env, then .conanrc, then the
        # ~/.conan2 default), reusing Conan's own resolver so .conanrc and ~ expansion stay correct.
        # The import is internal API; if it ever moves, degrade to the env/default path rather than
        # break the recipe. Returns an absolute path.
        try:
            from conan.internal.paths import get_conan_user_home
            return os.path.abspath(get_conan_user_home())
        except ImportError:
            env_home = os.getenv("CONAN_HOME")
            if env_home:
                return os.path.abspath(os.path.expanduser(env_home))
            return os.path.join(os.path.expanduser("~"), ".conan2")

    def generate(self):
        tc = CMakeToolchain(self)
        # Allow cmake to fetch eigen, re2, cpuinfo, boost/mp11 via FetchContent
        tc.variables["FETCHCONTENT_FULLY_DISCONNECTED"] = False
        # Persist FetchContent downloads across Conan rebuilds (new package hash = new build dir).
        # Anchor to the Conan home so the cache lives on the same persistent storage as the Conan
        # cache (in CI it is a runner volume mounted as CONAN_HOME); fall back to ~/.conan2 off-CI.
        tc.variables["FETCHCONTENT_BASE_DIR"] = os.path.join(self._conan_home(), "fetchcontent")

        tc.variables["onnxruntime_BUILD_SHARED_LIB"] = self.options.shared
        tc.variables["onnxruntime_USE_FULL_PROTOBUF"] = not self.dependencies["protobuf"].options.lite
        tc.variables["onnxruntime_USE_XNNPACK"] = self.options.with_xnnpack

        tc.variables["onnxruntime_BUILD_UNIT_TESTS"] = False
        tc.variables["onnxruntime_DISABLE_CONTRIB_OPS"] = False
        tc.variables["onnxruntime_USE_FLASH_ATTENTION"] = False
        tc.variables["onnxruntime_DISABLE_RTTI"] = False
        tc.variables["onnxruntime_DISABLE_EXCEPTIONS"] = False

        tc.variables["onnxruntime_ARMNN_RELU_USE_CPU"] = False
        tc.variables["onnxruntime_ARMNN_BN_USE_CPU"] = False
        tc.variables["onnxruntime_ENABLE_CPU_FP16_OPS"] = True
        tc.variables["onnxruntime_ENABLE_EAGER_MODE"] = False
        tc.variables["onnxruntime_ENABLE_LAZY_TENSOR"] = False

        tc.variables["onnxruntime_ENABLE_CUDA_EP_INTERNAL_TESTS"] = False
        tc.variables["onnxruntime_USE_NEURAL_SPEED"] = False
        tc.variables["onnxruntime_USE_MEMORY_EFFICIENT_ATTENTION"] = True

        # Disable a warning that gets converted to an error
        tc.preprocessor_definitions["_SILENCE_ALL_CXX23_DEPRECATION_WARNINGS"] = "1"
        tc.generate()

        deps = CMakeDeps(self)
        deps.set_property("flatbuffers", "cmake_target_name", "flatbuffers::flatbuffers")
        deps.generate()

    def _patch_sources(self):
        apply_conandata_patches(self)
        replace_in_file(self, os.path.join(self.source_folder, "cmake", "CMakeLists.txt"),
                        "if (Git_FOUND)", "if (FALSE)")
        # GitLab regenerates zip archives, making SHA1 hashes unreliable; remove the hash check for eigen
        replace_in_file(self, os.path.join(self.source_folder, "cmake", "external", "eigen.cmake"),
                        "URL_HASH SHA1=${DEP_SHA1_eigen}\n",
                        "")
        # When abseil is provided by Conan (find_package), include dirs are not set globally;
        # add them explicitly so onnxruntime headers can find absl/ includes
        replace_in_file(self, os.path.join(self.source_folder, "cmake", "external", "abseil-cpp.cmake"),
                        "message(STATUS \"Abseil source dir:\" ${ABSEIL_SOURCE_DIR})",
                        "message(STATUS \"Abseil source dir:\" ${ABSEIL_SOURCE_DIR})\n"
                        "if(NOT ABSEIL_SOURCE_DIR)\n"
                        "  include_directories(${absl_INCLUDE_DIRS})\n"
                        "endif()")

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_script_folder="cmake", cli_args=["--compile-no-warning-as-error"])
        cmake.build()

    def package(self):
        copy(self, pattern="LICENSE", dst=os.path.join(self.package_folder, "licenses"), src=self.source_folder)
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))

    def package_info(self):
        if self.options.shared:
            self.cpp_info.libs = ["onnxruntime"]
        else:
            # order is important
            # https://github.com/microsoft/onnxruntime/blob/v1.23.2/cmake/onnxruntime.cmake#L238
            onnxruntime_libs = [
                "session",
                *(["providers_xnnpack"] if self.options.with_xnnpack else []),
                "optimizer",
                "providers",
                "lora",
                "framework",
                "graph",
                "util",
                "mlas",
                "common",
                "flatbuffers",
            ]
            self.cpp_info.libs = [f"onnxruntime_{lib}" for lib in onnxruntime_libs]

        self.cpp_info.includedirs.append("include/onnxruntime")
        if not self.options.shared:
            self.cpp_info.includedirs.append("include/onnxruntime/core/session")

        if self.settings.os in ["Linux", "Android", "FreeBSD", "SunOS", "AIX"]:
            self.cpp_info.system_libs.append("m")
        if self.settings.os in ["Linux", "FreeBSD", "SunOS", "AIX"]:
            self.cpp_info.system_libs.append("pthread")
        if is_apple_os(self):
            self.cpp_info.frameworks.append("Foundation")
        if self.settings.os == "Windows":
            self.cpp_info.system_libs.append("shlwapi")

        self.cpp_info.set_property("cmake_file_name", "onnxruntime")
        self.cpp_info.set_property("cmake_target_name", "onnxruntime::onnxruntime")
        self.cpp_info.set_property("pkg_config_name", "onnxruntime")
