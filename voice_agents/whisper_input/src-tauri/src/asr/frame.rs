//! 火山引擎大模型流式 ASR 二进制帧编解码。
//!
//! 帧结构通常为：4 字节 header + 可选 sequence + 4 字节大端 payload size + payload。
//! 为了避免运行时依赖 gzip 实现，这里显式使用 no compression；官方协议允许客户端选择
//! no compression，服务端会沿用客户端声明的压缩方式。

const HEADER_BYTE_0: u8 = 0x11; // header_size = 1 * 4 = 4 bytes, version = 1
const COMPRESSION_NONE: u8 = 0b0000;

#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MessageType {
    FullClientRequest = 0b0001,
    AudioOnlyRequest = 0b0010,
    FullServerResponse = 0b1001,
    ErrorMessage = 0b1111,
}

impl MessageType {
    fn from_raw(raw: u8) -> Option<Self> {
        match raw {
            0b0001 => Some(Self::FullClientRequest),
            0b0010 => Some(Self::AudioOnlyRequest),
            0b1001 => Some(Self::FullServerResponse),
            0b1111 => Some(Self::ErrorMessage),
            _ => None,
        }
    }
}

#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Flags {
    None = 0b0000,
    PositiveSequence = 0b0001,
    LastPacket = 0b0010,
    NegativeSequence = 0b0011,
}

#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Serialization {
    None = 0b0000,
    Json = 0b0001,
}

/// Build a single binary frame.
///
/// `sequence` is only emitted into the wire when `flags` is
/// `PositiveSequence` or `NegativeSequence` — matches the Swift behavior.
pub fn build(
    message_type: MessageType,
    flags: Flags,
    serialization: Serialization,
    payload: &[u8],
    sequence: Option<i32>,
) -> Vec<u8> {
    let mut frame = Vec::with_capacity(4 + 4 + 4 + payload.len());
    frame.push(HEADER_BYTE_0);
    frame.push(((message_type as u8) << 4) | (flags as u8));
    frame.push(((serialization as u8) << 4) | COMPRESSION_NONE);
    frame.push(0x00);

    let needs_seq = matches!(flags, Flags::PositiveSequence | Flags::NegativeSequence);
    if needs_seq {
        if let Some(seq) = sequence {
            // i32 → big-endian bytes (preserves sign as two's-complement bit pattern).
            frame.extend_from_slice(&seq.to_be_bytes());
        }
    }

    let size: u32 = payload.len() as u32;
    frame.extend_from_slice(&size.to_be_bytes());
    frame.extend_from_slice(payload);
    frame
}

#[derive(Debug, Clone)]
pub struct ParsedFrame {
    pub message_type: Option<MessageType>,
    pub flags: u8,
    pub sequence: Option<i32>,
    pub error_code: Option<u32>,
    pub payload: Vec<u8>,
}

impl ParsedFrame {
    pub fn is_final(&self) -> bool {
        self.flags == Flags::LastPacket as u8
            || self.flags == Flags::NegativeSequence as u8
            || self.sequence.unwrap_or(0) < 0
    }
}

/// Parse a binary frame received from the server.
///
/// Returns `None` if the buffer is truncated, mis-framed, or uses an
/// unsupported compression mode.
pub fn parse(data: &[u8]) -> Option<ParsedFrame> {
    if data.len() < 8 {
        return None;
    }

    let header_size = (data[0] & 0x0F) as usize * 4;
    if header_size < 4 || data.len() < header_size + 4 {
        return None;
    }

    let message_type_raw = (data[1] >> 4) & 0x0F;
    let message_type = MessageType::from_raw(message_type_raw);
    let flags_raw = data[1] & 0x0F;
    let compression = data[2] & 0x0F;
    if compression != COMPRESSION_NONE {
        return None;
    }

    let mut offset = header_size;
    let mut sequence: Option<i32> = None;

    if has_sequence(flags_raw) {
        let value = read_i32(data, offset)?;
        sequence = Some(value);
        offset += 4;
    }

    if message_type == Some(MessageType::ErrorMessage) {
        let code = read_u32(data, offset)?;
        let message_size = read_u32(data, offset + 4)? as usize;
        offset += 8;
        if data.len() < offset + message_size {
            return None;
        }
        let payload = data[offset..offset + message_size].to_vec();
        return Some(ParsedFrame {
            message_type,
            flags: flags_raw,
            sequence,
            error_code: Some(code),
            payload,
        });
    }

    let payload_size = read_u32(data, offset)? as usize;
    offset += 4;
    if data.len() < offset + payload_size {
        return None;
    }
    let payload = data[offset..offset + payload_size].to_vec();
    Some(ParsedFrame {
        message_type,
        flags: flags_raw,
        sequence,
        error_code: None,
        payload,
    })
}

