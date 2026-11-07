SUMMARY = "llama.cpp CPU inference: llama-server and llama-cli"
DESCRIPTION = "Local LLM inference in C/C++ (ggml). Built CPU-only for INT: no CUDA, Vulkan, \
OpenCL, HIP or SYCL, no embedded web UI, no build-time downloads, no subprocess-based \
server tools. x86-64 builds every CPU variant as a loadable backend so one package \
runs well from SSE4.2 to AVX-512 machines."
HOMEPAGE = "https://github.com/ggml-org/llama.cpp"
# llama.cpp and ggml: MIT. Vendored: nlohmann/json and cpp-httplib (MIT),
# sheredom/subprocess.h (Unlicense; compiled out by LLAMA_SUBPROCESS=OFF),
# stb_image and miniaudio (public domain or MIT, dual).
LICENSE = "MIT & Unlicense"
LIC_FILES_CHKSUM = "file://LICENSE;md5=223b26b3c1143120c87e2b13111d3e99 \
                    file://licenses/LICENSE-jsonhpp;md5=d9545308f01613f54de6f21134ec51f3 \
                    file://vendor/cpp-httplib/LICENSE;md5=1321bdf796c67e3a8ab8e352dd81474b \
                    file://vendor/sheredom/subprocess.h;beginline=7;endline=30;md5=3cd197ec16ad94ed76ca1363db1d657d"

# Upstream release v0.9.0 (same commit as build tag b12110).
SRC_URI = "git://github.com/ggml-org/llama.cpp.git;protocol=https;branch=master;tag=v${PV}"
SRCREV = "cd959bae99ff4bed22bef2604f45241c09bbb8c8"
LLAMA_BUILD_NUMBER = "12110"

inherit cmake

# Only x86-64 is configured (all-variants CPU backend below).
COMPATIBLE_HOST = "x86_64.*-linux"

EXTRA_OECMAKE = " \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON \
    -DLLAMA_BUILD_IS_DEV=OFF \
    -DLLAMA_BUILD_NUMBER=${LLAMA_BUILD_NUMBER} \
    -DLLAMA_BUILD_COMMIT=${@d.getVar('SRCREV')[:7]} \
    -DLLAMA_BUILD_COMMON=ON \
    -DLLAMA_BUILD_TOOLS=ON \
    -DLLAMA_BUILD_SERVER=ON \
    -DLLAMA_BUILD_APP=OFF \
    -DLLAMA_BUILD_EXAMPLES=OFF \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_UI=OFF \
    -DLLAMA_USE_PREBUILT_UI=OFF \
    -DLLAMA_CONNECT=OFF \
    -DLLAMA_OPENSSL=OFF \
    -DLLAMA_SUBPROCESS=OFF \
    -DLLAMA_LLGUIDANCE=OFF \
    -DLLAMA_TOOLS_INSTALL=ON \
    -DGGML_NATIVE=OFF \
    -DGGML_CCACHE=OFF \
    -DGGML_OPENMP=OFF \
    -DGGML_CUDA=OFF \
    -DGGML_VULKAN=OFF \
    -DGGML_OPENCL=OFF \
    -DGGML_HIP=OFF \
    -DGGML_SYCL=OFF \
    -DGGML_RPC=OFF \
    -DGGML_BLAS=OFF \
    -DGGML_KLEIDIAI=OFF \
"
EXTRA_OECMAKE:append:x86-64 = " \
    -DGGML_BACKEND_DL=ON \
    -DGGML_CPU_ALL_VARIANTS=ON \
    -DGGML_BACKEND_DIR=${libdir}/ggml \
"

do_install:append() {
    # Ship only the two programs INT uses; the libraries stay for them.
    for tool in ${D}${bindir}/*; do
        case "$(basename "$tool")" in
            llama-server|llama-cli) ;;
            *) rm -f "$tool" ;;
        esac
    done
    # Since 0.9 each tool links a private unversioned libllama-<tool>-impl.so;
    # keep only those of the shipped tools.
    for lib in ${D}${libdir}/libllama-*-impl.so; do
        case "$(basename "$lib")" in
            libllama-server-impl.so|libllama-cli-impl.so) ;;
            *) rm -f "$lib" ;;
        esac
    done
}

# The libraries are unversioned by design (CPU backends loaded at runtime and
# per-tool implementation libraries): they are runtime files, not -dev links.
FILES_SOLIBSDEV = ""
FILES:${PN} += "${libdir}/*.so ${libdir}/ggml/*.so"
INSANE_SKIP:${PN} += "dev-so"
