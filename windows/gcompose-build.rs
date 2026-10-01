// Windows build of the pinned Genesis compositor plus the maintained media patch.
use std::{env, path::PathBuf};
fn main() {
    let ffmpeg = PathBuf::from(env::var_os("GENESIS_FFMPEG_SDK").expect("GENESIS_FFMPEG_SDK"));
    let cl_headers = env::var("GENESIS_OPENCL_HEADERS").expect("GENESIS_OPENCL_HEADERS");
    let cl_lib = env::var("GENESIS_OPENCL_LIB").expect("GENESIS_OPENCL_LIB");
    let compatibility = env::var("GENESIS_WINDOWS_COMPAT").expect("GENESIS_WINDOWS_COMPAT");
    let mut build = cc::Build::new();
    build.include(ffmpeg.join("include")).include(cl_headers).include(compatibility)
        .define("_USE_MATH_DEFINES", None).define("_CRT_SECURE_NO_WARNINGS", None)
        .flag_if_supported("/std:c11").opt_level(2).warnings(false);
    for file in ["fpx_decode.c", "fpx_gpu.c", "fpx_encode.c", "fpx_aread.c", "fpx_audio.c"] {
        build.file(format!("csrc/{file}"));
        println!("cargo:rerun-if-changed=csrc/{file}");
    }
    build.compile("fpxengine");
    println!("cargo:rustc-link-search=native={}", ffmpeg.join("lib").display());
    for library in ["avformat", "avcodec", "swscale", "swresample", "avfilter", "avutil"] {
        println!("cargo:rustc-link-lib={library}");
    }
    println!("cargo:rustc-link-search=native={cl_lib}");
    println!("cargo:rustc-link-lib=OpenCL");
}
