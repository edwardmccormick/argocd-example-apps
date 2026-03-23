from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from tracing import LangSmithClient, LangSmithRun


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


@dataclass
class GenerativeConfig:
    provider: str
    base_url: str
    api_key: str
    model: str


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


def normalize_result(grounded: bool, citations: list[dict]) -> str:
    return "success" if grounded and bool(citations) else "insufficient_context"


def format_response(question: str, answer: str, grounded: bool, mode: str, citations: list[dict], token_usage: dict) -> dict:
    return {
        "question": question,
        "answer": answer,
        "grounded": grounded,
        "mode": mode,
        "result": normalize_result(grounded, citations),
        "citations": citations,
        "token_usage": token_usage,
    }


def insufficient_context_response(question: str, mode: str) -> dict:
    return format_response(
        question=question,
        answer="I could not ground an answer in the local reliability lab corpus.",
        grounded=False,
        mode=mode,
        citations=[],
        token_usage={
            "prompt_estimate": estimate_tokens(question),
            "response_estimate": estimate_tokens("insufficient context"),
        },
    )


def citation_payload(hits: list[dict]) -> list[dict]:
    return [
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


def generative_config_from_env() -> GenerativeConfig:
    provider = os.environ.get("AI_GENERATIVE_PROVIDER", "gemini").strip().lower()
    base_url = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip().rstrip("/")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip()

    if not api_key:
        raise ValueError("generative mode requested but GEMINI_API_KEY is not configured")
    if not model:
        raise ValueError("generative mode requested but GEMINI_MODEL is not configured")
    if provider != "gemini":
        raise ValueError(f"unsupported generative provider: {provider}")

    return GenerativeConfig(provider=provider, base_url=base_url, api_key=api_key, model=model)


def extract_json_object(payload: str) -> dict:
    payload = payload.strip()
    if not payload:
        raise ValueError("generative provider returned an empty response")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", payload, re.DOTALL)
        if not match:
            raise ValueError("generative provider returned non-JSON content") from None
        return json.loads(match.group(0))


def call_gemini_generate_content(
    question: str,
    hits: list[dict],
    config: GenerativeConfig,
    tracer: LangSmithClient | None = None,
    parent_run: LangSmithRun | None = None,
) -> dict:
    allowed_chunk_ids = [hit["chunk_id"] for hit in hits]
    allowed_chunk_id_set = set(allowed_chunk_ids)
    context_lines = []
    for hit in hits:
        context_lines.append(
            "\n".join(
                [
                    f"chunk_id: {hit['chunk_id']}",
                    f"document: {hit['document']}",
                    f"heading: {hit['heading']}",
                    f"text: {hit['text']}",
                ]
            )
        )

    body = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "You answer questions only from the provided corpus chunks. "
                        "Return only JSON with keys: answer, grounded, cited_chunk_ids. "
                        "Set grounded to true only if the answer is supported by the supplied chunks. "
                        "cited_chunk_ids must contain only chunk_id values taken from the provided context. "
                        "If the context is insufficient, answer briefly, set grounded to false, and return an empty cited_chunk_ids array."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "\n\n".join(
                            [
                                f"Question: {question}",
                                f"Allowed chunk ids: {', '.join(allowed_chunk_ids)}",
                                "Context:",
                                "\n\n".join(context_lines),
                            ]
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
        },
    }

    req = request.Request(
        url=f"{config.base_url}/models/{config.model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-goog-api-key": config.api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    llm_run = None
    if tracer and parent_run:
        llm_run = tracer.start_run(
            name="gemini_generate_content",
            run_type="llm",
            inputs={
                "question": question,
                "provider": config.provider,
                "model": config.model,
                "allowed_chunk_ids": allowed_chunk_ids,
                "context_documents": [hit["document"] for hit in hits],
                "context_headings": [hit["heading"] for hit in hits],
            },
            parent_run_id=parent_run.id,
            metadata={"mode": "generative"},
            tags=["ai-docqa", "generative", "gemini"],
        )

    try:
        with request.urlopen(req, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if tracer and llm_run:
            tracer.end_run(llm_run, error_message=f"{exc.code} {detail[:500]}")
        raise ValueError(f"generative provider request failed: {exc.code} {detail}") from None
    except error.URLError as exc:
        if tracer and llm_run:
            tracer.end_run(llm_run, error_message=str(exc.reason))
        raise ValueError(f"generative provider request failed: {exc.reason}") from None

    candidates = raw.get("candidates", [])
    if not candidates:
        if tracer and llm_run:
            tracer.end_run(llm_run, error_message="generative provider returned no candidates")
        raise ValueError("generative provider returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    content = "".join(str(part.get("text", "")) for part in parts)
    parsed = extract_json_object(content)

    answer = compact_whitespace(str(parsed.get("answer", "")))
    grounded = bool(parsed.get("grounded", False))
    cited_chunk_ids = [str(item) for item in parsed.get("cited_chunk_ids", []) if str(item) in allowed_chunk_id_set]
    usage = raw.get("usageMetadata", {})

    result = {
        "answer": answer,
        "grounded": grounded,
        "cited_chunk_ids": cited_chunk_ids,
        "token_usage": {
            "prompt_estimate": usage.get("promptTokenCount", estimate_tokens(question)),
            "response_estimate": usage.get("candidatesTokenCount", estimate_tokens(answer or "insufficient context")),
        },
    }
    if tracer and llm_run:
        tracer.end_run(
            llm_run,
            outputs={
                "answer_preview": answer[:300],
                "grounded": grounded,
                "cited_chunk_ids": cited_chunk_ids,
                "token_usage": result["token_usage"],
            },
        )
    return result


def answer_question(
    question: str,
    chunks: list[Chunk],
    top_k: int = 3,
    mode: str = "extractive",
    tracer: LangSmithClient | None = None,
    parent_run: LangSmithRun | None = None,
) -> dict:
    question = compact_whitespace(question)
    if not question:
        raise ValueError("question must not be empty")

    mode = (mode or "extractive").strip().lower()
    if mode not in {"extractive", "generative"}:
        raise ValueError(f"unsupported mode: {mode}")

    retrieval_run = None
    if tracer and parent_run:
        retrieval_run = tracer.start_run(
            name="retrieve_corpus_chunks",
            run_type="retriever",
            inputs={"question": question, "top_k": top_k},
            parent_run_id=parent_run.id,
            metadata={"mode": mode},
            tags=["ai-docqa", "retrieval"],
        )

    hits = retrieve(question, chunks, top_k=top_k)
    if tracer and retrieval_run:
        tracer.end_run(
            retrieval_run,
            outputs={
                "hit_count": len(hits),
                "documents": [hit["document"] for hit in hits],
                "chunk_ids": [hit["chunk_id"] for hit in hits],
                "scores": {hit["chunk_id"]: hit["score"] for hit in hits},
            },
        )
    if not hits or hits[0]["score"] < MIN_GROUNDED_SCORE:
        return insufficient_context_response(question, mode=mode)

    if mode == "generative":
        config = generative_config_from_env()
        generated = call_gemini_generate_content(question, hits, config, tracer=tracer, parent_run=parent_run)
        citations_by_id = {hit["chunk_id"]: hit for hit in hits}
        citations = citation_payload([citations_by_id[chunk_id] for chunk_id in generated["cited_chunk_ids"]])
        grounded = generated["grounded"] and bool(citations)
        return format_response(
            question=question,
            answer=generated["answer"] or "I could not ground an answer in the local reliability lab corpus.",
            grounded=grounded,
            mode="generative",
            citations=citations if grounded else [],
            token_usage=generated["token_usage"],
        )

    answer_parts = []
    for hit in hits[:2]:
        summary = first_sentences(hit["text"], limit=2)
        if summary and summary not in answer_parts:
            answer_parts.append(summary)

    answer = " ".join(answer_parts)[:700]
    citations = citation_payload(hits)

    return format_response(
        question=question,
        answer=answer,
        grounded=True,
        mode="extractive",
        citations=citations,
        token_usage={
            "prompt_estimate": estimate_tokens(question),
            "response_estimate": estimate_tokens(answer),
        },
    )


def run_eval(corpus_dir: str, eval_file: str, mode: str = "extractive") -> dict:
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
            response = answer_question(case["question"], chunks, top_k=case.get("top_k", 3), mode=case.get("mode", mode))
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
