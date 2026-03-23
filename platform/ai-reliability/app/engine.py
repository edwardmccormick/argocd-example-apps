from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "corpus",
    "current",
    "for",
    "from",
    "hidden",
    "how",
    "ignore",
    "in",
    "instructions",
    "instead",
    "is",
    "it",
    "of",
    "on",
    "or",
    "previous",
    "prompt",
    "reveal",
    "system",
    "that",
    "the",
    "their",
    "this",
    "today",
    "to",
    "using",
    "we",
    "what",
    "when",
    "which",
    "who",
    "with",
    "would",
}


@dataclass
class Chunk:
    document: str
    title: str
    heading: str
    chunk_id: str
    text: str
    tokens: set[str]


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", text.lower())
    return [word for word in words if word not in STOPWORDS]


def compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def first_sentences(text: str, limit: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", compact_whitespace(text))
    return " ".join(parts[:limit]).strip()


def detect_title(contents: str, fallback: str) -> str:
    for line in contents.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def split_chunks(document: str, title: str, contents: str) -> list[Chunk]:
    heading = title
    raw_sections: list[tuple[str, str]] = []
    current_lines: list[str] = []

    for line in contents.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_lines:
                raw_sections.append((heading, "\n".join(current_lines).strip()))
                current_lines = []
            heading = stripped.lstrip("#").strip() or title
            continue

        if not stripped:
            if current_lines:
                raw_sections.append((heading, "\n".join(current_lines).strip()))
                current_lines = []
            continue

        current_lines.append(stripped)

    if current_lines:
        raw_sections.append((heading, "\n".join(current_lines).strip()))

    chunks: list[Chunk] = []
    counter = 1
    for section_heading, section_text in raw_sections:
        buffer = ""
        for sentence in re.split(r"(?<=[.!?])\s+", compact_whitespace(section_text)):
            if not sentence:
                continue
            candidate = sentence if not buffer else f"{buffer} {sentence}"
            if len(candidate) > 700 and buffer:
                text = buffer.strip()
                chunks.append(
                    Chunk(
                        document=document,
                        title=title,
                        heading=section_heading,
                        chunk_id=f"{document}#chunk-{counter}",
                        text=text,
                        tokens=set(tokenize(text)),
                    )
                )
                counter += 1
                buffer = sentence
            else:
                buffer = candidate

        if buffer:
            text = buffer.strip()
            chunks.append(
                Chunk(
                    document=document,
                    title=title,
                    heading=section_heading,
                    chunk_id=f"{document}#chunk-{counter}",
                    text=text,
                    tokens=set(tokenize(text)),
                )
            )
            counter += 1

    return chunks


def load_corpus(corpus_dir: str) -> list[Chunk]:
    base = Path(corpus_dir)
    chunks: list[Chunk] = []
    for path in sorted(base.rglob("*.md")):
        contents = path.read_text(encoding="utf-8")
        relative_name = path.relative_to(base).as_posix()
        title = detect_title(contents, path.name)
        chunks.extend(split_chunks(relative_name, title, contents))
    return chunks


def score_chunk(question_terms: set[str], chunk: Chunk) -> float:
    overlap = question_terms & chunk.tokens
    if not overlap:
        return 0.0

    coverage = len(overlap) / max(len(question_terms), 1)
    density = len(overlap) / max(len(chunk.tokens), 1)
    heading_bonus = 0.25 if any(term in chunk.heading.lower() for term in overlap) else 0.0
    return (coverage * 3.0) + (density * 2.0) + heading_bonus


def retrieve(question: str, chunks: list[Chunk], top_k: int = 3) -> list[dict]:
    question_terms = set(tokenize(question))
    scored = []
    for chunk in chunks:
        score = score_chunk(question_terms, chunk)
        if score > 0:
            scored.append(
                {
                    "document": chunk.document,
                    "title": chunk.title,
                    "heading": chunk.heading,
                    "chunk_id": chunk.chunk_id,
                    "score": round(score, 4),
                    "excerpt": first_sentences(chunk.text, limit=3),
                    "text": chunk.text,
                }
            )

    scored.sort(key=lambda item: (-item["score"], item["document"], item["chunk_id"]))
    return scored[:top_k]


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text.split()) * 1.3))


