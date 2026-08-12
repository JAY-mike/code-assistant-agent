"""Online retrieval defaults must remain the measured hybrid baseline."""

from app.routers.search_router import SearchRequest


def test_search_defaults_to_hybrid_without_expensive_experimental_stages():
    request = SearchRequest(query="How is JSONStorage implemented?")

    assert request.use_hybrid is True
    assert request.use_hyde is False
    assert request.use_rerank is False


def test_hyde_and_rerank_are_explicit_opt_in_flags():
    request = SearchRequest(
        query="How is JSONStorage implemented?",
        use_hyde=True,
        use_rerank=True,
    )

    assert request.use_hyde is True
    assert request.use_rerank is True
