"""
Resume Parser
Extracts structured information from resumes (PDF or text)
"""

import re
from typing import Dict, Any, Optional
from pypdf import PdfReader
from langchain_nebius import ChatNebius
from langchain_core.messages import SystemMessage, HumanMessage


RESUME_EXTRACTION_PROMPT = """You are an expert resume parser. Extract structured information from the resume text provided.

Extract the following information:
1. Name (if available)
2. Email
3. Phone number
4. Skills (list all technical and soft skills)
5. Work Experience (for each role: job title, company, duration, key responsibilities)
6. Education (degrees, institutions, years)
7. Certifications (if any)
8. Projects (if any, with brief descriptions)
9. Years of experience (estimate if not explicitly stated)
10. Key achievements and accomplishments

Format your response as a clear, structured summary that can be used to match against job descriptions.
Focus on technical skills, experience level, and relevant qualifications."""


def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from PDF file (handles file objects and file paths)"""
    try:
        # Reset file pointer if it's a file object
        if hasattr(pdf_file, "seek"):
            pdf_file.seek(0)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")


def parse_resume(resume_text: str, llm: Optional[ChatNebius] = None) -> Dict[str, Any]:
    """
    Parse resume text and extract structured information using LLM

    Args:
        resume_text: Raw text from resume
        llm: Optional LLM instance for extraction

    Returns:
        Dictionary with extracted resume information
    """
    if llm:
        try:
            messages = [
                SystemMessage(content=RESUME_EXTRACTION_PROMPT),
                HumanMessage(
                    content=f"Extract information from this resume:\n\n{resume_text[:4000]}"
                ),  # Limit length
            ]
            response = llm.invoke(messages)
            extracted_info = response.content
            return {
                "raw_text": resume_text,
                "extracted_summary": extracted_info,
                "parsed": True,
            }
        except Exception as e:
            # Fallback to basic extraction
            return basic_resume_extraction(resume_text)
    else:
        return basic_resume_extraction(resume_text)


def basic_resume_extraction(resume_text: str) -> Dict[str, Any]:
    """Basic resume extraction using regex patterns (fallback)"""
    # Extract email
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    emails = re.findall(email_pattern, resume_text)

    # Extract phone
    phone_pattern = r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    phones = re.findall(phone_pattern, resume_text)

    # Extract skills (common tech skills)
    skill_keywords = [
        "Python",
        "JavaScript",
        "Java",
        "C++",
        "React",
        "Node.js",
        "SQL",
        "AWS",
        "Docker",
        "Kubernetes",
        "Git",
        "Machine Learning",
        "AI",
        "Data Science",
        "TensorFlow",
        "PyTorch",
        "Django",
        "Flask",
        "FastAPI",
    ]
    found_skills = [
        skill for skill in skill_keywords if skill.lower() in resume_text.lower()
    ]

    return {
        "raw_text": resume_text,
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "skills": found_skills,
        "extracted_summary": f"Resume contains {len(found_skills)} identified skills: {', '.join(found_skills[:10])}",
        "parsed": True,
    }
