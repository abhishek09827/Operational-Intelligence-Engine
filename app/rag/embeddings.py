from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings

class EmbeddingService:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY
        )

    def generate_embedding(self, text: str) -> list[float]:
        return self.embeddings.embed_query(text)
