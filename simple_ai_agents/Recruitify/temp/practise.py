
# """import os

# from deepgram import (
#     DeepgramClient,
#     PrerecordedOptions,
#     FileSource,
# )
# import tempfile
# import streamlit as st
# from streamlit_mic_recorder import mic_recorder

# audio = mic_recorder(
#     start_prompt="⏺️",
#     stop_prompt="⏹️",
#     key='recorder'
# )

# if audio:
#     st.audio(audio['bytes'])  # playback

#     # Step 1: Save as a temporary MP3 file
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile:
#         tmpfile.write(audio['bytes'])
#         tmpfile_path = tmpfile.name


#     # Path to the audio file
#     AUDIO_FILE = tmpfile_path

#             # STEP 1 Create a Deepgram client using the API key
#     # deepgram = DeepgramClient(a)
#     deepgram = DeepgramClient(api_key="37c16f3a101aad2918c257d802f21f1843a9f683")


#     with open(AUDIO_FILE, "rb") as file:
#         buffer_data = file.read()

#     payload: FileSource = {
#         "buffer": buffer_data,
#     }

#     #STEP 2: Configure Deepgram options for audio analysis
#     options = PrerecordedOptions(
#         model="nova-3",
#         smart_format=True,
#     )

#     # STEP 3: Call the transcribe_file method with the text payload and options
#     response = deepgram.listen.rest.v("1").transcribe_file(payload, options)


#     text=response.to_dict().get("results").get("channels")[0].get("alternatives")[0].get("paragraphs").get('transcript')
#     print(tp)
#     st.write(tp)
# """




# import re
# import streamlit as st
# from groq import Groq
# import os
# import tempfile
# import pandas as pd
# from streamlit_mic_recorder import speech_to_text
# from langchain_groq import ChatGroq
# from dotenv import load_dotenv
# import base64

# load_dotenv()

# # ---- Groq Config ----
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# if not GROQ_API_KEY:
#     st.error("GROQ_API_KEY environment variable not set. Please configure it.")
#     st.stop()
# client = Groq(api_key=GROQ_API_KEY)

# # ---- State Init ----
# if "current_q" not in st.session_state:
#     st.session_state.current_q = 0
# if "questions" not in st.session_state:
#     st.session_state.questions = []
# if "responses" not in st.session_state:
#     st.session_state.responses = []
# if "feedback" not in st.session_state:
#     st.session_state.feedback = []
# if "audio_volume" not in st.session_state:
#     st.session_state.audio_volume = 1.0  # Default volume

# # ---- LLM ----
# llm = ChatGroq(model='llama-3.3-70b-versatile', temperature=0.7, api_key=GROQ_API_KEY)

# # ---- File Upload ----
# file_uploaded = st.file_uploader("Upload the interview questions (.md file)", type=["md", "txt"])
# if file_uploaded and not st.session_state.questions:
#     try:
#         content = file_uploaded.read().decode("utf-8")
#     except UnicodeDecodeError:
#         st.error("Failed to decode file. Ensure it’s a valid .md or .txt file with UTF-8 encoding.")
#         st.stop()

#     try:
#         questions = []
#         question_sections = re.split(r"## \d+[.\-]\s*", content)[1:]
#         for section in question_sections:
#             lines = section.strip().split("\n")
#             if len(lines) < 2:
#                 st.error("Invalid question format in file.")
#                 st.stop()
#             question_type = lines[0].split(" Question")[0].strip()
#             question_text = " ".join(lines[1:]).strip()
#             if question_type and question_text:
#                 questions.append({"type": question_type, "question": question_text})
#     except Exception as e:
#         st.error(f"Error parsing file: {str(e)}")
#         st.stop()

#     if not questions:
#         st.error("No valid questions found in the file.")
#         st.stop()

#     st.session_state.current_q = 0
#     st.session_state.questions = questions
#     st.session_state.responses = ["" for _ in questions]
#     st.session_state.feedback = ["" for _ in questions]
#     st.success(f"Loaded {len(questions)} questions.")

# # ---- Interview Flow ----
# if st.session_state.questions:
#     # State validation
#     if st.session_state.current_q < 0 or st.session_state.current_q >= len(st.session_state.questions):
#         st.error(f"Invalid question index: {st.session_state.current_q}. Resetting to 0.")
#         st.session_state.current_q = 0
#         st.rerun()

#     q = st.session_state.questions[st.session_state.current_q]
#     st.write(f"Progress: Question {st.session_state.current_q+1} of {len(st.session_state.questions)}")
#     st.subheader(f"Question {st.session_state.current_q+1}")
#     st.write(f"**Type:** {q['type']}")
#     st.markdown(q['question'])
#     st.write(f"Debug: Current question index: {st.session_state.current_q}")

