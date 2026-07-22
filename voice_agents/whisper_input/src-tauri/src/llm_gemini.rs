//! 谷歌 Gemini 原生 generateContent / streamGenerateContent 客户端。
//!
//! 为什么不复用 `polish.rs::OpenAICompatibleLLMProvider`：
//! 1. **思考模式控制**——Gemini 原生 `thinkingConfig` 比 OpenAI 兼容 shim
//!    的 provider 私有字段更直接；OpenLess 只做渠道级开关，不维护单模型适配表。
//! 2. **认证机制**——原生用 `x-goog-api-key` header（Bearer 不被识别），
//!    OpenAICompatibleLLMProvider 写死了 Bearer Authorization。
//! 3. **请求/响应 shape**——原生 `contents` 走 `role: user|model`，没有
//!    chat completions 的 system role；要走 `systemInstruction` 字段。
//!
//! prompt 装配 (system_prompt / user_prompt / qa system_prompt) 复用
//! `polish.rs::compose_*` pub(crate) 装配函数，避免两路 LLM 客户端漂移。
//! `clean_polish_output` 也复用——polish 提示词禁的"以下是整理后的内容"
//! 前缀只有走它才能在原生路径上同样剥离。

use std::time::{Duration, Instant};

use serde_json::{json, Value};

use crate::polish::{
    clean_polish_output, compose_polish_prompts, compose_qa_system_prompt,
    compose_translate_prompts, normalize_polish_layout, safe_str_slice, LLMError,
};
use crate::types::{ChineseScriptPreference, OutputLanguagePreference, PolishMode, QaChatMessage};

const DEFAULT_TEMPERATURE: f32 = 0.3;
const DEFAULT_REQUEST_TIMEOUT_SECS: u64 = 30;
const BODY_PREVIEW_LIMIT: usize = 200;
pub const GEMINI_DEFAULT_BASE_URL: &str = "https://generativelanguage.googleapis.com/v1beta";
pub const GEMINI_DEFAULT_MODEL: &str = "gemini-2.5-flash";

#[derive(Clone, Debug)]
pub struct GeminiConfig {
    pub api_key: String,
    pub model: String,
    /// e.g. `https://generativelanguage.googleapis.com/v1beta`。允许末尾带 `/`。
    /// 后端拼成 `{base_url}/models/{model}:generateContent`。
    pub base_url: String,
    pub temperature: f32,
    pub request_timeout_secs: u64,
    /// true = 不下发关闭思考的 thinkingConfig，让模型按自身默认思考；
    /// false = 下发 Gemini 原生渠道级最低思考配置。
    pub thinking_enabled: bool,
}

impl GeminiConfig {
    pub fn new(
        api_key: impl Into<String>,
        model: impl Into<String>,
        base_url: impl Into<String>,
    ) -> Self {
        Self {
            api_key: api_key.into(),
            model: model.into(),
            base_url: base_url.into(),
            temperature: DEFAULT_TEMPERATURE,
            request_timeout_secs: DEFAULT_REQUEST_TIMEOUT_SECS,
            thinking_enabled: false,
        }
    }

    pub fn with_thinking_enabled(mut self, enabled: bool) -> Self {
        self.thinking_enabled = enabled;
        self
    }
}

pub struct GeminiProvider {
    config: GeminiConfig,
    client: reqwest::Client,
}

