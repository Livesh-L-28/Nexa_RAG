"""
Reciprocal Rank Fusion (RRF) Algorithm
Combines ranked lists from disparate retrieval systems (BM25 sparse + FAISS dense).
Formula: RRF(d) = sum(weight_m / (k + rank_m(d)))
"""
from typing import Dict, List, Tuple

def reciprocal_rank_fusion(
    ranked_lists: List[List[str]],
    k: int = 60,
    weights: List[float] = None
) -> List[Tuple[str, float]]:
    """
    Compute reciprocal rank fusion scores for a set of ranked document identifiers.
    
    Args:
        ranked_lists: List of document ID lists, each sorted by retrieval relevance.
        k: Smoothing constant to control impact of top-ranked outliers (default: 60).
        weights: Relative weight multiplier per retrieval source.
        
    Returns:
        Sorted list of tuples (doc_id, fused_score) in descending order of relevance.
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
        
    scores: Dict[str, float] = {}
    for rank_list, weight in zip(ranked_lists, weights):
        for rank, doc_id in enumerate(rank_list, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight * (1.0 / (k + rank))
            
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
