//! Shared parsing/validation for user-configurable shortcut bindings.

use global_hotkey::hotkey::{Code, HotKey, Modifiers};

use crate::types::{HotkeyTrigger, ShortcutBinding};

#[derive(Debug, thiserror::Error)]
pub enum ShortcutBindingError {
    #[error("不支持的修饰键: {0}")]
    UnsupportedModifier(String),
    #[error("不支持的主键: {0}")]
    UnsupportedKey(String),
}

pub fn validate_binding(binding: &ShortcutBinding) -> Result<(), ShortcutBindingError> {
    if legacy_modifier_trigger(binding).is_some() {
        return Ok(());
    }
    if binding.modifiers.is_empty() && binding.primary.eq_ignore_ascii_case("shift") {
        return Ok(());
    }
    parse_global_hotkey(binding)?;
    Ok(())
}

pub fn parse_global_hotkey(binding: &ShortcutBinding) -> Result<HotKey, ShortcutBindingError> {
    let mut mods = Modifiers::empty();
    for raw in &binding.modifiers {
        let tag = normalize_modifier_tag(raw);
        let bit = match tag.as_str() {
            "cmd" | "command" | "super" | "meta" | "win" => Modifiers::SUPER,
            "ctrl" | "control" => Modifiers::CONTROL,
            "alt" | "option" | "opt" => Modifiers::ALT,
            "shift" => Modifiers::SHIFT,
            other => return Err(ShortcutBindingError::UnsupportedModifier(other.to_string())),
        };
        mods |= bit;
    }
    let code = parse_primary(&binding.primary)?;
    let mods = if mods.is_empty() { None } else { Some(mods) };
    Ok(HotKey::new(mods, code))
}

pub fn legacy_modifier_trigger(binding: &ShortcutBinding) -> Option<HotkeyTrigger> {
    if !binding.modifiers.is_empty() {
        return None;
    }
    match normalize_primary(&binding.primary).as_str() {
        "rightoption" => Some(HotkeyTrigger::RightOption),
        "rightalt" => Some(HotkeyTrigger::RightAlt),
        "leftoption" | "leftalt" => Some(HotkeyTrigger::LeftOption),
        "rightcontrol" | "rightctrl" => Some(HotkeyTrigger::RightControl),
        "leftcontrol" | "leftctrl" => Some(HotkeyTrigger::LeftControl),
        "rightcommand" | "rightcmd" | "rightsuper" | "rightmeta" => {
            Some(HotkeyTrigger::RightCommand)
        }
        "fn" | "function" => Some(HotkeyTrigger::Fn),
        _ => None,
    }
}

pub fn binding_from_legacy_trigger(trigger: HotkeyTrigger) -> ShortcutBinding {
    let primary = match trigger {
        HotkeyTrigger::RightOption => "RightOption",
        HotkeyTrigger::RightAlt => "RightAlt",
        HotkeyTrigger::LeftOption => "LeftOption",
        HotkeyTrigger::RightControl => "RightControl",
        HotkeyTrigger::LeftControl => "LeftControl",
        HotkeyTrigger::RightCommand => "RightCommand",
        HotkeyTrigger::Fn => "Fn",
        HotkeyTrigger::Custom => {
            #[cfg(target_os = "windows")]
            {
                "RightAlt"
            }
            #[cfg(not(target_os = "windows"))]
            {
                "RightOption"
            }
        }
    };
    ShortcutBinding {
        primary: primary.into(),
        modifiers: Vec::new(),
    }
}

fn normalize_modifier_tag(raw: &str) -> String {
    let tag = raw.trim().to_ascii_lowercase();
    #[cfg(target_os = "windows")]
    {
        if matches!(tag.as_str(), "cmd" | "command") {
            return "ctrl".to_string();
        }
    }
    tag
}

fn normalize_primary(raw: &str) -> String {
    raw.trim()
        .chars()
        .filter(|c| !matches!(c, ' ' | '-' | '_'))
        .collect::<String>()
        .to_ascii_lowercase()
}

