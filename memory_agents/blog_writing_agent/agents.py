"""
Newsletter/Blog Writing Agent with Memori Integration

Agent functions for:
1. Knowledge Agent: Analyzes uploaded documents to extract writing style, tone, and structure
2. Writing Agent: Generates new content using the stored writing style information

Requirements:
- pip install streamlit pypdf python-docx openai python-dotenv
- Set DIGITAL_OCEAN_ENDPOINT and DIGITAL_OCEAN_AGENT_ACCESS_KEY in environment or .env file
"""

from pathlib import Path
from typing import Dict, Any, List
import json
import os

from docx import Document
from dotenv import load_dotenv
from memori import Memori, create_memory_tool
import io
import openai
import pypdf
import tempfile
load_dotenv()

# Check for required Digital Ocean credentials
DIGITAL_OCEAN_ENDPOINT = os.getenv("DIGITAL_OCEAN_ENDPOINT")
DIGITAL_OCEAN_AGENT_ACCESS_KEY = os.getenv("DIGITAL_OCEAN_AGENT_ACCESS_KEY")

if not DIGITAL_OCEAN_ENDPOINT or not DIGITAL_OCEAN_AGENT_ACCESS_KEY:
    raise ValueError("Digital Ocean AI credentials not found in environment variables")

print("🤖 Setting up Digital Ocean AI client...")

# Configure Digital Ocean AI endpoint
base_url = (
    DIGITAL_OCEAN_ENDPOINT
    if DIGITAL_OCEAN_ENDPOINT.endswith("/api/v1/")
    else f"{DIGITAL_OCEAN_ENDPOINT}/api/v1/"
)

# Initialize Digital Ocean AI client
client = openai.OpenAI(
    base_url=base_url,
    api_key=DIGITAL_OCEAN_AGENT_ACCESS_KEY,
)


# Initialize Memori
def initialize_memori():
    """Initialize Memori memory system"""
    try:
        memory_system = Memori(
            database_connect="sqlite:///tmp/newsletter_style_memory.db",
            auto_ingest=True,
            conscious_ingest=True,
            verbose=False,
            namespace="newsletter_writing_style",
        )
        memory_system.enable()
        return memory_system
    except Exception as e:
        raise Exception(f"Failed to initialize Memori: {e}")


# Create memory tool
def create_memory_tool_instance(memory_system):
    """Create memory tool instance"""
    return create_memory_tool(memory_system)


