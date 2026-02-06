import pytest
from unittest.mock import MagicMock, patch
from app.rag.embeddings import EmbeddingService
from app.rag.vector_db import VectorDBService
from app.models.incident import Incident

@patch('app.rag.embeddings.GoogleGenerativeAIEmbeddings')
def test_embedding_generation(mock_embeddings_class):
    mock_embeddings_instance = MagicMock()
    mock_embeddings_instance.embed_query.return_value = [0.1] * 768
    mock_embeddings_class.return_value = mock_embeddings_instance
    
    service = EmbeddingService()
    embedding = service.generate_embedding("test text")
    
    assert len(embedding) == 768
    assert embedding[0] == 0.1

@patch('app.rag.embeddings.GoogleGenerativeAIEmbeddings')
def test_vector_search(mock_embeddings_class):
    # Mock embedding generation
    mock_embeddings_instance = MagicMock()
    mock_embeddings_instance.embed_query.return_value = [0.1] * 768
    mock_embeddings_class.return_value = mock_embeddings_instance
    
    # Mock DB session
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [Incident(title="Test Incident")]
    mock_db.execute.return_value = mock_result
    
    service = VectorDBService(db_session=mock_db)
    results = service.search_similar_incidents("query", limit=1)
    
    assert len(results) == 1
    assert results[0].title == "Test Incident"
    mock_db.execute.assert_called_once()