fn parse_primary(raw: &str) -> Result<Code, ShortcutBindingError> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err(ShortcutBindingError::UnsupportedKey("(空)".into()));
    }
    if trimmed.chars().count() == 1 {
        let ch = trimmed.chars().next().unwrap();
        if let Some(code) = char_to_code(ch) {
            return Ok(code);
        }
    }
    let upper = trimmed.to_ascii_uppercase();
    let named = match upper.as_str() {
        "ENTER" | "RETURN" => Code::Enter,
        "TAB" => Code::Tab,
        "ESC" | "ESCAPE" => Code::Escape,
        "SPACE" => Code::Space,
        "BACKSPACE" => Code::Backspace,
        "DELETE" | "DEL" => Code::Delete,
        "HOME" => Code::Home,
        "END" => Code::End,
        "PAGEUP" => Code::PageUp,
        "PAGEDOWN" => Code::PageDown,
        "ARROWUP" | "UP" => Code::ArrowUp,
        "ARROWDOWN" | "DOWN" => Code::ArrowDown,
        "ARROWLEFT" | "LEFT" => Code::ArrowLeft,
        "ARROWRIGHT" | "RIGHT" => Code::ArrowRight,
        "F1" => Code::F1,
        "F2" => Code::F2,
        "F3" => Code::F3,
        "F4" => Code::F4,
        "F5" => Code::F5,
        "F6" => Code::F6,
        "F7" => Code::F7,
        "F8" => Code::F8,
        "F9" => Code::F9,
        "F10" => Code::F10,
        "F11" => Code::F11,
        "F12" => Code::F12,
        _ => return Err(ShortcutBindingError::UnsupportedKey(trimmed.to_string())),
    };
    Ok(named)
}

fn char_to_code(ch: char) -> Option<Code> {
    let c = ch.to_ascii_uppercase();
    let code = match c {
        'A' => Code::KeyA,
        'B' => Code::KeyB,
        'C' => Code::KeyC,
        'D' => Code::KeyD,
        'E' => Code::KeyE,
        'F' => Code::KeyF,
        'G' => Code::KeyG,
        'H' => Code::KeyH,
        'I' => Code::KeyI,
        'J' => Code::KeyJ,
        'K' => Code::KeyK,
        'L' => Code::KeyL,
        'M' => Code::KeyM,
        'N' => Code::KeyN,
        'O' => Code::KeyO,
        'P' => Code::KeyP,
        'Q' => Code::KeyQ,
        'R' => Code::KeyR,
        'S' => Code::KeyS,
        'T' => Code::KeyT,
        'U' => Code::KeyU,
        'V' => Code::KeyV,
        'W' => Code::KeyW,
        'X' => Code::KeyX,
        'Y' => Code::KeyY,
        'Z' => Code::KeyZ,
        '0' | ')' => Code::Digit0,
        '1' | '!' => Code::Digit1,
        '2' | '@' => Code::Digit2,
        '3' | '#' => Code::Digit3,
        '4' | '$' => Code::Digit4,
        '5' | '%' => Code::Digit5,
        '6' | '^' => Code::Digit6,
        '7' | '&' => Code::Digit7,
        '8' | '*' => Code::Digit8,
        '9' | '(' => Code::Digit9,
        ';' | ':' => Code::Semicolon,
        ',' | '<' => Code::Comma,
        '.' | '>' => Code::Period,
        '/' | '?' => Code::Slash,
        '\\' | '|' => Code::Backslash,
        '[' | '{' => Code::BracketLeft,
        ']' | '}' => Code::BracketRight,
        '\'' | '"' => Code::Quote,
        '`' | '~' => Code::Backquote,
        '-' | '_' => Code::Minus,
        '=' | '+' => Code::Equal,
        ' ' => Code::Space,
        _ => return None,
    };
    Some(code)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_combo_and_single_key() {
        let combo = ShortcutBinding {
            primary: "D".into(),
            modifiers: vec!["cmd".into(), "shift".into()],
        };
        let parsed = parse_global_hotkey(&combo).expect("combo parses");
        #[cfg(target_os = "windows")]
        assert!(parsed.mods.contains(Modifiers::CONTROL));
        #[cfg(not(target_os = "windows"))]
        assert!(parsed.mods.contains(Modifiers::SUPER));
        assert!(parsed.mods.contains(Modifiers::SHIFT));
        assert_eq!(parsed.key, Code::KeyD);

        let single = ShortcutBinding {
            primary: "F8".into(),
            modifiers: vec![],
        };
        let parsed = parse_global_hotkey(&single).expect("single key parses");
        assert!(parsed.mods.is_empty());
        assert_eq!(parsed.key, Code::F8);
    }

    #[test]
    fn detects_legacy_modifier_only() {
        let binding = ShortcutBinding {
            primary: "RightControl".into(),
            modifiers: vec![],
        };
        assert_eq!(
            legacy_modifier_trigger(&binding),
            Some(HotkeyTrigger::RightControl)
        );
    }

    #[test]
    fn accepts_shifted_printable_aliases() {
        let cases = [
            ("?", Code::Slash),
            ("!", Code::Digit1),
            (":", Code::Semicolon),
            ("+", Code::Equal),
            ("_", Code::Minus),
            ("{", Code::BracketLeft),
            ("|", Code::Backslash),
        ];
        for (primary, expected) in cases {
            let binding = ShortcutBinding {
                primary: primary.into(),
                modifiers: vec!["shift".into()],
            };
            let parsed = parse_global_hotkey(&binding).expect("shifted printable parses");
            assert_eq!(parsed.key, expected);
            assert!(parsed.mods.contains(Modifiers::SHIFT));
        }
    }
}
