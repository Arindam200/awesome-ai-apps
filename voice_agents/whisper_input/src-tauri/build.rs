fn main() {
    #[cfg(target_os = "macos")]
    build_qwen_asr_macos();

    tauri_build::build();
}

/// 编译 antirez/qwen-asr 的 C 源（仅 macOS）。
///
/// 上游 Makefile `make blas` 等价配置：BLAS 加速通过 Accelerate framework，
/// `USE_BLAS` + `ACCELERATE_NEW_LAPACK` 是必要宏。
/// `-march=native` 这里**不**用——分发二进制要可移植，cc crate 在 release 下
/// 默认带 `-O2`，加上 `-O3` 提一档；NEON/AVX 在源码里有 `#ifdef` 自动分派。
#[cfg(target_os = "macos")]
fn build_qwen_asr_macos() {
    const VENDOR: &str = "vendor/qwen-asr";
    const SOURCES: &[&str] = &[
        "qwen_asr.c",
        "qwen_asr_kernels.c",
        "qwen_asr_kernels_generic.c",
        "qwen_asr_kernels_neon.c",
        "qwen_asr_kernels_avx.c",
        "qwen_asr_audio.c",
        "qwen_asr_encoder.c",
        "qwen_asr_decoder.c",
        "qwen_asr_tokenizer.c",
        "qwen_asr_safetensors.c",
    ];

    let mut build = cc::Build::new();
    build
        .include(VENDOR)
        .define("USE_BLAS", None)
        .define("ACCELERATE_NEW_LAPACK", None)
        .flag("-O3")
        .flag("-ffast-math")
        // 上游开 `-Wall -Wextra`；我们把 antirez 的代码当三方依赖，把无关警告压成静默
        // 避免 build log 噪音淹没我们自己的告警。
        .flag("-Wno-unused-parameter")
        .flag("-Wno-unused-variable")
        .flag("-Wno-unused-function")
        .flag("-Wno-sign-compare")
        .warnings(false);

    for src in SOURCES {
        let path = format!("{}/{}", VENDOR, src);
        println!("cargo:rerun-if-changed={}", path);
        build.file(path);
    }
    println!("cargo:rerun-if-changed={}/qwen_asr.h", VENDOR);

    build.compile("qwen_asr");

    // BLAS = Accelerate
    println!("cargo:rustc-link-lib=framework=Accelerate");
}
