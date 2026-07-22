<div align="center">

**English** | [English](README.en.md)

</div>

<p align="center">
  <img src="./public/AppIcon.png" width="104" height="104" alt="Whisper Input Logo" />
</p>

<h1 align="center">Whisper Input / Qingyu — OpenLess-based Windows Voice Typing</h1>

<p align="center">
  An OpenLess-based Windows AI voice input tool for Chinese workplace writing: hold a global hotkey, speak naturally, turn speech to text, remove filler words, polish or structure the result, and insert it at the current cursor position.
</p>

<p align="center">
  Search intent: <strong>OpenLess alternative</strong>, <strong>Typeless alternative</strong>, <strong>typeless-alternative</strong>, <strong>Windows voice typing</strong>, <strong>AI voice dictation</strong>, <strong>Chinese speech-to-text</strong>, <strong>workplace dictation</strong>, <strong>Chinese-to-English voice input</strong>.
</p>

<p align="center">
  中文搜索意图：<strong>OpenLess 改造版</strong>、<strong>Typeless 平替</strong>、<strong>开源 Typeless</strong>、<strong>Windows 语音输入</strong>、<strong>快捷键语音转文字</strong>、<strong>职场语音输入</strong>、<strong>中文转英文语音输入</strong>。
</p>

<p align="center">
  <a href="https://github.com/EthanYoQ/whisper-input/releases"><img src="https://badgen.net/github/tag/EthanYoQ/whisper-input?label=release" alt="Release" /></a>
  <a href="https://github.com/EthanYoQ/whisper-input/blob/main/LICENSE"><img src="https://badgen.net/badge/license/Apache-2.0/blue" alt="Apache License 2.0" /></a>
  <a href="https://github.com/EthanYoQ/whisper-input/stargazers"><img src="https://badgen.net/github/stars/EthanYoQ/whisper-input" alt="GitHub stars" /></a>
</p>

<p align="center">
  <a href="https://github.com/EthanYoQ/whisper-input/releases/latest">Download latest Windows installer</a>
</p>

<p align="center">
  <img src="./docs/images/whisper-input-hero-en.png" alt="Whisper Input Windows AI voice typing interface overview" />
</p>

---

## 🎯 At a Glance

Whisper Input is not a traditional IME, nor a meeting transcription tool.

It does one thing: **press a shortcut key, speak, and it turns your spoken words into natural, well-structured text at your cursor position.** If direct insertion fails, the result is copied to the clipboard as a fallback.

