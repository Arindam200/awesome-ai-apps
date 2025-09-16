# import streamlit as st
# import os
# from streamlit_mic_recorder import mic_recorder, speech_to_text

# state = st.session_state

# if 'text_received' not in state:
#     state.text_received = []

# c1, c2 = st.columns(2)
# with c1:
#     st.write("Convert speech to text:")
# with c2:
#     text = speech_to_text(language='en', use_container_width=True, just_once=True, key='STT')

# if text:
#     state.text_received.append(text)

# for text in state.text_received:
#     st.text(text)

# st.write("Record your voice, and play the recorded audio:")
# audio = mic_recorder(start_prompt="⏺️", stop_prompt="⏹️", key='recorder')

# if audio:
#     st.audio(audio['bytes'])


# text = speech_to_text(language='en', use_container_width=True, just_once=True, key='STT')
# if text:
#     st.write(text)
    

# import streamlit as st
# import tempfile
# import base64
# from deepgram import DeepgramClient, SpeakOptions

# # Deepgram API Key (replace with env variable for security)
# DEEPGRAM_API_KEY = "37c16f3a101aad2918c257d802f21f1843a9f683"

# st.title("🎤 Deepgram TTS Demo")

# # User text input
# user_text = st.text_area("Enter text to synthesize:", "Hello world! My name is Ankush")

# if st.button("Generate Speech"):
#     try:
#         # Create client
#         deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)

#         # Speak options
#         options = SpeakOptions(
#             model="aura-2-aries-en",   # Choose model
#             encoding="mp3",              # Ensure mp3 encoding
#         )

#         # Temp file for audio
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
#             temp_path = tmp_file.name

#         # Generate speech and save to file
#         response = deepgram.speak.rest.v("1").save(temp_path, {"text": user_text}, options)

#         # Play audio in Streamlit
#         st.success("✅ Speech generated successfully!")
#         st.audio(temp_path, format="audio/mp3")

#         # Optionally: Base64 for embedding elsewhere
#         with open(temp_path, "rb") as audio_file:
#             audio_bytes = audio_file.read()
#             audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
#             # st.text_area("Base64 Audio (for API use):", audio_base64[:200] + "...")

#     except Exception as e:
#         st.error(f"❌ Error: {e}")
