from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.incident import Incident
from app.rag.embeddings import EmbeddingService
from typing import List, Dict
import json

class VectorDBService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.embedding_service = EmbeddingService()

    def search_similar_incidents(self, query: str, limit: int = 3, threshold: float = 0.7):
        """
        Search for similar incidents using cosine similarity.
        Only return results with similarity score > threshold.
        """
        query_embedding = self.embedding_service.generate_embedding(query)
        
        # Fetch all incidents with embeddings
        stmt = select(Incident).where(Incident.embedding.isnot(None))
        results = self.db.execute(stmt).scalars().all()
        
        # Calculate cosine similarity manually
        scored_results = []
        for incident in results:
            if incident.embedding and isinstance(incident.embedding, list):
                similarity = self._cosine_similarity(query_embedding, incident.embedding)
                if similarity >= threshold:
                    scored_results.append((incident, similarity))
        
        # Sort by similarity and return top results
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [incident for incident, score in scored_results[:limit]]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)

    def store_incident_with_embedding(self, incident: Incident):
        """
        Generate embedding for the incident content and update the record.
        """
        # Create a text representation of the incident for embedding
        text_content = f"Title: {incident.title}\nDescription: {incident.description}\nRoot Cause: {incident.root_cause}"
        
        embedding_vector = self.embedding_service.generate_embedding(text_content)
        incident.embedding = embedding_vector
        
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident
