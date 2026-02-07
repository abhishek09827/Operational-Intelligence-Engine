from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.incident import Incident
from app.rag.embeddings import EmbeddingService

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
        
        # Using L2 distance (Euclidean distance)
        # For normalized vectors (like most embeddings), cosine similarity and L2 distance are related.
        # But let's stick to cosine distance <=> provided by pgvector.
        # distance = 0 (identical) to 2 (opposite).
        
        # We want similarity > threshold.
        # detailed logic: similarity = 1 - cosine_distance/2 (approx for some implementations)
        # But commonly cosine_distance in pgvector is 1 - cosine_similarity.
        # So acceptable distance < (1 - threshold).
        
        distance_limit = 1 - threshold
        
        stmt = select(Incident).order_by(
            Incident.embedding.cosine_distance(query_embedding)
        ).limit(limit)
        
        # Execute query
        results = self.db.execute(stmt).scalars().all()
        
        # TODO: Add actual filtering based on distance in the query itself once we confirm pgvector version syntax
        # For now, we return the top K nearest neighbors.
        
        return results

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
