import re
import streamlit as st
from groq import Groq
import os
import tempfile
import base64
import plotly.graph_objects as go
from streamlit_mic_recorder import mic_recorder
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
import time
from datetime import datetime, timedelta
from langchain_groq import ChatGroq


def apply_custom_css(accent_color="#d32f2f"):
    st.markdown(f"""
    <style>
        /* Main container */
        .main {{
            background-color: #000000 !important;
            color: white !important;
        }}

        /* Active tabs and highlights based on accent color */
        .stTabs [aria-selected=\"true\"] {{
            background-color: #000000 !important;
            border-bottom: 3px solid {accent_color} !important;
            color: {accent_color} !important;
        }}

        /* Buttons styled with accent color */
        .stButton button {{
            background-color: {accent_color} !important;
            color: white !important;
        }}

        .stButton button:hover {{
            filter: brightness(85%);
        }}

        /* Warning message */
        div.stAlert {{
            background-color: #4a0000 !important;
            color: white !important;
        }}

        /* Input fields */
        .stTextInput input, .stTextArea textarea, .stSelectbox div {{
            background-color: #222222 !important;
            color: white !important;
        }}

        /* Horizontal rule black and accent color gradient */
        hr {{
            border: none;
            height: 2px;
            background-image: linear-gradient(to right, black 50%, {accent_color} 50%);
        }}

        /* General markdown text */
        .stMarkdown, .stMarkdown p {{
            color: white !important;
        }}

        /* Skill tags styling */
        .skill-tag {{
            display: inline-block;
            background-color: {accent_color};
            color: white;
            padding: 5px 12px;
            border-radius: 15px;
            margin: 5px;
            font-weight: bold;
        }}

        .skill-tag.missing {{
            background-color: #444;
            color: #ccc;
        }}

        /* Horizontal layout for Strengths and Improvements */
        .strengths-improvements {{
            display: flex;
            gap: 20px;
        }}

        .strengths-improvements > div {{
            flex: 1;
        }}
        
        /* Card styling for sections */
        .card {{
            background-color: #111111;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid {accent_color};
        }}
        
        /* Improvement suggestion styling */
        .improvement-item {{
            background-color: #222222;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
        }}
        
        /* Before-after comparison */
        .comparison-container {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }}
        
        .comparison-box {{
            flex: 1;
            background-color: #333333;
            padding: 15px;
            border-radius: 5px;
        }}
        
        /* Weakness detail styling */
        .weakness-detail {{
            background-color: #330000;
            padding: 10px 15px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 3px solid #ff6666;
        }}
        
        /* Solution styling */
        .solution-detail {{
            background-color: #003300;
            padding: 10px 15px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 3px solid #66ff66;
        }}
        
        /* Example detail styling */
        .example-detail {{
            background-color: #000033;
            padding: 10px 15px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 3px solid #6666ff;
        }}
        
        /* Download button styling */
        .download-btn {{
            display: inline-block;
            background-color: {accent_color};
            color: white;
            padding: 8px 16px;
            border-radius: 5px;
            text-decoration: none;
            margin: 10px 0;
            text-align: center;
        }}
        
        .download-btn:hover {{
            filter: brightness(85%);
        }}
        
        /* Pie chart styling */
        .pie-chart-container {{
            padding: 10px;
            background-color: #111111;
            border-radius: 10px;
            margin-bottom: 15px;
        }}

        /* Ensure question container uses card styling */
        .question-container {{
            background-color: #111111;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid {accent_color};
        }}

    

        /* Ensure plotly container uses card styling */
        .plotly-container {{
            background-color: #111111;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid {accent_color};
        }}
    </style>
    """, unsafe_allow_html=True)