#     voice = "Deedee-PlayAI"
#     model = "playai-tts"
#     response_format = "mp3"

#     # Volume control
#     st.session_state.audio_volume = st.slider("Audio volume", 0.0, 1.0, st.session_state.audio_volume, 0.1)

#     if st.button("🔊 Play Question"):
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
#             temp_path = tmp_file.name
#         try:
#             with st.spinner("Generating speech..."):
#                 response = client.audio.speech.create(
#                     model=model,
#                     voice=voice,
#                     input=f"This is a {q['type']} question: {q['question']}",
#                     response_format=response_format
#                 )
#                 response.write_to_file(temp_path)
            
#             with open(temp_path, "rb") as audio_file:
#                 audio_bytes = audio_file.read()
#                 audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            
#             audio_html = f"""
#             <audio id="question-audio" autoplay style="display:none;">
#                 <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
#             </audio>
#             <script>
#                 var audio = document.getElementById("question-audio");
#                 if (audio) {{
#                     audio.volume = {st.session_state.audio_volume};
#                 }}
#             </script>
#             """
#             st.markdown(audio_html, unsafe_allow_html=True)
#         except Exception as e:
#             st.error(f"Failed to generate or play audio: {str(e)}")
#         finally:
#             if os.path.exists(temp_path):
#                 os.remove(temp_path)

#     # Record Answer
#     text = speech_to_text(language='en', use_container_width=True, just_once=True, key=f'STT_{st.session_state.current_q}')
#     if not text:
#         text = st.text_area("Type your response (if speech fails):", key=f'text_input_{st.session_state.current_q}')
#     if text:
#         st.write(f"🗣 **Your Response:** {text}")
#         st.session_state.responses[st.session_state.current_q] = text

#         # AI Feedback
#         prompt = f"""
#         You are an experienced technical interviewer assessing a candidate's answer.

#         **Question Type:** {q['type']}
#         **Question:** {q['question']}
#         **Candidate Response:** {text}

#         Your task:
#         1. Evaluate the overall quality of the response.
#         2. Highlight strengths and positive aspects.
#         3. Identify specific weaknesses or missing points.
#         4. Suggest clear, actionable improvements.
#         5. Provide a **Confidence Score** (1-10) for your evaluation.
#         6. Provide an **Accuracy Score** (1-10) for how factually correct the answer is.

#         Format your response exactly as follows:

#         Evaluation:
#         [Your evaluation text here]

#         Strengths:
#         - [Strength 1]
#         - [Strength 2]

#         Weaknesses:
#         - [Weakness 1]
#         - [Weakness 2]

#         Suggestions for Improvement:
#         - [Suggestion 1]
#         - [Suggestion 2]

#         Confidence Score: X/10
#         Accuracy Score: X/10
#         """
#         try:
#             ai_response = llm.invoke(prompt).content
#             st.session_state.feedback[st.session_state.current_q] = ai_response
#             st.markdown(f"🤖 **AI Feedback:** {ai_response}")
#         except Exception as e:
#             st.error(f"Failed to get AI feedback: {str(e)}")

#     # Navigation
#     col1, col2 = st.columns(2)
#     with col1:
#         prev_disabled = st.session_state.current_q == 0
#         if st.button("⬅️ Previous Question", key="prev_btn", disabled=prev_disabled):
#             st.write(f"Debug: Moving to previous question. Current index: {st.session_state.current_q}")
#             st.session_state.current_q -= 1
#             st.write(f"Debug: New index: {st.session_state.current_q}")
#             st.rerun()
#     with col2:
#         next_disabled = st.session_state.current_q >= len(st.session_state.questions) - 1
#         if st.button("➡️ Next Question", key="next_btn", disabled=next_disabled):
#             st.write(f"Debug: Moving to next question. Current index: {st.session_state.current_q}")
#             st.session_state.current_q += 1
#             st.write(f"Debug: New index: {st.session_state.current_q}")
#             st.rerun()

#     all_responded = all(response.strip() for response in st.session_state.responses)
#     if st.button("✅ Finish Interview", disabled=not all_responded):
#         st.success("Interview completed!")
#         if not all_responded:
#             st.warning("Some questions have no responses. The report may be incomplete.")

#         # Extract scores for chart
#         scores = []
#         for feedback in st.session_state.feedback:
#             if feedback:
#                 match = re.search(r"Confidence Score: (\d+)/10.*Accuracy Score: (\d+)/10", feedback, re.DOTALL)
#                 if match:
#                     scores.append((int(match.group(1)), int(match.group(2))))
#         import plotly.graph_objects as go

