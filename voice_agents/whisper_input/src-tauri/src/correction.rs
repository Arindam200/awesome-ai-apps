//! 用户自定义纠正规则。
//!
//! 规则独立于词汇表：词汇表负责 ASR/LLM 热词提示，纠正规则负责在听写流水线里
//! 做确定性的文本替换。当前只支持一个保守通配符 `{num}`，避免把任意正则暴露给
//! 用户造成误替换。

use crate::types::CorrectionRule;

const NUM_TOKEN: &str = "{num}";

pub fn apply_correction_rules(text: &str, rules: &[CorrectionRule]) -> String {
    let mut current = text.to_string();
    for rule in rules {
        if !rule.enabled {
            continue;
        }
        let pattern = rule.pattern.trim();
        if pattern.is_empty() {
            continue;
        }
        current = apply_rule(&current, pattern, &rule.replacement);
    }
    current
}

fn apply_rule(text: &str, pattern: &str, replacement: &str) -> String {
    let token_count = pattern.matches(NUM_TOKEN).count();
    if token_count == 0 {
        if replacement.contains(NUM_TOKEN) {
            return text.to_string();
        }
        return text.replace(pattern, replacement);
    }
    if token_count != 1 {
        return text.to_string();
    }
    apply_num_rule(text, pattern, replacement)
}

fn apply_num_rule(text: &str, pattern: &str, replacement: &str) -> String {
    let Some((prefix, suffix)) = pattern.split_once(NUM_TOKEN) else {
        return text.to_string();
    };
    if prefix.is_empty() && suffix.is_empty() {
        return text.to_string();
    }

    let mut output = String::with_capacity(text.len());
    let mut cursor = 0usize;
    while cursor < text.len() {
        let Some((match_start, token_start)) = next_prefix_match(text, cursor, prefix) else {
            break;
        };
        let Some(token_end) = consume_number_token(text, token_start) else {
            output.push_str(&text[cursor..next_char_boundary(text, match_start)]);
            cursor = next_char_boundary(text, match_start);
            continue;
        };
        let after_number = &text[token_end..];
        if !after_number.starts_with(suffix) {
            output.push_str(&text[cursor..next_char_boundary(text, match_start)]);
            cursor = next_char_boundary(text, match_start);
            continue;
        }

        let match_end = token_end + suffix.len();
        output.push_str(&text[cursor..match_start]);
        output.push_str(&replacement.replace(NUM_TOKEN, &text[token_start..token_end]));
        cursor = match_end;
    }
    output.push_str(&text[cursor..]);
    output
}

fn next_prefix_match(text: &str, cursor: usize, prefix: &str) -> Option<(usize, usize)> {
    if prefix.is_empty() {
        let match_start = next_number_start(text, cursor)?;
        return Some((match_start, match_start));
    }
    let relative = text[cursor..].find(prefix)?;
    let match_start = cursor + relative;
    Some((match_start, match_start + prefix.len()))
}

fn next_number_start(text: &str, cursor: usize) -> Option<usize> {
    text[cursor..]
        .char_indices()
        .find_map(|(offset, ch)| is_number_char(ch).then_some(cursor + offset))
}

fn consume_number_token(text: &str, start: usize) -> Option<usize> {
    let mut end = start;
    let mut consumed = false;
    for (offset, ch) in text[start..].char_indices() {
        if !is_number_char(ch) {
            break;
        }
        consumed = true;
        end = start + offset + ch.len_utf8();
    }
    consumed.then_some(end)
}

fn is_number_char(ch: char) -> bool {
    ch.is_ascii_digit()
        || matches!(
            ch,
            '零' | '〇'
                | '一'
                | '二'
                | '两'
                | '兩'
                | '三'
                | '四'
                | '五'
                | '六'
                | '七'
                | '八'
                | '九'
                | '十'
                | '百'
                | '千'
                | '万'
                | '萬'
                | '亿'
                | '億'
                | '几'
                | '幾'
        )
}

fn next_char_boundary(text: &str, start: usize) -> usize {
    text[start..]
        .chars()
        .next()
        .map(|ch| start + ch.len_utf8())
        .unwrap_or(text.len())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rule(pattern: &str, replacement: &str) -> CorrectionRule {
        CorrectionRule {
            id: "rule".into(),
            pattern: pattern.into(),
            replacement: replacement.into(),
            enabled: true,
            created_at: String::new(),
        }
    }

    #[test]
    fn applies_literal_replacement() {
        let rules = vec![rule("几粒", "几例")];
        assert_eq!(
            apply_correction_rules("这里有几粒样品", &rules),
            "这里有几例样品"
        );
    }

    #[test]
    fn applies_num_wildcard_for_arabic_digits() {
        let rules = vec![rule("{num}粒", "{num}例")];
        assert_eq!(
            apply_correction_rules("2粒样品和10粒对照", &rules),
            "2例样品和10例对照"
        );
    }

    #[test]
    fn applies_num_wildcard_for_chinese_numbers() {
        let rules = vec![rule("{num}粒", "{num}例")];
        assert_eq!(
            apply_correction_rules("两粒样品和幾粒对照", &rules),
            "两例样品和幾例对照"
        );
    }

    #[test]
    fn disabled_rules_are_ignored() {
        let mut disabled = rule("{num}粒", "{num}例");
        disabled.enabled = false;
        assert_eq!(apply_correction_rules("10粒样品", &[disabled]), "10粒样品");
    }

    #[test]
    fn malformed_rules_are_inert() {
        let rules = vec![
            rule("{num}到{num}粒", "{num}例"),
            rule("几粒", "{num}例"),
            rule("{num}", "{num}例"),
        ];
        assert_eq!(apply_correction_rules("几粒和10粒", &rules), "几粒和10粒");
    }

    #[test]
    fn applies_rules_sequentially() {
        let rules = vec![rule("{num}粒", "{num}例"), rule("样本", "样品")];
        assert_eq!(apply_correction_rules("10粒样本", &rules), "10例样品");
    }
}