impl GeminiProvider {
    pub fn new(config: GeminiConfig) -> Self {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(config.request_timeout_secs))
            .build()
            .unwrap_or_else(|_| reqwest::Client::new());
        Self { config, client }
    }

    pub async fn polish(
        &self,
        raw_text: &str,
        mode: PolishMode,
        hotwords: &[String],
        working_languages: &[String],
        chinese_script_preference: ChineseScriptPreference,
        output_language_preference: OutputLanguagePreference,
        front_app: Option<&str>,
        prior_turns: &[(String, String)],
    ) -> Result<String, LLMError> {
        let (system_prompt, user_prompt) = compose_polish_prompts(
            raw_text,
            mode,
            hotwords,
            working_languages,
            chinese_script_preference,
            output_language_preference,
            front_app,
            !prior_turns.is_empty(),
        );

        let contents = build_polish_history_contents(prior_turns, &user_prompt);
        let body = self.build_generate_body(&system_prompt, contents);
        let url = generate_content_url(&self.config.base_url, &self.config.model);

        log::info!(
            "[llm] POST {} provider=gemini model={} prior_turns={}",
            url,
            self.config.model,
            prior_turns.len()
        );

        let body_text = self.send_unary(&url, &body).await?;
        let raw = extract_assistant_content(&body_text)?;
        Ok(normalize_polish_layout(mode, &clean_polish_output(&raw)))
    }

    pub async fn polish_streaming<F, C>(
        &self,
        raw_text: &str,
        mode: PolishMode,
        hotwords: &[String],
        working_languages: &[String],
        chinese_script_preference: ChineseScriptPreference,
        output_language_preference: OutputLanguagePreference,
        front_app: Option<&str>,
        prior_turns: &[(String, String)],
        on_delta: F,
        should_cancel: C,
    ) -> Result<String, LLMError>
    where
        F: Fn(&str) + Send + Sync,
        C: Fn() -> bool + Send + Sync,
    {
        let (system_prompt, user_prompt) = compose_polish_prompts(
            raw_text,
            mode,
            hotwords,
            working_languages,
            chinese_script_preference,
            output_language_preference,
            front_app,
            !prior_turns.is_empty(),
        );

        let contents = build_polish_history_contents(prior_turns, &user_prompt);
        let body = self.build_generate_body(&system_prompt, contents);
        let url = stream_generate_content_url(&self.config.base_url, &self.config.model);

        log::info!(
            "[llm] POST {} provider=gemini model={} prior_turns={} stream=true",
            url,
            self.config.model,
            prior_turns.len()
        );

        let raw = self
            .send_streaming(&url, &body, on_delta, should_cancel)
            .await?;
        Ok(normalize_polish_layout(mode, &clean_polish_output(&raw)))
    }

    pub async fn translate_to(
        &self,
        raw_text: &str,
        target_language: &str,
        working_languages: &[String],
        chinese_script_preference: ChineseScriptPreference,
        _output_language_preference: OutputLanguagePreference,
        front_app: Option<&str>,
    ) -> Result<String, LLMError> {
        let (system_prompt, user_prompt) = compose_translate_prompts(
            raw_text,
            target_language,
            working_languages,
            chinese_script_preference,
            front_app,
        );

        let contents = vec![user_content(&user_prompt)];
        let body = self.build_generate_body(&system_prompt, contents);
        let url = generate_content_url(&self.config.base_url, &self.config.model);

        log::info!(
            "[llm] POST {} provider=gemini model={} translate=true",
            url,
            self.config.model
        );

        let body_text = self.send_unary(&url, &body).await?;
        let raw = extract_assistant_content(&body_text)?;
        Ok(clean_polish_output(&raw))
    }

    /// 划词语音问答的流式回答。Gemini 原生 SSE: `:streamGenerateContent?alt=sse`，
    /// 每个 `data: {...}` 帧里 `candidates[0].content.parts[0].text` 是 delta；
    /// 流结束没有 `[DONE]` sentinel，stream 自然终止。
    pub async fn answer_chat_streaming<F, C>(
        &self,
        messages: &[QaChatMessage],
        working_languages: &[String],
        chinese_script_preference: ChineseScriptPreference,
        output_language_preference: OutputLanguagePreference,
        front_app: Option<&str>,
        on_delta: F,
        should_cancel: C,
    ) -> Result<String, LLMError>
    where
        F: Fn(&str) + Send + Sync,
        C: Fn() -> bool + Send + Sync,
    {
        let system_prompt = compose_qa_system_prompt(
            working_languages,
            chinese_script_preference,
            output_language_preference,
            front_app,
        );

        let contents = qa_messages_to_contents(messages);
        let body = self.build_generate_body(&system_prompt, contents);
        let url = stream_generate_content_url(&self.config.base_url, &self.config.model);

        log::info!(
            "[llm] POST {} provider=gemini model={} chat_turns={} stream=true",
            url,
            self.config.model,
            messages.len()
        );

        self.send_streaming(&url, &body, on_delta, should_cancel)
            .await
    }

    /// `generationConfig` 注入：温度 + 渠道级 thinkingConfig。
    fn build_generate_body(&self, system_prompt: &str, contents: Vec<Value>) -> Value {
        let mut generation_config = json!({ "temperature": self.config.temperature });
        if !self.config.thinking_enabled {
            generation_config["thinkingConfig"] = disabled_thinking_config();
        }
        json!({
            "systemInstruction": system_instruction(system_prompt),
            "contents": contents,
            "generationConfig": generation_config,
        })
    }

    async fn send_unary(&self, url: &str, body: &Value) -> Result<String, LLMError> {
        let mut request = self
            .client
            .post(url)
            .header("Content-Type", "application/json");
        if !self.config.api_key.trim().is_empty() {
            request = request.header("x-goog-api-key", self.config.api_key.as_str());
        }
        let request = request.json(body);

        let response = match request.send().await {
            Ok(r) => r,
            Err(e) => {
                if e.is_timeout() {
                    return Err(LLMError::Timeout);
                }
                return Err(LLMError::Network(e.to_string()));
            }
        };

        let status = response.status();
        let body_text = response
            .text()
            .await
            .map_err(|e| LLMError::Network(e.to_string()))?;

        let preview_end = BODY_PREVIEW_LIMIT.min(body_text.len());
        let preview = safe_str_slice(&body_text, preview_end);
        log::info!("[llm] HTTP {} body={}", status.as_u16(), preview);

        if !status.is_success() {
            return Err(LLMError::InvalidResponse {
                status: status.as_u16(),
                body: preview.to_string(),
            });
        }

        Ok(body_text)
    }

    async fn send_streaming<F, C>(
        &self,
        url: &str,
        body: &Value,
        on_delta: F,
        should_cancel: C,
    ) -> Result<String, LLMError>
    where
        F: Fn(&str) + Send + Sync,
        C: Fn() -> bool + Send + Sync,
    {
        let mut request = self
            .client
            .post(url)
            .header("Content-Type", "application/json")
            .header("Accept", "text/event-stream");
        if !self.config.api_key.trim().is_empty() {
            request = request.header("x-goog-api-key", self.config.api_key.as_str());
        }
        let request = request.json(body);
        let started_at = Instant::now();
        let mut ttft_logged = false;

        let response = match request.send().await {
            Ok(r) => r,
            Err(e) => {
                if e.is_timeout() {
                    return Err(LLMError::Timeout);
                }
                return Err(LLMError::Network(e.to_string()));
            }
        };

        let status = response.status();
        if !status.is_success() {
            let body_text = response
                .text()
                .await
                .map_err(|e| LLMError::Network(e.to_string()))?;
            let preview_end = BODY_PREVIEW_LIMIT.min(body_text.len());
            let preview = safe_str_slice(&body_text, preview_end);
            log::error!("[llm] HTTP {} body={}", status.as_u16(), preview);
            return Err(LLMError::InvalidResponse {
                status: status.as_u16(),
                body: preview.to_string(),
            });
        }

        let mut response = response;
        // 字节级缓冲——`reqwest::chunk()` 可能在多字节 UTF-8 字符（CJK / emoji）
        // 中间切开，对每个 chunk 独立 from_utf8 会把合法的 SSE 流当成
        // "non-utf8 SSE chunk" 直接 fail（PR #398 pr_agent 实测漏洞）。
        // SSE 帧分隔符 `\n\n` 两字节都是 ASCII (0x0A)，永远不会落在多字节字符中部，
        // 所以按字节定位完整 event、再对完整 event 做 from_utf8 永远安全。
        let mut byte_buffer: Vec<u8> = Vec::new();
        let mut full_text = String::new();
        loop {
            // 与 polish.rs streaming 同款取消旗标——用户取消 / 关浮窗时立即 break，
            // 不再 drain HTTP body 烧 quota。
            if should_cancel() {
                log::info!("[llm] gemini stream cancelled by caller; breaking SSE loop");
                break;
            }
            let chunk_opt = response
                .chunk()
                .await
                .map_err(|e| LLMError::Network(e.to_string()))?;
            let Some(chunk) = chunk_opt else { break };
            byte_buffer.extend_from_slice(&chunk);

            for event in drain_complete_sse_events(&mut byte_buffer) {
                for line in event.lines() {
                    let Some(payload) = line
                        .strip_prefix("data: ")
                        .or_else(|| line.strip_prefix("data:"))
                    else {
                        continue;
                    };
                    let payload = payload.trim();
                    if payload.is_empty() {
                        continue;
                    }
                    let v: Value = match serde_json::from_str(payload) {
                        Ok(v) => v,
                        Err(e) => {
                            log::warn!(
                                "[llm] gemini SSE parse skip: {e}; payload preview: {}",
                                safe_str_slice(payload, 80)
                            );
                            continue;
                        }
                    };
                    // Gemini SSE: candidates[0].content.parts[*].text
                    if let Some(parts) = v["candidates"][0]["content"]["parts"].as_array() {
                        for part in parts {
                            if let Some(delta) = part["text"].as_str() {
                                if !delta.is_empty() {
                                    if !ttft_logged {
                                        ttft_logged = true;
                                        log::info!(
                                            "[llm] gemini streaming metrics model={} stream_enabled=true ttft_ms={}",
                                            self.config.model,
                                            started_at.elapsed().as_millis()
                                        );
                                    }
                                    full_text.push_str(delta);
                                    on_delta(delta);
                                }
                            }
                        }
                    }
                }
            }
        }

        log::info!(
            "[llm] HTTP 200 gemini stream done; total chars={} total_latency_ms={}",
            full_text.chars().count(),
            started_at.elapsed().as_millis()
        );
        log::info!(
            "[llm] gemini streaming metrics model={} stream_enabled=true total_latency_ms={} chars={}",
            self.config.model,
            started_at.elapsed().as_millis(),
            full_text.chars().count()
        );

        if full_text.is_empty() {
            return Err(LLMError::InvalidResponse {
                status: 200,
                body: "empty stream".to_string(),
            });
        }
        Ok(full_text)
    }
}

