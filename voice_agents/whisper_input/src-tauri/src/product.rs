pub const PRODUCT_NAME: &str = "Whisper Input";
pub const PRODUCT_NAME_ZH: &str = "轻语输入";
pub const PRODUCT_IDENTIFIER: &str = "com.qingyu.input";
pub const DATA_DIR_NAME: &str = "Qingyu Input";
pub const LEGACY_DATA_DIR_NAME: &str = "OpenLess";
pub const LOG_DIR_NAME: &str = "Whisper Input";
pub const KEYRING_SERVICE_NAME: &str = PRODUCT_IDENTIFIER;
pub const LEGACY_KEYRING_SERVICE_NAME: &str = "com.openless.app";
pub const LOCAL_ASR_PROVIDER_ID: &str = "qingyu-local-fired-asr";
pub const QWEN_REALTIME_ASR_PROVIDER_ID: &str = "qwen3-asr-flash-realtime";
pub const DOUBAO_ASR_PROVIDER_ID: &str = "doubao-streaming-asr-2";
pub const DEFAULT_ASR_PROVIDER_ID: &str = QWEN_REALTIME_ASR_PROVIDER_ID;
pub const QWEN_LLM_PROVIDER_ID: &str = "qwen-llm";
pub const DOUBAO_LLM_PROVIDER_ID: &str = "doubao-llm";
pub const GEMINI_PROVIDER_ID: &str = "gemini";
pub const OPENAI_COMPATIBLE_PROVIDER_ID: &str = "openai-compatible";
pub const DEFAULT_LLM_PROVIDER_ID: &str = QWEN_LLM_PROVIDER_ID;
pub const SHOW_SELECTION_ASK: bool = false;
pub const SHOW_TRANSLATION: bool = false;
pub const SHOW_QWEN_LOCAL_ASR: bool = false;
pub const SHOW_FOUNDRY_LOCAL_ASR: bool = false;
pub const SHOW_LOCAL_ASR_EXPERIMENTS: bool = false;

pub fn is_visible_active_asr_provider(id: &str) -> bool {
    let id = id.trim();
    id == QWEN_REALTIME_ASR_PROVIDER_ID
        || id == DOUBAO_ASR_PROVIDER_ID
        || (SHOW_LOCAL_ASR_EXPERIMENTS && id == LOCAL_ASR_PROVIDER_ID)
        || (SHOW_LOCAL_ASR_EXPERIMENTS && SHOW_QWEN_LOCAL_ASR && id == "local-qwen3")
        || (SHOW_LOCAL_ASR_EXPERIMENTS && SHOW_FOUNDRY_LOCAL_ASR && id == "foundry-local-whisper")
}

pub fn normalize_active_asr_provider_id(id: &str) -> String {
    match id.trim() {
        QWEN_REALTIME_ASR_PROVIDER_ID | "qwen" | "qwen-realtime" | "bailian" => {
            QWEN_REALTIME_ASR_PROVIDER_ID.into()
        }
        DOUBAO_ASR_PROVIDER_ID | "doubao" | "doubao-streaming" | "volcengine" => {
            DOUBAO_ASR_PROVIDER_ID.into()
        }
        LOCAL_ASR_PROVIDER_ID | "local-qwen3" | "foundry-local-whisper" => {
            if SHOW_LOCAL_ASR_EXPERIMENTS {
                id.trim().to_string()
            } else {
                DEFAULT_ASR_PROVIDER_ID.into()
            }
        }
        "" => DEFAULT_ASR_PROVIDER_ID.into(),
        other if is_visible_active_asr_provider(other) => other.to_string(),
        _ => DEFAULT_ASR_PROVIDER_ID.into(),
    }
}

pub fn is_visible_active_llm_provider(id: &str) -> bool {
    matches!(
        id.trim(),
        QWEN_LLM_PROVIDER_ID | DOUBAO_LLM_PROVIDER_ID | GEMINI_PROVIDER_ID
    )
}

pub fn is_advanced_llm_provider(id: &str) -> bool {
    id.trim() == OPENAI_COMPATIBLE_PROVIDER_ID
}

pub fn normalize_active_llm_provider_id(id: &str) -> String {
    match id.trim() {
        "" | QWEN_LLM_PROVIDER_ID | "qwen" | "dashscope" | "alibaba" => QWEN_LLM_PROVIDER_ID.into(),
        DOUBAO_LLM_PROVIDER_ID | "doubao" | "volcengine" | "ark-doubao" => {
            DOUBAO_LLM_PROVIDER_ID.into()
        }
        GEMINI_PROVIDER_ID => GEMINI_PROVIDER_ID.into(),
        OPENAI_COMPATIBLE_PROVIDER_ID | "ark" | "deepseek" | "ollama" | "openai" => {
            OPENAI_COMPATIBLE_PROVIDER_ID.into()
        }
        _ => OPENAI_COMPATIBLE_PROVIDER_ID.into(),
    }
}

