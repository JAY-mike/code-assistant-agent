"""Static definitions for the public code knowledge bases."""

from dataclasses import dataclass

from app.config import PROJECT_ROOT, settings


@dataclass(frozen=True)
class KnowledgeBase:
    id: str
    label: str
    collection_name: str
    repo_path: str


TINYDB_KNOWLEDGE_BASE = "tinydb"
PROJECT_KNOWLEDGE_BASE = "project"
DEFAULT_KNOWLEDGE_BASE = TINYDB_KNOWLEDGE_BASE

KNOWLEDGE_BASES = {
    TINYDB_KNOWLEDGE_BASE: KnowledgeBase(
        id=TINYDB_KNOWLEDGE_BASE,
        label="TinyDB",
        collection_name="system_code",
        repo_path=settings.REPO_PATH,
    ),
    PROJECT_KNOWLEDGE_BASE: KnowledgeBase(
        id=PROJECT_KNOWLEDGE_BASE,
        label="Code Assistant Agent",
        collection_name="project_code",
        repo_path=settings.PROJECT_SOURCE_PATH or str(PROJECT_ROOT),
    ),
}


def get_knowledge_base(knowledge_base_id: str) -> KnowledgeBase:
    try:
        return KNOWLEDGE_BASES[knowledge_base_id]
    except KeyError as exc:
        raise ValueError(f"Unknown knowledge base '{knowledge_base_id}'") from exc