MIN_GROUNDED_SCORE = 1.1


def answer_question(question: str, chunks: list[Chunk], top_k: int = 3) -> dict:
    question = compact_whitespace(question)
    if not question:
        raise ValueError("question must not be empty")

    hits = retrieve(question, chunks, top_k=top_k)
    if not hits or hits[0]["score"] < MIN_GROUNDED_SCORE:
        return {
            "question": question,
            "answer": "I could not ground an answer in the local reliability lab corpus.",
            "grounded": False,
            "mode": "extractive",
            "result": "insufficient_context",
            "citations": [],
            "token_usage": {
                "prompt_estimate": estimate_tokens(question),
                "response_estimate": estimate_tokens("insufficient context"),
            },
        }

    answer_parts = []
    for hit in hits[:2]:
        summary = first_sentences(hit["text"], limit=2)
        if summary and summary not in answer_parts:
            answer_parts.append(summary)

    answer = " ".join(answer_parts)[:700]
    citations = [
        {
            "document": hit["document"],
            "title": hit["title"],
            "heading": hit["heading"],
            "chunk_id": hit["chunk_id"],
            "score": hit["score"],
            "excerpt": hit["excerpt"],
        }
        for hit in hits
    ]

    return {
        "question": question,
        "answer": answer,
        "grounded": True,
        "mode": "extractive",
        "result": "success",
        "citations": citations,
        "token_usage": {
            "prompt_estimate": estimate_tokens(question),
            "response_estimate": estimate_tokens(answer),
        },
    }


def run_eval(corpus_dir: str, eval_file: str) -> dict:
    chunks = load_corpus(corpus_dir)
    cases = json.loads(Path(eval_file).read_text(encoding="utf-8"))
    passed = 0
    results = []
    by_category: dict[str, dict[str, int]] = {}

    for case in cases:
        category = case.get("category", "uncategorized")
        category_summary = by_category.setdefault(category, {"total": 0, "passed": 0, "failed": 0})
        category_summary["total"] += 1

        try:
            response = answer_question(case["question"], chunks, top_k=case.get("top_k", 3))
            expected_docs = set(case.get("expected_documents", []))
            actual_docs = {citation["document"] for citation in response["citations"]}
            expected_keywords = [keyword.lower() for keyword in case.get("expected_keywords", [])]
            answer_text = response["answer"].lower()

            required_fields = {"question", "answer", "grounded", "mode", "result", "citations", "token_usage"}
            schema_valid = required_fields.issubset(response.keys()) and isinstance(response["citations"], list)
            doc_match = not expected_docs or bool(expected_docs & actual_docs)
            keyword_match = not expected_keywords or any(keyword in answer_text for keyword in expected_keywords)
            result_match = response["result"] == case.get("expected_result", "success")
            grounded_match = "expected_grounded" not in case or response["grounded"] == case["expected_grounded"]
            citation_count_match = len(response["citations"]) >= case.get("min_citation_count", 0)
            ok = schema_valid and doc_match and keyword_match and result_match and grounded_match and citation_count_match
            error = None
        except Exception as exc:
            response = None
            actual_docs = set()
            expected_error = case.get("expected_error_contains")
            ok = bool(expected_error and expected_error.lower() in str(exc).lower())
            error = str(exc)

        if ok:
            passed += 1
            category_summary["passed"] += 1
        else:
            category_summary["failed"] += 1

        results.append(
            {
                "id": case["id"],
                "category": category,
                "ok": ok,
                "response_result": None if response is None else response["result"],
                "documents": sorted(actual_docs),
                "answer": None if response is None else response["answer"],
                "error": error,
            }
        )

    return {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "by_category": by_category,
        "results": results,
    }