def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from PDF file"""
    try:
        pdf_reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise Exception(f"Error reading PDF: {e}")


def extract_text_from_docx(docx_file) -> str:
    """Extract text from DOCX file"""
    try:
        doc = Document(docx_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        raise Exception(f"Error reading DOCX: {e}")


def extract_text_from_txt(txt_file) -> str:
    """Extract text from TXT file"""
    try:
        return txt_file.read().decode("utf-8")
    except Exception as e:
        raise Exception(f"Error reading TXT: {e}")


def analyze_writing_style(text: str) -> Dict[str, Any]:
    """Analyze writing style using Digital Ocean AI"""
    try:
        prompt = f"""
        Analyze the following text and extract the author's writing style characteristics.
        Focus on:
        1. Tone (formal, casual, professional, friendly, etc.)
        2. Writing structure (how paragraphs are organized, transitions, etc.)
        3. Vocabulary level and complexity
        4. Sentence structure patterns
        5. Use of examples, analogies, or storytelling
        6. Overall voice and personality

        Text to analyze:
        {text[:3000]}  # Limit to first 3000 characters for analysis

        Provide your analysis in JSON format with these keys:
        - tone: string describing the tone
        - structure: string describing paragraph and content structure
        - vocabulary: string describing vocabulary level and style
        - sentence_patterns: string describing sentence structure
        - examples_style: string describing how examples/analogies are used
        - voice: string describing overall voice/personality
        - writing_habits: list of specific writing habits or patterns
        """

        response = client.chat.completions.create(
            model="n/a",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert writing analyst. Analyze the given text and provide detailed insights about the author's writing style in JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        analysis_text = response.choices[0].message.content
        # Extract JSON from response
        try:
            # Find JSON content between ```json and ``` markers
            if "```json" in analysis_text:
                json_start = analysis_text.find("```json") + 7
                json_end = analysis_text.find("```", json_start)
                json_content = analysis_text[json_start:json_end].strip()
            else:
                # Try to find JSON content
                json_start = analysis_text.find("{")
                json_end = analysis_text.rfind("}") + 1
                json_content = analysis_text[json_start:json_end]

            return json.loads(json_content)
        except:
            # Fallback: create structured response
            return {
                "tone": "Professional",
                "structure": "Well-organized with clear transitions",
                "vocabulary": "Advanced with technical terms",
                "sentence_patterns": "Varied sentence lengths",
                "examples_style": "Uses relevant examples",
                "voice": "Authoritative and informative",
                "writing_habits": [
                    "Clear headings",
                    "Logical flow",
                    "Professional language",
                ],
            }

    except Exception as e:
        raise Exception(f"Error analyzing writing style: {e}")


def store_writing_style_in_memori(
    memory_system, style_analysis: Dict[str, Any], original_text: str
):
    """Store writing style analysis in Memori as a simple conversation"""
    try:
        # Create a simple conversation about the writing style
        user_input = f"Hi AI, here is my writing style: {style_analysis.get('tone', 'N/A')} tone, {style_analysis.get('voice', 'N/A')} voice, {style_analysis.get('structure', 'N/A')} structure, {style_analysis.get('vocabulary', 'N/A')} vocabulary, and {len(style_analysis.get('writing_habits', []))} writing habits including {', '.join(style_analysis.get('writing_habits', [])[:3])}."

        ai_response = f"I understand your writing style! You write with a {style_analysis.get('tone', 'N/A')} tone and {style_analysis.get('voice', 'N/A')} voice. Your structure is {style_analysis.get('structure', 'N/A')} and you use {style_analysis.get('vocabulary', 'N/A')} vocabulary. Your key writing habits include {', '.join(style_analysis.get('writing_habits', []))}. I'll use this to write content that sounds exactly like you."

        # Record the conversation in memory
        memory_system.record_conversation(
            user_input=user_input,
            ai_output=ai_response,
            model="n/a",
            metadata={
                "type": "writing_style_profile",
                "style_data": style_analysis,
                "text_length": len(original_text),
                "analysis_timestamp": "now",
            },
        )

        return ai_response

    except Exception as e:
        raise Exception(f"Error storing in memory: {e}")


def generate_blog_with_style(memory_tool, topic: str) -> str:
    """Generate blog content using stored writing style from memory"""
    try:
        # Get writing style context from memory
        writing_style_context = ""
        try:
            context_result = memory_tool.execute(query="writing style")
            if context_result and "No relevant memories found" not in str(
                context_result
            ):
                writing_style_context = str(context_result)[
                    :300
                ]  # Limit context length
        except Exception:
            pass  # Continue without context if search fails

        # Create appropriate prompt based on whether we have writing style
        if writing_style_context:
            prompt = f"Write a blog post about {topic}. Use this writing style: {writing_style_context}"
        else:
            prompt = f"Write a professional and engaging blog post about {topic}. Make it informative, well-structured, and easy to read."

        response = client.chat.completions.create(
            model="n/a",
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        return response.choices[0].message.content

    except Exception as e:
        raise Exception(f"Error generating blog: {e}")


def get_stored_writing_style(memory_tool):
    """Retrieve stored writing style profile from memory"""
    try:
        # Try multiple queries to find the writing style (following digital_ocean.py pattern)
        queries = [
            "writing style tone voice",
            "writing style analysis",
            "style profile habits",
            "writing characteristics",
        ]

        for query in queries:
            try:
                result = memory_tool.execute(query=query.strip())
                if result and "No relevant memories found" not in str(result):
                    return result
            except Exception:
                continue  # Try next query if one fails

        return None
    except Exception as e:
        raise Exception(f"Error retrieving writing style: {e}")


def save_generated_blog(memory_system, topic: str, blog_content: str):
    """Save generated blog content to memory"""
    try:
        memory_system.record_conversation(
            user_input=f"Generated blog post about: {topic}",
            ai_output=blog_content,
            model="n/a",
            metadata={
                "type": "generated_blog",
                "topic": topic,
                "word_count": len(blog_content.split()),
                "generated_timestamp": "now",
            },
        )
        return True
    except Exception as e:
        raise Exception(f"Error saving blog to memory: {e}")