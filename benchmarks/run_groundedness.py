"""API 최종 답변의 사실 주장이 검색 근거로 지지되는지 평가한다."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from benchmarks.groundedness_metrics import claim_support_summary


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT / "benchmarks" / "data" / "groundedness_cases.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"


class ClaimVerdict(BaseModel):
    claim: str = Field(description="답변에서 분리한 단일 사실 주장")
    verdict: Literal["supported", "unsupported"]
    evidence_indexes: list[int] = Field(default_factory=list)
    reason: str


class GroundednessAssessment(BaseModel):
    verdicts: list[ClaimVerdict]


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def _create_session(base_url: str) -> str:
    request = Request(f"{base_url}/sessions", data=b"", method="POST")
    with urlopen(request, timeout=30) as response:
        return str(json.loads(response.read().decode("utf-8"))["data"]["id"])


def _generate_response(base_url: str, query: str) -> tuple[str, list[dict[str, Any]], str]:
    session_id = _create_session(base_url)
    payload = _post_json(
        f"{base_url}/sessions/{session_id}/responses",
        {"input": {"type": "text", "content": query}},
    )["data"]
    message = payload["message"]
    answer = str(message.get("content") or "")
    return answer, list(payload.get("sources") or []), str(payload.get("intent") or "unknown")


def _judge(answer: str, sources: list[dict[str, Any]]) -> GroundednessAssessment:
    context = "\n\n".join(
        f"[{index}] {source.get('content', '')}"
        for index, source in enumerate(sources, start=1)
    )
    judge = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(
        GroundednessAssessment
    )
    prompt = f"""당신은 RAG 답변 근거 일치율 평가자입니다.

아래 답변에서 검증 가능한 사실 주장과 실행 안내를 원자 단위로 나누세요. 인사말·감사·공감·향후 노력 표현은 출력에서 제외하세요. 남은 각 주장이 제공된 근거만으로 직접 지지되면 supported, 근거와 모순되거나 근거에 없으면 unsupported로 판정하세요.

규칙:
- 외부 지식이나 상식으로 보완하지 마세요.
- supported일 때만 evidence_indexes에 근거 번호를 하나 이상 넣으세요.
- 답변의 표현이 근거보다 더 구체적이면 unsupported입니다.
- 연락처, 주문 정보, 사진 요청, 환불·보상·처리 절차 등 실행 안내는 모두 검증 대상입니다.
- 검증 대상이 아닌 인사말만 있는 답변이면 verdicts는 빈 목록으로 반환하세요.

[답변]
{answer}

[검색 근거]
{context or '(검색 근거 없음)'}
"""
    return judge.invoke(prompt)


def run(base_url: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        try:
            answer, sources, intent = _generate_response(base_url, str(case["query"]))
            assessment = _judge(answer, sources)
            verdicts = [item.model_dump() for item in assessment.verdicts]
            rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "intent": intent,
                    "answer": answer,
                    "source_count": len(sources),
                    "sources": sources,
                    "verdicts": verdicts,
                    "summary": claim_support_summary(verdicts),
                }
            )
        except Exception as exc:
            rows.append({"id": case["id"], "query": case["query"], "error": str(exc)})

    successful_rows = [row for row in rows if "error" not in row]
    all_verdicts = [
        verdict
        for row in successful_rows
        for verdict in row["verdicts"]
    ]
    aggregate = claim_support_summary(all_verdicts)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "judge_model": "gpt-4o-mini",
        "method": "LLM-as-a-judge against API-returned retrieval sources",
        "summary": {
            "case_count": len(rows),
            "success_count": len(successful_rows),
            "error_count": len(rows) - len(successful_rows),
            **aggregate,
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 답변 근거 일치율 측정")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--cases-file", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    os.environ["LANGSMITH_TRACING"] = "false"
    load_dotenv()
    cases = json.loads(args.cases_file.read_text(encoding="utf-8"))
    report = run(args.base_url.rstrip("/"), cases)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "groundedness.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {output}")
    print("Claim support rate:", f"{report['summary']['claim_support_rate']:.1%}")


if __name__ == "__main__":
    main()
