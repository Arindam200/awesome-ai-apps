pub const VK_SHIFT: u32 = 0x10;
pub const VK_CONTROL: u32 = 0x11;
pub const VK_MENU: u32 = 0x12;
pub const VK_ESCAPE: u32 = 0x1B;
pub const VK_LSHIFT: u32 = 0xA0;
pub const VK_RSHIFT: u32 = 0xA1;
pub const VK_LCONTROL: u32 = 0xA2;
pub const VK_RCONTROL: u32 = 0xA3;
pub const VK_LMENU: u32 = 0xA4;
pub const VK_RMENU: u32 = 0xA5;
pub const VK_LWIN: u32 = 0x5B;
pub const VK_RWIN: u32 = 0x5C;
pub const LLKHF_EXTENDED: u32 = 0x0000_0001;
pub const LLKHF_INJECTED: u32 = 0x0000_0010;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WindowsHotkeyTrigger {
    RightControl,
    LeftControl,
    RightAlt,
    RightCommand,
    LeftAlt,
}

pub fn normalize_modifier_vk_code(vk_code: u32, flags: u32) -> u32 {
    let extended = flags & LLKHF_EXTENDED != 0;
    match vk_code {
        VK_CONTROL => {
            if extended {
                VK_RCONTROL
            } else {
                VK_LCONTROL
            }
        }
        VK_MENU => {
            if extended {
                VK_RMENU
            } else {
                VK_LMENU
            }
        }
        _ => vk_code,
    }
}

pub fn should_process_keyboard_event(
    vk_code: u32,
    flags: u32,
    accept_injected_events: bool,
) -> bool {
    if flags & LLKHF_INJECTED == 0 || accept_injected_events {
        return true;
    }
    matches!(vk_code, VK_MENU | VK_LMENU | VK_RMENU)
}

pub fn trigger_to_vk_code(trigger: WindowsHotkeyTrigger) -> u32 {
    match trigger {
        WindowsHotkeyTrigger::RightControl => VK_RCONTROL,
        WindowsHotkeyTrigger::LeftControl => VK_LCONTROL,
        WindowsHotkeyTrigger::RightAlt => VK_RMENU,
        WindowsHotkeyTrigger::RightCommand => VK_RWIN,
        WindowsHotkeyTrigger::LeftAlt => VK_LMENU,
    }
}

pub fn shortcut_recorder_code_from_vk(vk_code: u32) -> Option<&'static str> {
    match vk_code {
        VK_RMENU => Some("AltRight"),
        VK_LMENU => Some("AltLeft"),
        VK_RCONTROL => Some("ControlRight"),
        VK_LCONTROL => Some("ControlLeft"),
        VK_RSHIFT => Some("ShiftRight"),
        VK_LSHIFT => Some("ShiftLeft"),
        VK_RWIN => Some("MetaRight"),
        VK_LWIN => Some("MetaLeft"),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generic_alt_uses_extended_flag_to_identify_right_alt() {
        assert_eq!(normalize_modifier_vk_code(VK_MENU, 0), VK_LMENU);
        assert_eq!(
            normalize_modifier_vk_code(VK_MENU, LLKHF_EXTENDED),
            VK_RMENU
        );
    }

    #[test]
    fn right_alt_trigger_maps_to_physical_right_menu_key() {
        assert_eq!(trigger_to_vk_code(WindowsHotkeyTrigger::RightAlt), VK_RMENU);
    }

    #[test]
    fn shortcut_recorder_reports_right_alt_as_alt_right() {
        assert_eq!(shortcut_recorder_code_from_vk(VK_RMENU), Some("AltRight"));
    }

    #[test]
    fn injected_alt_events_are_accepted_for_windows_right_alt() {
        assert!(should_process_keyboard_event(
            VK_MENU,
            LLKHF_INJECTED | LLKHF_EXTENDED,
            false
        ));
        assert!(should_process_keyboard_event(
            VK_RMENU,
            LLKHF_INJECTED,
            false
        ));
        assert!(!should_process_keyboard_event(0x41, LLKHF_INJECTED, false));
    }
}