#         if scores:
#             avg_confidence = sum(s[0] for s in scores) / len(scores)
#             avg_accuracy = sum(s[1] for s in scores) / len(scores)

#             st.write(f"Average Confidence Score: {avg_confidence:.1f}/10")
#             st.write(f"Average Accuracy Score: {avg_accuracy:.1f}/10")

#             labels = [f"Q{i+1}" for i in range(len(scores))]
#             confidence_data = [s[0] for s in scores]
#             accuracy_data = [s[1] for s in scores]

#             fig = go.Figure(data=[
#                 go.Bar(name='Confidence', x=labels, y=confidence_data, marker_color='rgba(75, 192, 192, 0.7)'),
#                 go.Bar(name='Accuracy', x=labels, y=accuracy_data, marker_color='rgba(255, 99, 132, 0.7)')
#             ])

#             fig.update_layout(
#                 barmode='group',
#                 yaxis=dict(range=[0, 10], title="Score"),
#                 xaxis=dict(title="Questions"),
#                 title="Interview Performance Scores",
#                 legend=dict(title="Metrics")
#             )

#             st.plotly_chart(fig, use_container_width=True)



#  temp
"""""# import re
# import streamlit as st
# from groq import Groq
# import os
# import tempfile
# import base64
# import plotly.graph_objects as go
# from streamlit_mic_recorder import mic_recorder
# from deepgram import DeepgramClient, PrerecordedOptions, FileSource
# import time
# from datetime import datetime, timedelta
# from dotenv import load_dotenv
# from langchain_groq import ChatGroq

# load_dotenv()

# ---- API Keys ----
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# DATAGRAM_API_KEY = os.getenv("DATAGRAM_API_KEY")

# class Interview:
#     def __init__(self,groq_api_key,datagram_api_key):
#         self.GROQ_API_KEY=groq_api_key
#         self.DATAGRAM_API_KEY=datagram_api_key

#         self.client = Groq(api_key=self.GROQ_API_KEY)
#         self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.7, api_key=self.GROQ_API_KEY)
#         # ---- Session State ----
#         if "current_q" not in st.session_state:
#             st.session_state.current_q = 0
#         if "questions" not in st.session_state:
#             st.session_state.questions = []
#         if "responses" not in st.session_state:
#             st.session_state.responses = []
#         if "feedback" not in st.session_state:
#             st.session_state.feedback = []
#         if "audio_volume" not in st.session_state:
#             st.session_state.audio_volume = 1.0
#         if "recorder_key" not in st.session_state:
#             st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
#         if "answer_times" not in st.session_state:
#             st.session_state.answer_times = []
#         if "start_time" not in st.session_state:
#             st.session_state.start_time = None

#     def sidebar_upload_and_summary(self):
#         """Handles file upload and shows sidebar summary"""
#         with st.sidebar:
#             st.markdown("### 📤 Upload Questions")

#             file_uploaded = st.file_uploader("Upload the interview questions (.md file)", type=["md", "txt"])
#         if file_uploaded and not st.session_state.questions:
#             try:
#                 content = file_uploaded.read().decode("utf-8")
#             except UnicodeDecodeError:
#                 st.error("Failed to decode file. Ensure it’s a valid .md or .txt file with UTF-8 encoding.")
#                 st.stop()

#             questions = []
#             try:
#                 question_sections = re.split(r"## \d+[.\-]\s*", content)[1:]
#                 for section in question_sections:
#                     lines = section.strip().split("\n")
#                     if len(lines) < 2:
#                         st.error("Invalid question format in file.")
#                         st.stop()
#                     question_type = lines[0].split(" Question")[0].strip()
#                     question_text = " ".join(lines[1:]).strip()
#                     if question_type and question_text:
#                         questions.append({"type": question_type, "question": question_text})
#             except Exception as e:
#                 st.error(f"Error parsing file: {str(e)}")
#                 st.stop()

#             if not questions:
#                 st.error("No valid questions found in the file.")
#                 st.stop()

#             st.session_state.current_q = 0
#             st.session_state.questions = questions
#             st.session_state.responses = ["" for _ in questions]
#             st.session_state.feedback = ["" for _ in questions]
#             st.session_state.answer_times = [None for _ in questions]
#             st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
#             st.success(f"Loaded {len(questions)} questions.")

#         # Sidebar UI
#         with st.sidebar:
#             st.session_state.audio_volume = st.slider("🎚️ Audio volume", 0.0, 1.0, st.session_state.audio_volume, 0.1)
#             st.header("Interview Summary")
#             for i, q in enumerate(st.session_state.questions):
#                 with st.expander(f"Question {i+1}"):
#                     st.write(f"**Type:** {q['type']}")
#                     st.markdown(f"**Question:** {q['question']}")
#                     st.write(f"**Response:** {st.session_state.responses[i] if st.session_state.responses[i] else 'Not answered'}")
#                     st.markdown(f"**Feedback:** {st.session_state.feedback[i] if st.session_state.feedback[i] else 'No feedback yet'}")
#                     if st.session_state.answer_times[i] is not None:
#                         st.write(f"**Time Taken:** {timedelta(seconds=int(st.session_state.answer_times[i]))}")

#     def run(self):
#         """Main interview workflow"""
#         st.title("🎙️ AI-Powered Interview Practice")

#         self.sidebar_upload_and_summary()

#         if not st.session_state.questions:
#             return

#         # Validate state
#         if st.session_state.current_q < 0 or st.session_state.current_q >= len(st.session_state.questions):
#             st.error(f"Invalid question index: {st.session_state.current_q}. Resetting to 0.")
#             st.session_state.current_q = 0
#             st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
#             st.session_state.start_time = None
#             st.rerun()

#         q = st.session_state.questions[st.session_state.current_q]
#         st.subheader(f"Question {st.session_state.current_q+1}")
#         st.write(f"**Type:** {q['type']}")
#         st.markdown(q['question'])

#         # Progress Bar
#         with st.sidebar:
#             st.markdown('# Progress')
#             progress = (st.session_state.current_q + 1) / len(st.session_state.questions)
#             st.progress(progress)

#         # Play Question
#         if st.button("🔊 Play Question"):
#             voice = "Deedee-PlayAI"
#             model = "playai-tts"
#             response_format = "mp3"

#             with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
#                 temp_path = tmp_file.name
#             try:
#                 with st.spinner("Generating speech..."):
#                     response = self.client.audio.speech.create(
#                         model=model,
#                         voice=voice,
#                         input=f"This is a {q['type']} question: {q['question']}",
#                         response_format=response_format
#                     )
#                     response.write_to_file(temp_path)

#                 with open(temp_path, "rb") as audio_file:
#                     audio_bytes = audio_file.read()
#                     audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

#                 audio_html = f"""
#                 <audio id="question-audio" autoplay style="display:none;">
#                     <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
#                 </audio>
#                 <script>
#                     var audio = document.getElementById("question-audio");
#                     if (audio) {{
#                         audio.volume = {st.session_state.audio_volume};
#                     }}
#                 </script>
#                 """
#                 st.markdown(audio_html, unsafe_allow_html=True)
#             except Exception as e:
#                 st.error(f"Failed to generate or play audio: {str(e)}")
#             finally:
#                 if os.path.exists(temp_path):
#                     os.remove(temp_path)

