import streamlit as st
import os
from datetime import datetime
import json
from dotenv import load_dotenv
import requests
import re
import base64

load_dotenv()

st.set_page_config(page_title="Nebius-chat", page_icon="🧠", layout="wide")


class NebiusStudioChat:
    def __init__(self):
        self.api_key = os.getenv("NEBIUS_API_KEY")
        self.base_url = "https://api.studio.nebius.com/v1"
        self.models = {
            "DeepSeek-R1-0528": "deepseek-ai/DeepSeek-R1-0528",
            "Qwen3-235B-A22B": "Qwen/Qwen3-235B-A22B",
        }
        self.conversation_history = []
        self.custom_instruction = "You are a helpful AI assistant."

    def send_message(
        self,
        message,
        model="deepseek-ai/DeepSeek-R1-0528",
        temperature=0.6,
        max_tokens=8192,
        top_p=0.95,
        presence_penalty=0.63,
        top_k=51,
    ):
        if not self.api_key:
            return None, "API key not configured", {}

        try:
            url = f"{self.base_url}/chat/completions"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            messages = []
            if self.custom_instruction:
                messages.append({"role": "system", "content": self.custom_instruction})
            for entry in self.conversation_history[-5:]:
                messages.append({"role": "user", "content": entry["user"]})
                messages.append({"role": "assistant", "content": entry["assistant"]})
            messages.append({"role": "user", "content": message})

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "presence_penalty": presence_penalty,
                "extra_body": {"top_k": top_k},
            }

            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                result = response.json()
                assistant_response = result["choices"][0]["message"]["content"].strip()
                usage = result.get("usage", {})
                conversation_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user": message,
                    "assistant": assistant_response,
                    "model": model,
                    "temperature": temperature,
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                }
                self.conversation_history.append(conversation_entry)
                return assistant_response, None, conversation_entry["usage"]
            else:
                return None, f"API Error: {response.status_code} - {response.text}", {}

        except Exception as e:
            return None, f"Error: {str(e)}", {}

    def summarize_text(self, text):
        return None, "Summarization is not implemented for Nebius API."

    def paraphrase_text(self, text, style="general"):
        return None, "Paraphrasing is not implemented for Nebius API."

    def set_custom_instruction(self, instruction):
        self.custom_instruction = instruction

    def clear_conversation(self):
        self.conversation_history = []

    def get_usage_stats(self):
        if not self.conversation_history:
            return {}
        total_tokens = sum(
            entry.get("usage", {}).get("total_tokens", 0)
            for entry in self.conversation_history
        )
        total_prompt_tokens = sum(
            entry.get("usage", {}).get("prompt_tokens", 0)
            for entry in self.conversation_history
        )
        total_completion_tokens = sum(
            entry.get("usage", {}).get("completion_tokens", 0)
            for entry in self.conversation_history
        )
        return {
            "total_conversations": len(self.conversation_history),
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "avg_tokens_per_conversation": (
                total_tokens / len(self.conversation_history)
                if self.conversation_history
                else 0
            ),
        }

    def export_conversation(self):
        if not self.conversation_history:
            return None, None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nebius_conversation_{timestamp}.json"
        export_data = {
            "generated_at": datetime.now().isoformat(),
            "custom_instruction": self.custom_instruction,
            "usage_stats": self.get_usage_stats(),
            "conversation": self.conversation_history,
        }
        return filename, json.dumps(export_data, indent=2)

    def generate_image(
        self,
        prompt,
        model="black-forest-labs/flux-schnell",
        response_format="b64_json",
        response_extension="png",
        width=1024,
        height=1024,
        num_inference_steps=4,
        negative_prompt="",
        seed=-1,
        loras=None,
    ):
        if not self.api_key:
            return None, "API key not configured"
        try:
            url = f"{self.base_url}/images/generations"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "*/*",
            }
            payload = {
                "model": model,
                "prompt": prompt,
                "response_format": response_format,
                "response_extension": response_extension,
                "width": width,
                "height": height,
                "num_inference_steps": num_inference_steps,
                "negative_prompt": negative_prompt,
                "seed": seed,
                "loras": loras,
            }
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                # Expecting result['data'][0]['b64_json']
                image_b64 = result["data"][0]["b64_json"]
                return image_b64, None
            else:
                return None, f"API Error: {response.status_code} - {response.text}"
        except Exception as e:
            return None, f"Error: {str(e)}"