fn has_sequence(flags: u8) -> bool {
    flags == Flags::PositiveSequence as u8 || flags == Flags::NegativeSequence as u8
}

fn read_u32(data: &[u8], offset: usize) -> Option<u32> {
    if data.len() < offset + 4 {
        return None;
    }
    let bytes: [u8; 4] = data[offset..offset + 4].try_into().ok()?;
    Some(u32::from_be_bytes(bytes))
}

fn read_i32(data: &[u8], offset: usize) -> Option<i32> {
    let unsigned = read_u32(data, offset)?;
    Some(unsigned as i32)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_full_client_request_with_positive_sequence() {
        let payload = b"hi";
        let frame = build(
            MessageType::FullClientRequest,
            Flags::PositiveSequence,
            Serialization::Json,
            payload,
            Some(1),
        );
        let parsed = parse(&frame).expect("frame should parse");
        assert_eq!(parsed.message_type, Some(MessageType::FullClientRequest));
        assert_eq!(parsed.flags, Flags::PositiveSequence as u8);
        assert_eq!(parsed.sequence, Some(1));
        assert_eq!(parsed.error_code, None);
        assert_eq!(parsed.payload, payload);
        assert!(!parsed.is_final());
    }

    #[test]
    fn round_trip_audio_only_with_last_packet_is_final() {
        let frame = build(
            MessageType::AudioOnlyRequest,
            Flags::LastPacket,
            Serialization::None,
            &[],
            None,
        );
        let parsed = parse(&frame).expect("frame should parse");
        assert_eq!(parsed.message_type, Some(MessageType::AudioOnlyRequest));
        assert_eq!(parsed.flags, Flags::LastPacket as u8);
        assert_eq!(parsed.sequence, None);
        assert!(parsed.payload.is_empty());
        assert!(parsed.is_final());
    }

    #[test]
    fn parse_returns_none_on_truncated_buffer() {
        assert!(parse(&[0u8; 4]).is_none());
    }

    #[test]
    fn round_trip_negative_sequence_is_final() {
        let frame = build(
            MessageType::AudioOnlyRequest,
            Flags::NegativeSequence,
            Serialization::None,
            &[],
            Some(-5),
        );
        let parsed = parse(&frame).expect("frame should parse");
        assert_eq!(parsed.sequence, Some(-5));
        assert!(parsed.is_final());
    }

    #[test]
    fn round_trip_error_message() {
        // Manually craft an ErrorMessage frame: header + code(BE u32) + size(BE u32) + body.
        let body = b"boom";
        let mut frame = Vec::new();
        frame.push(HEADER_BYTE_0);
        frame.push(((MessageType::ErrorMessage as u8) << 4) | (Flags::None as u8));
        frame.push(((Serialization::None as u8) << 4) | COMPRESSION_NONE);
        frame.push(0x00);
        frame.extend_from_slice(&123u32.to_be_bytes());
        frame.extend_from_slice(&(body.len() as u32).to_be_bytes());
        frame.extend_from_slice(body);

        let parsed = parse(&frame).expect("error frame should parse");
        assert_eq!(parsed.message_type, Some(MessageType::ErrorMessage));
        assert_eq!(parsed.error_code, Some(123));
        assert_eq!(parsed.payload, body);
    }
}