#         # Record Answer
#         audio = mic_recorder(start_prompt="Start Interview", stop_prompt="Stop Interview", key=st.session_state.recorder_key)
#         if audio:
#             st.audio(audio['bytes'])
#             if st.session_state.start_time is None:
#                 st.session_state.start_time = time.time()

#             with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile:
#                 tmpfile.write(audio['bytes'])
#                 tmpfile_path = tmpfile.name

#             deepgram = DeepgramClient(api_key=self.DATAGRAM_API_KEY)
#             with open(tmpfile_path, "rb") as file:
#                 buffer_data = file.read()

#             payload: FileSource = {"buffer": buffer_data}
#             options = PrerecordedOptions(model="nova-3", smart_format=True)
#             response = deepgram.listen.rest.v("1").transcribe_file(payload, options)

#             text = response.to_dict()["results"]["channels"][0]["alternatives"][0]["paragraphs"]["transcript"]
#             st.session_state.responses[st.session_state.current_q] = text

#             # Track time taken
#             if st.session_state.start_time is not None:
#                 time_taken = time.time() - st.session_state.start_time
#                 st.session_state.answer_times[st.session_state.current_q] = time_taken
#                 st.session_state.start_time = None

#             st.markdown("**The Response:**")
#             st.write(text)

#             # AI Feedback
#             prompt = f"""
#             You are an experienced technical interviewer assessing a candidate's answer.

#             **Question Type:** {q['type']}
#             **Question:** {q['question']}
#             **Candidate Response:** {text}

#             Your task:
#             1. Evaluate the overall quality of the response.
#             2. Highlight strengths and positive aspects.
#             3. Identify specific weaknesses or missing points.
#             4. Suggest clear, actionable improvements.
#             5. Provide a **Confidence Score** (1-10) for your evaluation.
#             6. Provide an **Accuracy Score** (1-10) for how factually correct the answer is.