This project is built upon [OpenLess](https://github.com/Open-Less/openless), but it is not an official OpenLess distribution and is not affiliated with Typeless. It explores a Windows-first, cloud-first direction for people searching for an open-source Typeless-style voice typing workflow in Chinese workplace scenarios.

Here are some typical scenarios:

| Scenario | What you say | What Whisper Input produces |
| --- | --- | --- |
| 💬 Everyday chat | "Just handle this requirement like this for now, I will fill in the details tomorrow" | Clear, natural chat text with fewer filler words |
| 🧑‍💼 Reporting to your boss | "Boss, there are three meetings this week, which one works for you?" | A formal request / meeting invitation |
| 🧱 Task breakdown | "First push the code, second update the README, third publish the installer" | `1.`, `1.1`, `2.` structured text |
| 🌐 English output | Dictate email content in Chinese | English email / Issue / work document |
| 🔢 Number formatting | "Three yuan twenty-eight, tomorrow at two in the afternoon" | `3.28 yuan`, `Tomorrow 14:00` |

---

## 🧭 How It Works

```mermaid
flowchart LR
  A["⌨️ Global Shortcut"] --> B["🎙️ Start Recording"]
  B --> C["☁️ Cloud Real-time ASR"]
  C --> D["✨ LLM Refinement / Polish"]
  D --> E["📍 Insert at Cursor"]
  E --> F{"Insertion Successful?"}
  F -->|Yes| G["✅ Done"]
  F -->|No| H["📋 Copy to Clipboard"]
  H --> I["🕘 Save to History"]
```

No need to switch input methods, open a chat window, or copy and paste manually.  
Wherever your cursor is, the transcribed text appears there; if insertion fails, it is automatically copied to the clipboard as a fallback.

## 🖥️ Interface Preview

### Today Overview: The First Screen When You Open the App

![Whisper Input overview showing model status, dictation metrics, usage trends, and recent recognition](./docs/images/whisper-input-overview-en.png)

### Output Styles: Shape the Same Dictation for Different Needs

![Whisper Input shows Original, Light Polish, Clear Structure, and Formal output styles side by side](./docs/images/whisper-input-output-styles.png)

### Model Settings: Choose and Check Speech and Polishing Services

![Whisper Input model settings with quick cloud ASR and LLM configuration plus connectivity checks](./docs/images/whisper-input-model-settings.png)

### Privacy & Data: See Data Flow and Local Controls Clearly

![Whisper Input privacy and data screen showing audio data, recognized text, local history, and configuration clearing controls](./docs/images/whisper-input-privacy-data.png)

---

## ✨ Core Capabilities

| Icon | Capability | Problem It Solves |
| --- | --- | --- |
| 🎙️ | Chinese voice input | Designed for real work scenarios—primarily Chinese with occasional English terms |
| ⚡ | Low-latency pipeline | Recognizes, polishes, and inserts as quickly as possible after recording ends |
| 🧹 | Light polish | Removes "uh", "um", "like", filler words, repetitions, and obvious speech errors |
| 🧱 | Clear structure | Organizes multiple points from spoken text into hierarchical numbering |
| 🧑‍💼 | Formal expression | Converts to emails, requests, feedback, handoff documents, and other formal text |
| 🌐 | Chinese to English | Speak in Chinese, get English work text as output |
| 🔢 | Format normalization | Automatically formats currency, time, numbers, and corrects spacing and punctuation |
| 📚 | User dictionary | Preserves names, company names, product names, and technical terms |
| 🕘 | History | Local review, copy, and delete recent inputs |
| 📋 | Clipboard fallback | Ensures you get the result even if insertion into the input field fails |

---

## 🧩 Four Output Styles

```mermaid
flowchart TB
  A["The same spoken text"] --> B["📝 Original"]
  A --> C["🧹 Light Polish"]
  A --> D["🧱 Clear Structure"]
  A --> E["🧑‍💼 Formal"]
  B --> B1["Keeps original wording, only adds sentence breaks and punctuation"]
  C --> C1["Removes filler words and repetitions, maintains original order"]
  D --> D1["Organizes into 1 / 1.1 / 2 hierarchical structure"]
  E --> E1["Converts to formal email, request, feedback, or work document"]
```

### Original Dictation

```text
Hey boss about that project acceptance I was wrong earlier it is not Tuesday it is Wednesday at two in the afternoon and also please check the contract and payment milestones and the testing part needs some changes too.
```

### 📝 Original

```text
Hey boss, about the project acceptance—I was wrong earlier, it is not Tuesday, it is Wednesday at two in the afternoon. Also, please check the contract and payment milestones, and the testing part needs some changes too.
```

### 🧹 Light Polish

```text
Boss, regarding the project acceptance—I was wrong earlier. It is not Tuesday, but Wednesday at two in the afternoon. Please check the contract and payment milestones. The testing part also needs some changes.
```

### 🧱 Clear Structure

```text
Boss, regarding the project acceptance, the following items need to be adjusted:

1. Time Correction
1.1 The project acceptance is not on Tuesday, but on Wednesday at 2:00 PM.

2. Items Requiring Confirmation
2.1 Please review the contract and payment milestones.
2.2 The testing section needs adjustments.
```

### 🧑‍💼 Formal

```text
Dear Boss,

Regarding the project acceptance, I would like to update you on the following:

1. Time Correction
The project acceptance date was previously stated incorrectly. It has been corrected to Wednesday at 2:00 PM.

2. Items Requiring Confirmation
Please review the contract and payment milestones. Additionally, the testing section requires further adjustments.

Thank you.
```

---

## 🧑‍💼 Formal Expression Example: Meeting Invitation

You can dictate naturally, just as you would speak:

```text
Hello Director Li, there are three meetings this week: tomorrow is the Jiangsu Provincial Annual Conference, Thursday is the Chang'an Studies Forum, and Friday is the Factory Recruitment Fair. The locations are Jinan, Tai'an, and Xinjiang respectively. Which one would be convenient for you to attend? I would like to invite you to one of the meetings. Thank you.
```

The Formal mode would produce output more like this:

```text
Dear Director Li,

I would like to request your attendance at one of this week's meetings as follows.

1. Meeting Schedule
1.1 Jiangsu Provincial Annual Conference: Tomorrow, in Jinan.
1.2 Chang'an Studies Forum: Thursday, in Tai'an.
1.3 Factory Recruitment Fair: Friday, in Xinjiang.

2. Request
We sincerely invite you to attend and provide guidance at one of these meetings. Please let us know which meeting fits your schedule this week.

Thank you.
```

It will not fabricate background information or expand on facts you did not mention. The focus is on organizing what you have already said into a format more suitable for professional communication.

---

## 🌐 Speak Chinese, Output English

```mermaid
flowchart LR
  A["🗣️ Chinese Dictation"] --> B["🧠 Understand Intent"]
  B --> C["🌐 English Expression"]
  C --> D["📍 Insert into Email / Issue / Document"]
```

You say:

```text
Help me write something in English saying we have completed this update. The main fix was for the issue where long voice input text would get truncated, and we also improved the Formal expression mode.
```

Output:

```text
We have completed this update. The main changes include fixing the issue where long voice input could be truncated, and improving the Formal style so that spoken content is converted into a more structured and professional format.
```

No need to think in English while typing, or write Chinese first and then copy it into a translation tool.

---

## 🔐 Data & Privacy

Whisper Input is a cloud-first product, not an offline ASR tool. Before use, complete the cloud speech-recognition and text-polishing service setup shown in the current interface.

```mermaid
flowchart TB
  A["🎙️ Your Recording"] --> B["☁️ Your Configured ASR Service"]
  B --> C["📝 ASR Text"]
  C --> D["☁️ Your Configured LLM Service"]
  D --> E["✨ Polished Text"]
  E --> F["💻 Current App Input Field"]
  E --> G["🕘 Local History"]
  H["📚 User Dictionary"] --> D
  I["Cloud Service Setup"] --> B
  I --> D
```

| Data | Default Location / Destination |
| --- | --- |
| 🎙️ Audio Recording | Sent to your configured cloud ASR service |
| 📝 ASR Text | Sent to your configured LLM service |
| 🕘 History | Saved locally by default |
| 📚 User Dictionary | Saved locally by default |
| Cloud service configuration | Stored in local config, can be cleared |

You can clear history, dictionary, and API configuration from the settings.

---

## ⚙️ Recommended Configuration

| Type | Recommendation | Notes |
| --- | --- | --- |
| 🎙️ Default ASR | Qwen Real-time ASR | Better overall Chinese performance and lower latency after stopping speech |
| 🎙️ Backup ASR | Doubao Streaming Speech Recognition 2.0 | Can serve as a backup pipeline |
| ✨ Default LLM | Qwen / Gemini / Doubao | Choose based on region, cost, and availability |
| ⚡ Low-cost mode | Lightweight LLM | Suitable for high-frequency daily input |

The settings interface provides common models and service paths. Select a provider and complete the required setup shown in the interface.

---

## 💰 Why It's Low Cost

Whisper Input uses the cloud services configured through its settings interface for speech recognition and text polishing.

```mermaid
flowchart LR
  A["Subscription Voice Input"] --> B["Fixed Monthly Fee"]
  C["Whisper Input"] --> D["Pay per actual ASR duration and LLM usage"]
  D --> E["Light usage typically costs about 1-2 RMB per month"]
```

Actual costs depend on your chosen service provider, model, audio duration, and usage volume. For light daily input, the cost is typically far lower than subscription-based tools like Typeless.

---

## 🚀 Installation & Usage

1. Open [Releases](https://github.com/EthanYoQ/whisper-input/releases).
2. Download the latest Windows installer.
3. Install and launch Whisper Input.
4. Go to "Settings - Model Settings".
5. Select the Qwen or Doubao option and complete the corresponding setup shown in the interface.
6. Press the global shortcut key and start speaking.

---

## 🧱 Product Boundaries

Whisper Input intentionally does NOT do the following:

| Does NOT Do | Reason |
| --- | --- |
| ❌ Register as a Windows system IME | Stays lightweight, does not take over the system IME |
| ❌ Meeting transcription tool | Focused on short-to-medium text input, not a meeting documentation platform |
| ❌ Chatbot | Does not generate information the user has not spoken |
| ❌ RAG / Agent | Maintains its position as an input tool |
| ❌ Offline ASR-first | Current focus is cloud-first, prioritizing real-world usability |

---

## 🙏 Acknowledgements: OpenLess

Whisper Input is built upon [OpenLess](https://github.com/Open-Less/openless).

Thanks to the OpenLess authors and contributors for laying the foundation in desktop voice input, global shortcuts, recording state management, text insertion, and Tauri application infrastructure. Building on this foundation, Whisper Input pivots to a Windows cloud-first approach, focusing more on Chinese professional voice input, formal expression, Chinese-to-English translation, and low-cost API usage.

---

## ⭐ Star

If you find this project helpful, please consider giving it a star on GitHub to support continued development.

## License

Apache License 2.0
