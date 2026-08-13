"""Optional RAGAS evaluation for the TinyDB retrieval-and-answer pipeline.

Install with ``python -m pip install -r requirements-eval.txt``. The script
uses the configured LLM as the judge unless RAGAS_JUDGE_* variables override
it. It makes paid judge calls and should be run deliberately, not in CI.
"""

import argparse
import json
import os
from pathlib import Path

from app.agent.eval_tasks import EVAL_TASKS
from app.agent.llm import call_llm
from app.config import settings
from app.rag.knowledge_bases import (
    DEFAULT_KNOWLEDGE_BASE,
    KNOWLEDGE_BASES,
    get_knowledge_base,
)


PROJECT_EVAL_SET_PATHS = (
    Path(__file__).resolve().parents[1] / "data" / "eval" / "project_eval_set.json",
    Path(__file__).resolve().parents[1] / "data" / "eval" / "project_eval_set_extra.json",
)


def load_eval_tasks(knowledge_base_id: str) -> list[dict]:
    """Load the reviewed test set for a supported public knowledge base."""
    if knowledge_base_id == "tinydb":
        return EVAL_TASKS
    if knowledge_base_id == "project":
        tasks = []
        for path in PROJECT_EVAL_SET_PATHS:
            with path.open(encoding="utf-8") as file:
                tasks.extend(json.load(file))
        return tasks
    raise ValueError(f"No evaluation set for knowledge base '{knowledge_base_id}'")


def retrieve_contexts(
    question: str,
    knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE,
    top_k: int = 5,
) -> list[str]:
    """Use the production Hybrid RAG retrieval path for each evaluation item."""
    from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
    from app.rag.fusion import rrf
    from app.rag.sparse_retriever import SparseRetriever

    knowledge_base = get_knowledge_base(knowledge_base_id)
    dense = DenseRetriever(collection_name=knowledge_base.collection_name)
    sparse = SparseRetriever.from_redis(knowledge_base.collection_name)
    if sparse.count() == 0:
        raise RuntimeError(
            f"BM25 index for '{knowledge_base.id}' is unavailable. "
            "Start Redis and rebuild that knowledge base first."
        )

    dense_results = dense.search(question, k=top_k * 2, where=SYSTEM_CORPUS)
    sparse_results = sparse.search(question, k=top_k * 2)
    fused = rrf([dense_results, sparse_results], top_n=top_k)
    return [result["text"] for result in fused]


def answer_with_context(
    question: str,
    contexts: list[str],
    knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE,
) -> str:
    evidence = "\n\n---\n\n".join(contexts)
    prompt = (
        f"Question:\n{question}\n\n"
        f"Retrieved code context:\n{evidence}\n\n"
        "Answer only from the retrieved context. If it is insufficient, say so."
    )
    return call_llm(
        prompt,
        system_prompt=(
            f"You are a careful {get_knowledge_base(knowledge_base_id).label} "
            "code assistant. Answer in Chinese."
        ),
    )


def build_samples(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE) -> list[dict]:
    """Build the RAGAS question, context, answer, and reference contract."""
    samples = []
    for task in load_eval_tasks(knowledge_base_id):
        contexts = retrieve_contexts(task["question"], knowledge_base_id)
        answer = answer_with_context(task["question"], contexts, knowledge_base_id)
        samples.append({
            "question": task["question"],
            "contexts": contexts,
            "answer": answer,
            "ground_truth": task["reference"],
        })
    return samples


def _judge_base_url(endpoint: str) -> str:
    suffix = "/chat/completions"
    if not endpoint.endswith(suffix):
        raise RuntimeError(
            "RAGAS requires an OpenAI-compatible chat-completions endpoint."
        )
    return endpoint[:-len(suffix)]


def run(knowledge_base_id: str = DEFAULT_KNOWLEDGE_BASE) -> None:
    try:
        from datasets import Dataset
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.metrics import answer_correctness, context_precision
    except ImportError as exc:
        import traceback
        traceback.print_exc()
        raise SystemExit(
            "Install optional evaluation dependencies first: "
            "python -m pip install -r requirements-eval.txt"
        ) from exc

    judge_endpoint = os.getenv("RAGAS_JUDGE_ENDPOINT", settings.LLM_API_ENDPOINT)
    judge_model = os.getenv("RAGAS_JUDGE_MODEL", settings.LLM_MODEL)
    judge_key = os.getenv("RAGAS_JUDGE_API_KEY", settings.LLM_API_KEY)
    if not judge_key:
        raise SystemExit("RAGAS_JUDGE_API_KEY or LLM_API_KEY must be configured.")

    judge = ChatOpenAI(
        model=judge_model,
        openai_api_key=judge_key,
        openai_api_base=_judge_base_url(judge_endpoint),
        temperature=0,
    )
    local_embeddings = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": settings.EMBEDDING_DEVICE},
    )
    dataset = Dataset.from_list(build_samples(knowledge_base_id))
    result = evaluate(
        dataset,
        metrics=[context_precision, answer_correctness],
        llm=judge,
        embeddings=local_embeddings,
    )
    print(result)
    print(
        f"RAGAS is an LLM-judge result on the '{knowledge_base_id}' reviewed set; "
        "record the model, prompt, index version, and run date with every result."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--knowledge-base",
        choices=sorted(KNOWLEDGE_BASES),
        default=DEFAULT_KNOWLEDGE_BASE,
    )
    arguments = parser.parse_args()
    run(arguments.knowledge_base)
