"""RAG, BM25, Hybrid Search & Reranker Isolation Tests (Invariants S7, S8, S11).

Proves that User B cannot retrieve User A's private document chunks through:
1. Dense Vector Search (pgvector cosine similarity)
2. Sparse BM25 Keyword Search
3. Hybrid Search Fusion
4. Cross-Encoder Reranking
5. End-to-End RAGPipeline query execution
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document, DocumentChunk, User
from app.rag.pipeline import RAGPipeline
from app.retrieval.bm25_search import BM25Search
from app.retrieval.hybrid_search import HybridSearch
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.vector_search import ScoredChunk, VectorSearch


@pytest.fixture
async def isolated_rag_dataset(db_session: AsyncSession):
    """Setup User A with confidential Document A and User B with public Document B."""
    user_a = User(
        id=uuid.uuid4(),
        email="owner_a@nexarag.ai",
        password_hash="hash_a",
        role="USER",
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        email="attacker_b@nexarag.ai",
        password_hash="hash_b",
        role="USER",
        is_active=True,
    )
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    # User A document containing confidential alpha credentials
    doc_a = Document(
        id=uuid.uuid4(),
        user_id=user_a.id,
        filename="project_alpha_secrets.txt",
        file_type="txt",
        file_size=500,
        storage_path="/tmp/project_alpha_secrets.txt",
        status="COMPLETED",
        chunk_count=2,
    )
    # User B document with generic content
    doc_b = Document(
        id=uuid.uuid4(),
        user_id=user_b.id,
        filename="user_b_notes.txt",
        file_type="txt",
        file_size=500,
        storage_path="/tmp/user_b_notes.txt",
        status="COMPLETED",
        chunk_count=1,
    )
    db_session.add_all([doc_a, doc_b])
    await db_session.flush()

    # Identical embedding vector to test semantic similarity collision
    shared_test_embedding = [0.8] * 384

    chunks_a = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_a.id,
            chunk_index=0,
            content="TOP SECRET PROJECT ALPHA: Quantum cryptographic keys are stored in vault-alpha-99.",
            embedding=shared_test_embedding,
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_a.id,
            chunk_index=1,
            content="Project Alpha internal database host is alpha-db.internal.corp.",
            embedding=shared_test_embedding,
        ),
    ]

    chunks_b = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_b.id,
            chunk_index=0,
            content="User B daily shopping list: apples, milk, bread, and coffee beans.",
            embedding=[0.01] * 384,
        ),
    ]
    db_session.add_all(chunks_a + chunks_b)
    await db_session.commit()

    return {
        "user_a": user_a,
        "doc_a": doc_a,
        "chunks_a": chunks_a,
        "user_b": user_b,
        "doc_b": doc_b,
        "chunks_b": chunks_b,
        "target_embedding": shared_test_embedding,
    }


@pytest.mark.asyncio
async def test_vector_search_strict_isolation(db_session: AsyncSession, isolated_rag_dataset):
    """Vector search must NEVER return User A's chunks when queried as User B.

    Even when User B provides the exact embedding vector matching User A's secret document.
    """
    data = isolated_rag_dataset
    vector_search = VectorSearch(db_session)

    # User B queries with vector that perfectly matches User A's chunks
    results_b = await vector_search.search(
        query_vector=data["target_embedding"],
        user_id=data["user_b"].id,
        top_k=10,
        similarity_threshold=0.0,
    )

    # User B must NOT receive any chunks from Document A
    chunk_ids_b = {r.chunk_id for r in results_b}
    for chunk_a in data["chunks_a"]:
        assert chunk_a.id not in chunk_ids_b

    # User A querying with the same vector DOES receive their own chunks
    results_a = await vector_search.search(
        query_vector=data["target_embedding"],
        user_id=data["user_a"].id,
        top_k=10,
        similarity_threshold=0.0,
    )
    chunk_ids_a = {r.chunk_id for r in results_a}
    assert any(c.id in chunk_ids_a for c in data["chunks_a"])


@pytest.mark.asyncio
async def test_bm25_keyword_strict_isolation(db_session: AsyncSession, isolated_rag_dataset):
    """BM25 search must NEVER return User A's chunks when searched by User B.

    Even when User B searches for exact keywords present in User A's document.
    """
    data = isolated_rag_dataset
    bm25 = BM25Search(db_session)

    # User B searches for exact keywords in User A's document
    query = "TOP SECRET PROJECT ALPHA Quantum cryptographic keys vault-alpha-99"
    results_b = await bm25.search(
        query=query,
        user_id=data["user_b"].id,
        top_k=10,
    )

    # Must be completely empty or contain only User B's documents
    assert len(results_b) == 0

    # User A searching the same query finds their document
    results_a = await bm25.search(
        query=query,
        user_id=data["user_a"].id,
        top_k=10,
    )
    assert len(results_a) >= 1
    assert "PROJECT ALPHA" in results_a[0].content


@pytest.mark.asyncio
async def test_hybrid_search_strict_isolation(db_session: AsyncSession, isolated_rag_dataset):
    """Hybrid search (Vector + BM25) must enforce tenant boundaries across both retrieval limbs."""
    data = isolated_rag_dataset
    hybrid = HybridSearch(db_session)

    # User B searches for User A's secrets
    query = "Where are Project Alpha cryptographic keys and database host?"
    results = await hybrid.search(
        query=query,
        user_id=data["user_b"].id,
        top_k=10,
        similarity_threshold=0.0,
    )

    for r in results:
        assert r.document_id != data["doc_a"].id
        assert "alpha" not in r.content.lower()


@pytest.mark.asyncio
async def test_reranker_cannot_introduce_unauthorized_content():
    """Reranker operates only on pre-authorized candidate chunks and cannot introduce cross-user data."""
    reranker = CrossEncoderReranker(enabled=False)  # Test passthrough / rerank logic

    # Authorized candidates for User B
    authorized_b = [
        ScoredChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            filename="user_b.txt",
            chunk_index=0,
            content="User B authorized chunk content",
            page_number=1,
            metadata={"user_id": "user_b_id"},
            score=0.8,
        )
    ]

    reranked = reranker.rerank(query="anything", candidates=authorized_b, top_k=5)
    assert len(reranked) == 1
    assert reranked[0].filename == "user_b.txt"


@pytest.mark.asyncio
async def test_pipeline_query_rag_isolation(db_session: AsyncSession, isolated_rag_dataset):
    """End-to-end RAGPipeline test: User B asking for User A's secret project

    verifies that User A's confidential excerpts NEVER enter User B's retrieved context.
    """
    data = isolated_rag_dataset
    pipeline = RAGPipeline(routing_enabled=False)

    response = await pipeline.query(
        session=db_session,
        query="What is the cryptographic key for Project Alpha?",
        user_id=data["user_b"].id,
        top_k=5,
        similarity_threshold=0.0,
    )

    # Context level verification:
    # 1. No chunks returned in retrieved_chunks belonging to doc_a
    for chunk_dict in response.retrieved_chunks:
        assert chunk_dict["document_id"] != str(data["doc_a"].id)
        assert "PROJECT ALPHA" not in chunk_dict.get("content_preview", "")

    # 2. No citations pointing to doc_a
    for source in response.sources:
        assert source.document_id != data["doc_a"].id
        assert "project_alpha_secrets" not in source.filename

    # 3. LLM answer cannot cite secret Project Alpha details from doc_a
    assert "vault-alpha-99" not in response.answer