// ─────────────────────── 内部辅助 ───────────────────────

fn user_content(text: &str) -> Value {
    json!({ "role": "user", "parts": [{ "text": text }] })
}

fn model_content(text: &str) -> Value {
    json!({ "role": "model", "parts": [{ "text": text }] })
}

fn system_instruction(system_prompt: &str) -> Value {
    json!({ "parts": [{ "text": system_prompt }] })
}

/// 从字节缓冲里取出所有以 SSE 帧分隔符（`\n\n` 或 `\r\n\r\n`）分隔的完整
/// event；剩余不完整字节留在 buffer 里等下一次 chunk 拼接。
///
/// 不变量：两种分隔符的所有字节都是 ASCII（0x0A / 0x0D），永远不会出现在
/// UTF-8 多字节字符的中部位置，所以
/// 1. 按字节查找分隔符 100% 安全；
/// 2. 对完整 event 字节区间 (event_start..delim_start) 做 from_utf8 永远不会因
///    chunk 边界把多字节字符切开而失败；
/// 3. CRLF 与 LF 不会在同一位置都匹配（\r\n\r\n 内部不含 \n\n），按"最早出现"
///    选取分隔符不会歧义。
///
/// 这是 PR #398 pr_agent 指出的两个 SSE 漏洞的合修：
/// (a) 原代码对每个网络 chunk 独立 from_utf8，遇到 CJK / emoji 跨 chunk 切分时
///     直接报错让流挂掉；
/// (b) 原代码只识别 `\n\n`，碰到走 CRLF 风格的服务器流（个别 HTTP/2 中间层、
///     CDN 会做行尾标准化）会以为流是空的——文档没强制 LF only，必须兼容。
fn drain_complete_sse_events(buffer: &mut Vec<u8>) -> Vec<String> {
    let mut events = Vec::new();
    loop {
        let crlf = buffer.windows(4).position(|w| w == b"\r\n\r\n");
        let lf = buffer.windows(2).position(|w| w == b"\n\n");
        let (end, delim_len) = match (crlf, lf) {
            (Some(c), Some(l)) => {
                if c <= l {
                    (c, 4)
                } else {
                    (l, 2)
                }
            }
            (Some(c), None) => (c, 4),
            (None, Some(l)) => (l, 2),
            (None, None) => break,
        };
        let event_str = match std::str::from_utf8(&buffer[..end]) {
            Ok(s) => s.to_string(),
            Err(e) => {
                // 完整 event 自身 UTF-8 不合法（极少见，可能是上游异常）：丢弃此 event 不让流挂掉。
                log::warn!("[llm] gemini SSE event has invalid UTF-8 (skipping): {e}");
                buffer.drain(..end + delim_len);
                continue;
            }
        };
        events.push(event_str);
        buffer.drain(..end + delim_len);
    }
    events
}

