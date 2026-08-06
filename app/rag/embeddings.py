from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings
import hashlib

class EmbeddingService:
    def __init__(self):
        model_name = settings.GEMINI_EMBEDDING_MODEL
        if not model_name.startswith("models/"):
            model_name = "models/gemini-embedding-001"
        
        if settings.GOOGLE_API_KEY:
            try:
                self.embeddings = GoogleGenerativeAIEmbeddings(
                    model=model_name,
                    google_api_key=settings.GOOGLE_API_KEY
                )
            except Exception:
                self.embeddings = None
        else:
            self.embeddings = None

    def generate_embedding(self, text: str) -> list[float]:
        if self.embeddings:
            try:
                return self.embeddings.embed_query(text)
            except Exception as e:
                print(f"Embedding generation API fallback: {e}")
        
        # Deterministic local fallback embedding vector (768 dimensions)
        h = hashlib.sha256(text.encode()).digest()
        vector = [(b / 255.0) - 0.5 for b in h]
        while len(vector) < 768:
            vector.extend(vector[:768 - len(vector)])
        return vector[:768]