#             Format your response exactly as follows:

#             Evaluation:
#             [Your evaluation text here]

#             Strengths:
#             - [Strength 1]
#             - [Strength 2]

#             Weaknesses:
#             - [Weakness 1]
#             - [Weakness 2]

#             Suggestions for Improvement:
#             - [Suggestion 1]
#             - [Suggestion 2]

#             Confidence Score: X/10
#             Accuracy Score: X/10
#             """
#             try:
#                 ai_response = self.llm.invoke(prompt).content
#                 st.session_state.feedback[st.session_state.current_q] = ai_response
#             except Exception as e:
#                 st.error(f"Failed to get AI feedback: {str(e)}")

#         # Feedback
#         if st.session_state.feedback[st.session_state.current_q]:
#             st.markdown(f"🤖 **AI Feedback:** {st.session_state.feedback[st.session_state.current_q]}")

#         # Navigation
#         col1, col2 = st.columns(2)
#         with col1:
#             if st.button("⬅️ Previous Question", disabled=st.session_state.current_q == 0):
#                 st.session_state.current_q -= 1
#                 st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
#                 st.session_state.start_time = None
#                 st.rerun()
#         with col2:
#             if st.button("➡️ Next Question", disabled=st.session_state.current_q >= len(st.session_state.questions) - 1):
#                 st.session_state.current_q += 1
#                 st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
#                 st.session_state.start_time = None
#                 st.rerun()

#         # Finish Interview
#         if st.button("✅ Finish Interview"):
#             self.finish_report()

#     def finish_report(self):
#         """Generates final interview report with charts and download option"""
#         all_responded = all(r.strip() for r in st.session_state.responses)
#         st.success("Interview completed!")
#         if not all_responded:
#             st.warning("Some questions have no responses. The report may be incomplete.")

#         scores = []
#         for feedback in st.session_state.feedback:
#             if feedback:
#                 match = re.search(r"Confidence Score: (\d+)/10.*Accuracy Score: (\d+)/10", feedback, re.DOTALL)
#                 if match:
#                     scores.append((int(match.group(1)), int(match.group(2))))

#         if scores:
#             avg_confidence = sum(s[0] for s in scores) / len(scores)
#             avg_accuracy = sum(s[1] for s in scores) / len(scores)

#             st.write(f"Average Confidence Score: {avg_confidence:.1f}/10")
#             st.write(f"Average Accuracy Score: {avg_accuracy:.1f}/10")

#             labels = [f"Q{i+1}" for i in range(len(scores))]
#             confidence_data = [s[0] for s in scores]
#             accuracy_data = [s[1] for s in scores]

#             fig = go.Figure(data=[
#                 go.Bar(name="Confidence", x=labels, y=confidence_data, marker_color="rgba(75, 192, 192, 0.7)"),
#                 go.Bar(name="Accuracy", x=labels, y=accuracy_data, marker_color="rgba(255, 99, 132, 0.7)")
#             ])
#             fig.update_layout(barmode="group", yaxis=dict(range=[0, 10], title="Score"), xaxis=dict(title="Questions"), title="Interview Performance Scores")
#             st.plotly_chart(fig, use_container_width=True)

#         # Markdown Report
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         markdown_report = "# Interview Report\n\n"
#         for i, q in enumerate(st.session_state.questions):
#             markdown_report += f"## Question {i+1}\n"
#             markdown_report += f"**Type:** {q['type']}\n\n"
#             markdown_report += f"**Question:** {q['question']}\n\n"
#             markdown_report += f"**User Response:** {st.session_state.responses[i] if st.session_state.responses[i] else 'Not answered'}\n\n"
#             markdown_report += f"**AI Feedback:**\n{st.session_state.feedback[i] if st.session_state.feedback[i] else 'No feedback'}\n\n"
#             time_taken = st.session_state.answer_times[i]
#             markdown_report += f"**Time Taken:** {timedelta(seconds=int(time_taken)) if time_taken else 'Not recorded'}\n\n"
#             markdown_report += "---\n\n"

#         if scores:
#             markdown_report += f"**Average Confidence Score:** {avg_confidence:.1f}/10\n\n"
#             markdown_report += f"**Average Accuracy Score:** {avg_accuracy:.1f}/10\n\n"

#         st.download_button(
#             label="📥 Download Feedback Report (Markdown)",
#             data=markdown_report.encode("utf-8"),
#             file_name=f"interview_feedback_{timestamp}.md",
#             mime="text/markdown"
#         )

"""