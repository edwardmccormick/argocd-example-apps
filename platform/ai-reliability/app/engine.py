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
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "we",
    "what",
    "when",
    "which",
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


def answer_question(question: str, chunks: list[Chunk], top_k: int = 3) -> dict:
    question = compact_whitespace(question)
    if not question:
        raise ValueError("question must not be empty")

    hits = retrieve(question, chunks, top_k=top_k)
    if not hits:
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

    for case in cases:
        response = answer_question(case["question"], chunks, top_k=case.get("top_k", 3))
        expected_docs = set(case.get("expected_documents", []))
        actual_docs = {citation["document"] for citation in response["citations"]}
        expected_keywords = [keyword.lower() for keyword in case.get("expected_keywords", [])]
        answer_text = response["answer"].lower()

        doc_match = not expected_docs or bool(expected_docs & actual_docs)
        keyword_match = not expected_keywords or any(keyword in answer_text for keyword in expected_keywords)
        result_match = response["result"] == case.get("expected_result", "success")
        ok = doc_match and keyword_match and result_match
        if ok:
            passed += 1

        results.append(
            {
                "id": case["id"],
                "ok": ok,
                "response_result": response["result"],
                "documents": sorted(actual_docs),
                "answer": response["answer"],
            }
        )

    return {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "results": results,
    }