/// 多轮 polish 的 contents 序列。
/// 输入约定：`prior_turns` 与 polish.rs 一致（最新在前 newest-first），
/// chat 时间序为 oldest-first，所以这里 `iter().rev()` 反转。
fn build_polish_history_contents(
    prior_turns: &[(String, String)],
    user_prompt: &str,
) -> Vec<Value> {
    let mut contents: Vec<Value> = Vec::with_capacity(prior_turns.len() * 2 + 1);
    for (raw, polished) in prior_turns.iter().rev() {
        contents.push(user_content(&crate::polish::prompts::user_prompt(raw)));
        contents.push(model_content(polished));
    }
    contents.push(user_content(user_prompt));
    contents
}

/// QA chat messages → Gemini contents：assistant role 重命名为 model。
/// QaChatMessage.role 在 polish.rs OpenAI 路径里是 `"user" | "assistant"`；
/// 这里把 `assistant` 翻成 Gemini 的 `model`，其它原样保留。
fn qa_messages_to_contents(messages: &[QaChatMessage]) -> Vec<Value> {
    messages
        .iter()
        .map(|m| {
            let role = if m.role == "assistant" {
                "model"
            } else {
                "user"
            };
            json!({ "role": role, "parts": [{ "text": m.content }] })
        })
        .collect()
}