class Interview:
    def __init__(self, groq_api_key, deepgram_api_key):
        self.GROQ_API_KEY = groq_api_key
        self.DEEPGRAM_API_KEY = deepgram_api_key
        self.client = Groq(api_key=self.GROQ_API_KEY)
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, api_key=self.GROQ_API_KEY)
        if "current_q" not in st.session_state:
            st.session_state.current_q = 0
        if "questions" not in st.session_state:
            st.session_state.questions = []
        if "responses" not in st.session_state:
            st.session_state.responses = []
        if "feedback" not in st.session_state:
            st.session_state.feedback = []
        if "audio_volume" not in st.session_state:
            st.session_state.audio_volume = 1.0
        if "recorder_key" not in st.session_state:
            st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
        if "answer_times" not in st.session_state:
            st.session_state.answer_times = []
        if "start_time" not in st.session_state:
            st.session_state.start_time = None

    def sidebar_upload_and_summary(self):
        with st.sidebar:
            st.markdown("### 📤 Upload Questions")
            file_uploaded = st.file_uploader("Upload the interview questions (.md file)", type=["md", "txt"])
        if file_uploaded and not st.session_state.questions:
            try:
                content = file_uploaded.read().decode("utf-8")
            except UnicodeDecodeError:
                st.error("Failed to decode file. Ensure it’s a valid .md or .txt file with UTF-8 encoding.")
                st.stop()
            questions = []
            try:
                question_sections = re.split(r"## \d+[.\-]\s*", content)[1:]
                for section in question_sections:
                    lines = section.strip().split("\n")
                    if len(lines) < 2:
                        st.error("Invalid question format in file.")
                        st.stop()
                    question_type = lines[0].split(" Question")[0].strip()
                    question_text = " ".join(lines[1:]).strip()
                    if question_type and question_text:
                        questions.append({"type": question_type, "question": question_text})
            except Exception as e:
                st.error(f"Error parsing file: {str(e)}")
                st.stop()
            if not questions:
                st.error("No valid questions found in the file.")
                st.stop()
            st.session_state.current_q = 0
            st.session_state.questions = questions
            st.session_state.responses = ["" for _ in questions]
            st.session_state.feedback = ["" for _ in questions]
            st.session_state.answer_times = [None for _ in questions]
            st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
            st.success(f"Loaded {len(questions)} questions.")
        with st.sidebar:
            st.markdown("### 🎚️ Audio Settings")
            st.session_state.audio_volume = st.slider("Audio volume", 0.0, 1.0, st.session_state.audio_volume, 0.1)
            st.markdown("### 📊 Interview Summary")
            for i, q in enumerate(st.session_state.questions):
                with st.expander(f"Question {i+1}"):
                    st.write(f"**Type:** {q['type']}")
                    st.markdown(f"**Question:** {q['question']}")
                    st.write(f"**Response:** {st.session_state.responses[i] if st.session_state.responses[i] else 'Not answered'}")
                    st.markdown(f"**Feedback:** {st.session_state.feedback[i] if st.session_state.feedback[i] else 'No feedback yet'}")
                    if st.session_state.answer_times[i] is not None:
                        st.write(f"**Time Taken:** {timedelta(seconds=int(st.session_state.answer_times[i]))}")

    def run(self):
        apply_custom_css()  # Apply the custom CSS
        st.markdown('<h1>🎙️Interview assistant</h1>', unsafe_allow_html=True)
        self.sidebar_upload_and_summary()
        if not st.session_state.questions:
            st.info("Please upload a question file to start the interview.")
            return
        if st.session_state.current_q < 0 or st.session_state.current_q >= len(st.session_state.questions):
            st.error(f"Invalid question index: {st.session_state.current_q}. Resetting to 0.")
            st.session_state.current_q = 0
            st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
            st.session_state.start_time = None
            st.rerun()

        q = st.session_state.questions[st.session_state.current_q]
        with st.container():
            st.markdown(
                f'<div class="question-container"><h2>Question {st.session_state.current_q+1} of {len(st.session_state.questions)}</h2>'
                f'<p>{q["question"]}</p></div>',
                unsafe_allow_html=True
            )
        with st.sidebar:
            st.markdown("### 📈 Progress")
            progress = (st.session_state.current_q + 1) / len(st.session_state.questions)
            st.progress(progress)
            st.markdown(f"**{st.session_state.current_q + 1}/{len(st.session_state.questions)}** questions completed")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔊 Play Question"):
                voice = "Deedee-PlayAI"
                model = "playai-tts"
                response_format = "mp3"
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                    temp_path = tmp_file.name
                try:
                    with st.spinner("Just a Second..."):
                        response = self.client.audio.speech.create(
                            model=model,
                            voice=voice,
                            input=f"This is a {q['type']} question: {q['question']}",
                            response_format=response_format
                        )
                        response.write_to_file(temp_path)
                    with open(temp_path, "rb") as audio_file:
                        audio_bytes = audio_file.read()
                        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                    audio_html = f"""
                    <audio id="question-audio" autoplay style="display:none;">
                        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                    </audio>
                    <script>
                        var audio = document.getElementById("question-audio");
                        if (audio) {{
                            audio.volume = {st.session_state.audio_volume};
                        }}
                    </script>
                    """
                    st.markdown(audio_html, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Failed to generate or play audio: {str(e)}")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

        st.markdown('<h3>🎤 Your Interviewer</h3>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="audio-recorder">', unsafe_allow_html=True)
            audio = mic_recorder(start_prompt="Start Interview", stop_prompt="Stop Interview", key=st.session_state.recorder_key)
            st.markdown('</div>', unsafe_allow_html=True)
        if audio:
            st.audio(audio['bytes'])
            if st.session_state.start_time is None:
                st.session_state.start_time = time.time()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile:
                tmpfile.write(audio['bytes'])
                tmpfile_path = tmpfile.name
            deepgram = DeepgramClient(api_key=self.DEEPGRAM_API_KEY)
            with open(tmpfile_path, "rb") as file:
                buffer_data = file.read()
            payload: FileSource = {"buffer": buffer_data}
            options = PrerecordedOptions(model="nova-3", smart_format=True)
            response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
            text = response.to_dict()["results"]["channels"][0]["alternatives"][0]["paragraphs"]["transcript"]
            st.session_state.responses[st.session_state.current_q] = text
            if st.session_state.start_time is not None:
                time_taken = time.time() - st.session_state.start_time
                st.session_state.answer_times[st.session_state.current_q] = time_taken
                st.session_state.start_time = None
            st.markdown("**The Response:**")
            st.write(text)

            type_q = q['type']
            if type_q == 'Basic':
                type_q = "HR Recruiter"
            elif type_q == 'Technical':
                type_q = "Technical Expert"
            else:
                type_q = "Manager or Team Lead"

            prompt = f"""
            You are an experienced {type_q} interviewer assessing a candidate's answer.

            **Question:** {q['question']}
            **Candidate Response:** {text}

            ⚠️ Important: Do not be biased in your evaluation. Focus only on the quality, clarity, and correctness of the response.

            Your task:
            1. Evaluate the overall quality of the response.
            2. Highlight strengths and positive aspects.
            3. Identify specific weaknesses or missing points.
            4. Suggest clear, actionable improvements.
            5. Provide a **Confidence Score** (1-10) for how confidently the response was delivered.
            6. Provide an **Accuracy Score** (1-10) for how factually correct the response is, based on the question.

            Format your response exactly as follows:

            Evaluation:
            [Your evaluation text here]

            Strengths:
            - [Strength 1]
            - [Strength 2]

            Weaknesses:
            - [Weakness 1]
            - [Weakness 2]

            Suggestions for Improvement:
            - [Suggestion 1]
            - [Suggestion 2]

            Confidence Score: X/10
            Accuracy Score: X/10
            """

            try:
                ai_response = self.llm.invoke(prompt).content
                st.session_state.feedback[st.session_state.current_q] = ai_response
            except Exception as e:
                st.error(f"Failed to get AI feedback: {str(e)}")
        if st.session_state.feedback[st.session_state.current_q]:
            st.markdown(f'<h3>🤖 AI Feedback</h3><div class="card">{st.session_state.feedback[st.session_state.current_q]}</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Previous Question", disabled=st.session_state.current_q == 0):
                st.session_state.current_q -= 1
                st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
                st.session_state.start_time = None
                st.rerun()
        with col2:
            if st.button("➡️ Next Question", disabled=st.session_state.current_q >= len(st.session_state.questions) - 1):
                st.session_state.current_q += 1
                st.session_state.recorder_key = f"recorder_{st.session_state.current_q}"
                st.session_state.start_time = None
                st.rerun()
        if st.button("✅ Finish Interview"):
            self.finish_report()

    def finish_report(self):
        all_responded = all(r.strip() for r in st.session_state.responses)
        st.success("Interview completed!")
        if not all_responded:
            st.warning("Some questions have no responses. The report may be incomplete.")
        scores = []
        for feedback in st.session_state.feedback:
            if feedback:
                match = re.search(r"Confidence Score: (\d+)/10.*Accuracy Score: (\d+)/10", feedback, re.DOTALL)
                if match:
                    scores.append((int(match.group(1)), int(match.group(2))))
        with st.container():
            st.markdown('<div class="plotly-container">', unsafe_allow_html=True)
            if scores:
                avg_confidence = sum(s[0] for s in scores) / len(scores)
                avg_accuracy = sum(s[1] for s in scores) / len(scores)
                st.markdown(f"<h3>Average Scores</h3><p><strong>Confidence:</strong> {avg_confidence:.1f}/10</p><p><strong>Accuracy:</strong> {avg_accuracy:.1f}/10</p>", unsafe_allow_html=True)
                labels = [f"Q{i+1}" for i in range(len(scores))]
                confidence_data = [s[0] for s in scores]
                accuracy_data = [s[1] for s in scores]
                fig = go.Figure(data=[
                    go.Bar(name="Confidence", x=labels, y=confidence_data, marker_color="#2563eb", text=confidence_data, textposition="auto"),
                    go.Bar(name="Accuracy", x=labels, y=accuracy_data, marker_color="#dc2626", text=accuracy_data, textposition="auto")
                ])
                fig.update_layout(
                    barmode="group",
                    yaxis=dict(range=[0, 10], title="Score", gridcolor="#e5e7eb"),
                    xaxis=dict(title="Questions"),
                    title=dict(text="Interview Performance Scores", x=0.5, xanchor="center"),
                    template="plotly_white",
                    height=400,
                    margin=dict(t=50, b=50, l=50, r=50),
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No scores available to display the graph. Please ensure all questions have feedback.")
            st.markdown('</div>', unsafe_allow_html=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        markdown_report = "# Interview Report\n\n"
        for i, q in enumerate(st.session_state.questions):
            markdown_report += f"## Question {i+1}\n"
            markdown_report += f"**Type:** {q['type']}\n\n"
            markdown_report += f"**Question:** {q['question']}\n\n"
            markdown_report += f"**User Response:** {st.session_state.responses[i] if st.session_state.responses[i] else 'Not answered'}\n\n"
            markdown_report += f"**AI Feedback:**\n{st.session_state.feedback[i] if st.session_state.feedback[i] else 'No feedback'}\n\n"
            time_taken = st.session_state.answer_times[i]
            markdown_report += f"**Time Taken:** {timedelta(seconds=int(time_taken)) if time_taken else 'Not recorded'}\n\n"
            markdown_report += "---\n\n"
        if scores:
            markdown_report += f"**Average Confidence Score:** {avg_confidence:.1f}/10\n\n"
            markdown_report += f"**Average Accuracy Score:** {avg_accuracy:.1f}/10\n\n"
        st.download_button(
            label="📥 Download Feedback Report",
            data=markdown_report.encode("utf-8"),
            file_name=f"interview_feedback_Requirement_Agent😎.md",
            mime="text/markdown",
            key="download_button",
            help="Download the interview report as a Markdown file"
        )