#[cfg(test)]
mod cloud_first_tests {
    use super::*;

    #[test]
    fn defaults_are_qwen_realtime_asr_and_qwen_llm() {
        assert_eq!(DEFAULT_ASR_PROVIDER_ID, QWEN_REALTIME_ASR_PROVIDER_ID);
        assert_eq!(DEFAULT_LLM_PROVIDER_ID, QWEN_LLM_PROVIDER_ID);
    }

    #[test]
    fn normal_visible_llm_providers_are_qwen_doubao_and_gemini_with_openai_advanced() {
        assert!(is_visible_active_llm_provider(QWEN_LLM_PROVIDER_ID));
        assert!(is_visible_active_llm_provider(DOUBAO_LLM_PROVIDER_ID));
        assert!(is_visible_active_llm_provider(GEMINI_PROVIDER_ID));
        assert!(!is_visible_active_llm_provider(
            OPENAI_COMPATIBLE_PROVIDER_ID
        ));
        assert!(is_advanced_llm_provider(OPENAI_COMPATIBLE_PROVIDER_ID));
        assert!(!is_advanced_llm_provider(QWEN_LLM_PROVIDER_ID));
        assert!(!is_advanced_llm_provider(DOUBAO_LLM_PROVIDER_ID));
        assert!(!is_advanced_llm_provider(GEMINI_PROVIDER_ID));
    }

    #[test]
    fn normal_visible_asr_providers_are_qwen_and_doubao_only() {
        assert!(is_visible_active_asr_provider(
            QWEN_REALTIME_ASR_PROVIDER_ID
        ));
        assert!(is_visible_active_asr_provider(DOUBAO_ASR_PROVIDER_ID));
        assert!(!is_visible_active_asr_provider(LOCAL_ASR_PROVIDER_ID));
        assert!(!is_visible_active_asr_provider("bailian"));
        assert!(!is_visible_active_asr_provider("whisper"));
        assert!(!is_visible_active_asr_provider("local-qwen3"));
        assert!(!is_visible_active_asr_provider("foundry-local-whisper"));
    }

    #[test]
    fn legacy_asr_ids_normalize_without_returning_to_local_first() {
        assert_eq!(
            normalize_active_asr_provider_id(""),
            QWEN_REALTIME_ASR_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_asr_provider_id("qwen"),
            QWEN_REALTIME_ASR_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_asr_provider_id("bailian"),
            QWEN_REALTIME_ASR_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_asr_provider_id(LOCAL_ASR_PROVIDER_ID),
            QWEN_REALTIME_ASR_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_asr_provider_id("volcengine"),
            DOUBAO_ASR_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_asr_provider_id(DOUBAO_ASR_PROVIDER_ID),
            DOUBAO_ASR_PROVIDER_ID
        );
    }

    #[test]
    fn llm_defaults_to_qwen_but_preserves_gemini_and_openai_compatible_advanced() {
        assert_eq!(normalize_active_llm_provider_id(""), QWEN_LLM_PROVIDER_ID);
        assert_eq!(
            normalize_active_llm_provider_id("qwen"),
            QWEN_LLM_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_llm_provider_id("dashscope"),
            QWEN_LLM_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_llm_provider_id("gemini"),
            GEMINI_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_llm_provider_id("doubao"),
            DOUBAO_LLM_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_llm_provider_id("volcengine"),
            DOUBAO_LLM_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_llm_provider_id(OPENAI_COMPATIBLE_PROVIDER_ID),
            OPENAI_COMPATIBLE_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_llm_provider_id("ark"),
            OPENAI_COMPATIBLE_PROVIDER_ID
        );
        assert_eq!(
            normalize_active_llm_provider_id("deepseek"),
            OPENAI_COMPATIBLE_PROVIDER_ID
        );
    }

    #[test]
    fn unknown_legacy_llm_ids_normalize_to_openai_compatible() {
        for id in [
            "siliconflow",
            "custom",
            "openrouterFree",
            "unrecognized-provider",
        ] {
            assert_eq!(
                normalize_active_llm_provider_id(id),
                OPENAI_COMPATIBLE_PROVIDER_ID
            );
        }
    }

    #[test]
    fn legacy_local_asr_ids_normalize_to_qwen_realtime() {
        for id in [
            LOCAL_ASR_PROVIDER_ID,
            "local-qwen3",
            "foundry-local-whisper",
            "whisper",
        ] {
            assert_eq!(
                normalize_active_asr_provider_id(id),
                QWEN_REALTIME_ASR_PROVIDER_ID
            );
        }
    }
}