/// Gemini 原生通道的关闭/最低思考请求。
///
/// OpenLess 不维护 Gemini 单模型适配表；开启时不下发 thinkingConfig，关闭时
/// 使用官方 thinkingConfig 中可表达“关闭思考”的 `thinkingBudget = 0`。若某个
/// 具体模型不支持该字段或不能完全关闭思考，交由 Gemini API 自身处理。
fn disabled_thinking_config() -> Value {
    json!({ "thinkingBudget": 0 })
}

fn generate_content_url(base_url: &str, model: &str) -> String {
    let trimmed = base_url.trim().trim_end_matches('/');
    format!("{trimmed}/models/{model}:generateContent")
}

fn stream_generate_content_url(base_url: &str, model: &str) -> String {
    let trimmed = base_url.trim().trim_end_matches('/');
    format!("{trimmed}/models/{model}:streamGenerateContent?alt=sse")
}

fn extract_assistant_content(body: &str) -> Result<String, LLMError> {
    let json: Value = serde_json::from_str(body)
        .map_err(|e| LLMError::ParseError(format!("not valid JSON: {}", e)))?;
    let candidates = json
        .get("candidates")
        .and_then(|v| v.as_array())
        .ok_or_else(|| LLMError::ParseError("missing candidates array".into()))?;
    let first = candidates
        .first()
        .ok_or_else(|| LLMError::ParseError("candidates array is empty".into()))?;
    let parts = first
        .get("content")
        .and_then(|c| c.get("parts"))
        .and_then(|p| p.as_array())
        .ok_or_else(|| LLMError::ParseError("missing content.parts".into()))?;
    // 把所有 part.text 拼起来。开启思考时模型可能产出多段；逐段拼接避免
    // future-proof 单 part vs 多 part 的差异坑到。
    let mut buf = String::new();
    for part in parts {
        if let Some(t) = part.get("text").and_then(|v| v.as_str()) {
            buf.push_str(t);
        }
    }
    if buf.is_empty() {
        return Err(LLMError::ParseError(
            "candidates[0].content.parts[*].text 为空".into(),
        ));
    }
    Ok(buf)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disabled_thinking_config_uses_channel_level_budget_zero() {
        assert_eq!(disabled_thinking_config(), json!({ "thinkingBudget": 0 }));
    }

    #[test]
    fn generate_content_url_handles_trailing_slash_in_base_url() {
        let a = generate_content_url("https://x/v1beta", "gemini-2.5-flash");
        let b = generate_content_url("https://x/v1beta/", "gemini-2.5-flash");
        assert_eq!(
            a,
            "https://x/v1beta/models/gemini-2.5-flash:generateContent"
        );
        assert_eq!(
            b,
            "https://x/v1beta/models/gemini-2.5-flash:generateContent"
        );
    }

    #[test]
    fn stream_generate_content_url_appends_alt_sse() {
        let a = stream_generate_content_url("https://x/v1beta", "gemini-2.5-flash");
        assert_eq!(
            a,
            "https://x/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse"
        );
    }

    #[test]
    fn extract_assistant_content_concatenates_multiple_parts() {
        let body = r#"{"candidates":[{"content":{"parts":[{"text":"hello "},{"text":"world"}]}}]}"#;
        assert_eq!(extract_assistant_content(body).unwrap(), "hello world");
    }

    #[test]
    fn extract_assistant_content_empty_array_errors() {
        let body = r#"{"candidates":[]}"#;
        assert!(extract_assistant_content(body).is_err());
    }

    #[test]
    fn build_polish_history_contents_orders_oldest_to_newest_and_uses_model_role() {
        // prior_turns 入参约定 newest-first（与 polish.rs::build_polish_history_messages
        // 同源约定）；这里反转为 chat 时间序 oldest-first 喂给 Gemini。
        // assistant role 的 polished 历史必须挂在 Gemini 的 `model` role 上。
        let prior = vec![
            ("raw-newest".into(), "polished-newest".into()),
            ("raw-mid".into(), "polished-mid".into()),
            ("raw-oldest".into(), "polished-oldest".into()),
        ];
        let contents = build_polish_history_contents(&prior, "USER_NOW");
        // 3×(user/model) + 1 当前 user = 7
        assert_eq!(contents.len(), 7);
        assert_eq!(contents[0]["role"], "user");
        assert!(contents[0]["parts"][0]["text"]
            .as_str()
            .unwrap()
            .contains("raw-oldest"));
        assert_eq!(contents[1]["role"], "model");
        assert_eq!(contents[1]["parts"][0]["text"], "polished-oldest");
        assert_eq!(contents[5]["role"], "model");
        assert_eq!(contents[5]["parts"][0]["text"], "polished-newest");
        assert_eq!(contents[6]["role"], "user");
        assert_eq!(contents[6]["parts"][0]["text"], "USER_NOW");
    }

    #[test]
    fn qa_messages_assistant_role_is_remapped_to_model() {
        let messages = vec![
            QaChatMessage {
                role: "user".into(),
                content: "选区是什么意思".into(),
            },
            QaChatMessage {
                role: "assistant".into(),
                content: "这是一段示例文本".into(),
            },
            QaChatMessage {
                role: "user".into(),
                content: "继续问".into(),
            },
        ];
        let contents = qa_messages_to_contents(&messages);
        assert_eq!(contents[0]["role"], "user");
        assert_eq!(contents[1]["role"], "model");
        assert_eq!(contents[2]["role"], "user");
    }

    #[test]
    fn build_generate_body_disabled_includes_channel_level_thinking_budget_zero() {
        let cfg = GeminiConfig::new("k", "any-gemini-model", "https://x/v1beta");
        let provider = GeminiProvider::new(cfg);
        let body = provider.build_generate_body("SYS", vec![user_content("hi")]);
        assert_eq!(
            body["generationConfig"]["thinkingConfig"],
            json!({ "thinkingBudget": 0 })
        );
        assert_eq!(body["systemInstruction"]["parts"][0]["text"], "SYS");
        assert_eq!(body["contents"][0]["role"], "user");
    }

    #[test]
    fn build_generate_body_thinking_enabled_omits_thinking_config() {
        let cfg = GeminiConfig::new("k", "gemini-2.5-flash", "https://x/v1beta")
            .with_thinking_enabled(true);
        let provider = GeminiProvider::new(cfg);
        let body = provider.build_generate_body("SYS", vec![user_content("hi")]);
        assert!(
            body["generationConfig"].get("thinkingConfig").is_none(),
            "开启思考模式时不下发关闭思考的 thinkingConfig"
        );
    }

    #[test]
    fn drain_complete_sse_events_splits_full_event_at_delimiter() {
        let mut buf = b"data: {\"a\":1}\n\ndata: {\"b\":2}\n\ndata: incompl".to_vec();
        let events = drain_complete_sse_events(&mut buf);
        assert_eq!(events, vec!["data: {\"a\":1}", "data: {\"b\":2}"]);
        // 不完整的最后一段保留在 buffer 里等下次 chunk 拼接
        assert_eq!(buf, b"data: incompl");
    }

    #[test]
    fn drain_complete_sse_events_handles_multibyte_split_across_chunks() {
        // 回归 PR #398 pr_agent UTF-8 SSE 漏洞：
        // "你好" 的 UTF-8 字节是 e4 bd a0 e5 a5 bd（共 6 字节）。
        // 模拟 reqwest::chunk() 把这段切在 e4 bd 后（即第一个汉字的 1/3 处），
        // 旧代码立刻 from_utf8(&chunk) 报错让整条流挂掉；新代码累积字节直到拿到
        // 完整 event (\n\n) 才解码，应当无损。
        let event_bytes = b"data: {\"text\":\"\xe4\xbd\xa0\xe5\xa5\xbd\"}\n\n";
        let cut = 17; // 切在 e4 bd 之后、a0 之前——多字节字符内部
        assert!(cut < event_bytes.len() && event_bytes[cut] == 0xa0);

        let mut buf = Vec::new();
        buf.extend_from_slice(&event_bytes[..cut]);
        let events_round_1 = drain_complete_sse_events(&mut buf);
        assert!(
            events_round_1.is_empty(),
            "尚未收到 \\n\\n，不能产生 event；同时 buffer 不应因半截多字节字符报错"
        );

        buf.extend_from_slice(&event_bytes[cut..]);
        let events_round_2 = drain_complete_sse_events(&mut buf);
        assert_eq!(events_round_2.len(), 1, "拼齐后应产生 1 个完整 event");
        assert!(
            events_round_2[0].contains("你好"),
            "中文必须在拼齐后完好解出；旧实现这里会丢字"
        );
        assert!(buf.is_empty(), "处理完后 buffer 应清空");
    }

    #[test]
    fn drain_complete_sse_events_handles_crlf_delimiter() {
        // 回归 PR #398 pr_agent advisory：部分服务器/CDN 用 \r\n\r\n 分隔 SSE 帧，
        // 旧实现只认 \n\n 会把整条流当空流。新实现按字节同时查 \r\n\r\n 与 \n\n，
        // 取最早位置。Rust str::lines() 在 event 内自动剥 \r，所以 line 处理无需改。
        let mut buf = b"data: {\"a\":1}\r\n\r\ndata: {\"b\":2}\r\n\r\n".to_vec();
        let events = drain_complete_sse_events(&mut buf);
        assert_eq!(events, vec!["data: {\"a\":1}", "data: {\"b\":2}"]);
        assert!(buf.is_empty());
    }

    #[test]
    fn drain_complete_sse_events_picks_earliest_delimiter_when_mixed() {
        // 同一 buffer 里既有 LF 风格也有 CRLF 风格——按出现顺序处理，不漏 event。
        let mut buf = b"data: lf-event\n\ndata: crlf-event\r\n\r\nrest".to_vec();
        let events = drain_complete_sse_events(&mut buf);
        assert_eq!(events, vec!["data: lf-event", "data: crlf-event"]);
        assert_eq!(buf, b"rest");
    }

    #[test]
    fn drain_complete_sse_events_skips_invalid_utf8_event_without_failing_stream() {
        // 极端情况：完整 event 自身字节序列就 UTF-8 不合法（上游脏数据）。
        // 旧实现会 ? 直接 fail 让流挂掉；新实现降级为 warn + skip。
        let mut buf: Vec<u8> = b"data: ok\n\n".to_vec();
        buf.extend_from_slice(&[0xff, 0xfe, b'\n', b'\n']); // 不合法 event
        buf.extend_from_slice(b"data: ok2\n\n");
        let events = drain_complete_sse_events(&mut buf);
        assert_eq!(events, vec!["data: ok", "data: ok2"]);
        assert!(buf.is_empty());
    }
}