user_input = st.chat_input("Ask your Questions.")


def format_reasoning_response(thinking_content):
    """Format assistant content by removing think tags."""
    return (
        thinking_content.replace("<think>\n\n</think>", "")
        .replace("<think>", "")
        .replace("</think>", "")
    )


def display_assistant_message(content):
    """Display assistant message with thinking content if present, and always render the full response."""
    pattern = r"<think>(.*?)</think>"
    think_match = re.search(pattern, content, re.DOTALL)
    if think_match:
        think_content = think_match.group(0)
        response_content = content.replace(think_content, "")
        think_content = format_reasoning_response(think_content)
        with st.expander("Thinking complete!"):
            st.markdown(think_content)
        st.markdown(response_content)
    else:
        st.markdown(content, unsafe_allow_html=False)


def main():
    # base64 is already imported at the top, do not redefine it here
    with open("./assets/nebius.png", "rb") as nebius_file:
        nebius_base64 = base64.b64encode(nebius_file.read()).decode()
        # Create title with embedded images
        title_html = f"""
        <div style="display: flex; width: 100%; padding: 32px 0 24px 0;">
            <h1 style="margin: 0; padding: 0; font-size: 2.5rem; font-weight: bold;">
                <img src=\"data:image/png;base64,{nebius_base64}\" style=\"height: 28px;padding-bottom: 1px; margin-right: 1px;\"/> AI Studio Chat
            </h1>
        </div>
        """
        st.markdown(title_html, unsafe_allow_html=True)

    if "nebius_chat" not in st.session_state:
        st.session_state.nebius_chat = NebiusStudioChat()

    chat = st.session_state.nebius_chat

    with st.sidebar:
        st.header("⚙️ Configuration")

        tool_mode = st.selectbox(
            "Choose Tool",
            ["Chat", "Image Generation"],
            help="Select Nebius Studio tool to use",
        )
        st.divider()

        if tool_mode == "Chat":
            api_key = st.text_input(
                "Nebius API Key", value=chat.api_key or "", type="password"
            )
            chat.api_key = api_key
            st.markdown("### 🤖 Model Settings")
            selected_model = st.selectbox(
                "Choose Nebius Model",
                list(chat.models.keys()),
                help="Different models offer different capabilities",
            )
            model_id = chat.models[selected_model]
            model_info = {
                "DeepSeek-R1-0528": "🔬 DeepSeek: General-purpose, strong reasoning",
                "Qwen3-235B-A22B": "🌐 Qwen3: Large multilingual, advanced capabilities",
            }
            st.info(model_info[selected_model])
            st.markdown("### 🎛️ Generation Parameters")
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.1,
                help="Controls response creativity",
            )
            top_p = st.slider(
                "Top-p",
                min_value=0.1,
                max_value=1.0,
                value=1.0,
                step=0.1,
                help="Controls diversity of token selection",
            )
            max_tokens = st.slider(
                "Max Tokens",
                min_value=50,
                max_value=500,
                value=200,
                step=50,
                help="Maximum response length",
            )
            st.divider()
            st.markdown("### 📝 Custom Instructions")
            custom_instruction = user_input or chat.custom_instruction

            preset_instructions = {
                "Default": "You are a helpful AI assistant.",
                "Creative Writer": "You are a creative writing assistant. Help with storytelling, character development, and narrative techniques.",
                "Business Assistant": "You are a professional business assistant. Provide clear, concise, and actionable advice.",
                "Language Tutor": "You are a language learning tutor. Help with grammar, vocabulary, and conversation practice.",
                "Technical Expert": "You are a technical expert. Provide detailed, accurate technical information and solutions.",
            }
            selected_preset = st.selectbox(
                "Quick Presets", list(preset_instructions.keys())
            )
            if st.button("Apply Preset"):
                chat.set_custom_instruction(preset_instructions[selected_preset])
                st.success(f"✅ Applied {selected_preset} preset!")
                st.rerun()
            st.divider()
            st.markdown("### 📊 Usage Stats")
            if chat.conversation_history:

                stats = chat.get_usage_stats()
                st.metric("Conversations", stats["total_conversations"])
                st.metric("Total Tokens", stats["total_tokens"])
                st.metric(
                    "Avg Tokens/Conv", f"{stats['avg_tokens_per_conversation']:.1f}"
                )
            st.divider()
            if chat.conversation_history:
                st.markdown("### 📥 Export Chat")
                if st.button("Export Conversation"):
                    filename, content = chat.export_conversation()
                    if content:
                        st.download_button(
                            "📄 Download Chat",
                            content,
                            file_name=filename,
                            mime="application/json",
                        )
            if st.button("🗑️ Clear Chat"):
                chat.clear_conversation()
                st.rerun()
        elif tool_mode == "Image Generation":
            api_key = st.text_input(
                "Nebius API Key", value=chat.api_key or "", type="password"
            )
            chat.api_key = api_key
            st.markdown("### 🖼️ Image Generation Settings")
            image_models = {
                "Flux Schnell": "black-forest-labs/flux-schnell",
                "Flux Dev": "black-forest-labs/flux-dev",
                "SDXL": "stability-ai/sdxl",
            }
            selected_image_model = st.selectbox(
                "Choose Image Model",
                list(image_models.keys()),
                help="Select the image generation model",
            )
            image_model_id = image_models[selected_image_model]
            response_format = st.selectbox(
                "Response Format", ["b64_json", "url"], index=0
            )
            response_extension = st.selectbox(
                "Response Extension", ["png", "jpg", "jpeg", "webp"], index=0
            )
            width = st.number_input(
                "Width", min_value=64, max_value=2048, value=1024, step=64
            )
            height = st.number_input(
                "Height", min_value=64, max_value=2048, value=1024, step=64
            )
            num_inference_steps = st.number_input(
                "Num Inference Steps", min_value=1, max_value=100, value=4, step=1
            )
            negative_prompt = st.text_area("Negative Prompt", value="", height=70)
            seed = st.number_input("Seed", value=-1, step=1)
            loras = st.text_area("Loras (JSON or leave blank)", value="", height=70)

    if not chat.api_key:
        st.warning("⚠️ Please enter your Nebius API key in the sidebar.")
        with st.expander("ℹ️ Setup Instructions"):
            st.markdown(
                """
            1. **Get API Key**: Sign up at [Nebius AI Studio](https://console.nebius.ai/ai/llm)
            2. **Enter Key**: Add your API key in the sidebar
            3. **Choose Model**: Select the appropriate Nebius model
            4. **Customize**: Adjust instructions and parameters
            5. **Start Chatting or Generating Images!**
            """
            )
        return
    if tool_mode == "Chat":
        # st.header("\ud83d\udcac Chat with Nebius")

        # Display chat history using st.chat_message
        for entry in chat.conversation_history:
            with st.chat_message("user"):
                st.markdown(entry["user"])
            with st.chat_message("assistant"):
                display_assistant_message(entry["assistant"])

        # Handle new user input
        if user_input and user_input.strip():
            # Add user message
            with st.chat_message("user"):
                st.markdown(user_input.strip())
            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Nebius is thinking..."):
                    response, error, usage = chat.send_message(
                        user_input.strip(),
                        model_id,
                        temperature,
                        max_tokens,
                        top_p,
                        # presence_penalty and top_k use defaults
                    )
                    if response:
                        display_assistant_message(response)
                        # st.rerun()
                    else:
                        st.error(f"\u274c {error}")

        col1, col2 = st.columns([3, 1])

        # with col2:
        #     if st.button("🔄 New Chat"):
        #         chat.clear_conversation()
        #         st.rerun()

    elif tool_mode == "Image Generation":
        # st.header("🖼️ Image Generation (Nebius)")
        prompt = user_input or ""
        loras_val = None
        if loras.strip():
            try:
                loras_val = json.loads(loras)
            except Exception:
                st.warning("Loras must be valid JSON or left blank.")
                loras_val = None
        if user_input and user_input.strip():
            with st.spinner("Generating image..."):
                image_b64, error = chat.generate_image(
                    prompt=prompt.strip(),
                    model=image_model_id,
                    response_format=response_format,
                    response_extension=response_extension,
                    width=width,
                    height=height,
                    num_inference_steps=num_inference_steps,
                    negative_prompt=negative_prompt,
                    seed=seed,
                    loras=loras_val,
                )
                if image_b64:
                    # st.success("✅ Image generated!")
                    # import base64

                    image_bytes = base64.b64decode(image_b64)
                    st.image(
                        image_bytes,
                        caption="Generated Image",
                        use_container_width=True,
                        width=256,
                    )
                else:
                    st.error(f"❌ {error}")


if __name__ == "__main__":
    main()
