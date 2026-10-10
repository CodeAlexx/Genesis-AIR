// Windows build of the pinned Genesis compositor plus the maintained media patch.
use std::{env, fs, path::PathBuf};
fn main() {
    for name in ["GENESIS_FFMPEG_SDK", "GENESIS_OPENCL_HEADERS", "GENESIS_OPENCL_LIB", "GENESIS_WINDOWS_COMPAT"] {
        println!("cargo:rerun-if-env-changed={name}");
    }
    let ffmpeg = PathBuf::from(env::var_os("GENESIS_FFMPEG_SDK").expect("GENESIS_FFMPEG_SDK"));
    let cl_headers = env::var("GENESIS_OPENCL_HEADERS").expect("GENESIS_OPENCL_HEADERS");
    let cl_lib = env::var("GENESIS_OPENCL_LIB").expect("GENESIS_OPENCL_LIB");
    let compatibility = env::var("GENESIS_WINDOWS_COMPAT").expect("GENESIS_WINDOWS_COMPAT");
    let mut build = cc::Build::new();
    build.include(ffmpeg.join("include")).include(cl_headers).include(&compatibility)
        .define("_USE_MATH_DEFINES", None).define("_CRT_SECURE_NO_WARNINGS", None)
        .flag_if_supported("/std:c11").opt_level(2).warnings(false);
    for file in ["fpx_decode.c", "fpx_gpu.c", "fpx_encode.c", "fpx_aread.c", "fpx_audio.c"] {
        build.file(format!("csrc/{file}"));
        println!("cargo:rerun-if-changed=csrc/{file}");
    }
    let runtime = PathBuf::from(&compatibility).parent().unwrap().join("media-runtime.c");
    build.file(&runtime);
    println!("cargo:rerun-if-changed={}", runtime.display());
    let preview = PathBuf::from(&compatibility).parent().unwrap().join("hdr-preview.c");
    let shader = preview.with_extension("hlsl");
    let mut source = fs::read(&shader).expect("HDR preview shader");
    source.push(0);
    let header = format!("static const unsigned char genesis_hdr_preview_shader[] = {{{}}};\n",
        source.iter().map(|b| b.to_string()).collect::<Vec<_>>().join(","));
    let generated = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    fs::write(generated.join("genesis-hdr-preview-shader.h"), header).unwrap();
    build.include(generated).file(&preview);
    println!("cargo:rerun-if-changed={}", preview.display());
    println!("cargo:rerun-if-changed={}", shader.display());
    build.compile("fpxengine");
    let imports = env::var("GENESIS_FFMPEG_IMPORTS").expect("GENESIS_FFMPEG_IMPORTS");
    println!("cargo:rerun-if-env-changed=GENESIS_FFMPEG_IMPORTS");
    println!("cargo:rustc-link-search=native={imports}");
    for library in ["avformat", "avcodec", "swscale", "swresample", "avfilter", "avutil"] {
        println!("cargo:rustc-link-lib={library}");
    }
    // Bind native imports after startup loads the shared MM-AIR library set.
    for dll in ["avformat-63.dll", "avcodec-63.dll", "swscale-10.dll", "swresample-7.dll", "avfilter-12.dll", "avutil-61.dll"] {
        println!("cargo:rustc-link-arg=/DELAYLOAD:{dll}");
    }
    println!("cargo:rustc-link-lib=delayimp");
    println!("cargo:rustc-link-search=native={cl_lib}");
    println!("cargo:rustc-link-lib=OpenCL");
}
