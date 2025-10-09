import os

from crewai_tools import QdrantVectorSearchTool
from dotenv import load_dotenv
from openai import OpenAI
from operator import le
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
import pdfplumber
import uuid
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Qdrant client
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

collection_name = os.getenv("QDRANT_COLLECTION_NAME", "rag_with_web_search")

# Extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text.strip())
    return text

# Generate OpenAI embeddings
def get_openai_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-large"
    )
    # print(f"Generated embedding for text: {text[:30]}...")
    print(f"Generated embedding: {response.data[0].embedding[:30]}...")

    print(f"the length is: {len(response.data[0].embedding)}")
    return response.data[0].embedding

# Store text and embeddings in Qdrant
def load_pdf_to_qdrant(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    # Extract text from PDF
    text_chunks = extract_text_from_pdf(pdf_path)

    # Create Qdrant collection
    if qdrant.collection_exists(collection_name):
        qdrant.delete_collection(collection_name)
    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=3072, distance=Distance.COSINE)
    )

    # Store embeddings
    points = []
    for chunk in text_chunks:
        embedding = get_openai_embedding(chunk)
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={"text": chunk}
        ))
    qdrant.upsert(collection_name=collection_name, points=points)

def get_qdrant_tool():
    try:
        # Initialize Qdrant search tool
        qdrant_tool = QdrantVectorSearchTool(
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            collection_name=collection_name,
            limit=3,
            score_threshold=0.35
        )
        print("Qdrant search tool initialized successfully.")
        return qdrant_tool
    except Exception as e:
        print(f"Failed to initialize Qdrant search tool: {e}")