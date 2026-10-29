"""CS 답변의 주장이 정답 CS 문서로 뒷받침되는지 평가한다.

실행 방법:
    venv\\Scripts\\python.exe -m eval.run_cs_grounding --split dev --system baseline
"""

import argparse
import asyncio
import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
CS_DATA_PATH = EVAL_DIR.parent / "Data" / "BBQ_CS.xlsx"
# 생성 모델(gpt-4o-mini)과 다른 모델로 채점해야 자기 답에 후한 점수를 주지 않는다.
JUDGE_MODEL = "gpt-4.1"
JUDGE_PROMPT = """당신은 고객센터 답변의 근거를 검증하는 평가자입니다.

아래 [답변]을 검증 가능한 주장 단위로 나누세요. 인사말, 사과, 공감, "도움이 되었으면 합니다" 같은 표현은 제외하세요.
남은 각 주장이 [정답 문서]로 직접 뒷받침되면 supported, 문서에 없거나 문서와 다르면 unsupported로 판정하세요.

규칙:
- 외부 지식이나 상식으로 보완하지 마세요.
- 답변이 문서보다 더 구체적이면(연락처, 기한, 보상 약속, 문서에 없는 절차) unsupported입니다.
- 고객에게 사진 촬영, 앱 신고, 전화 문의 등을 안내했는데 문서에 그 행동이 없으면 unsupported입니다.
- supported일 때만 evidence_indexes에 문서 번호를 넣으세요.
- 검증할 주장이 없으면 verdicts는 빈 목록입니다.

[답변]
{answer}

[정답 문서]
{reference}
"""


COVERAGE_PROMPT = """당신은 고객센터 답변을 평가하는 평가자입니다.

[정답 문서]의 '대응 방법'과 '조치 사항'을 고객에게 전할 만한 핵심 처리 내용 2~6개로 나누세요.
각 내용이 [답변]에 같은 뜻으로 들어 있으면 covered=true, 없으면 false로 판정하세요.

[답변]
{answer}

[정답 문서]
{reference}
"""


def _load_reference_rows() -> dict[str, str]:
    df = pd.read_excel(CS_DATA_PATH)
    return {
        str(row["CS 구분"]): "\n".join(f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col]))
        for _, row in df.iterrows()
    }


def _build_agent(prompt: str):
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    from graph.graph import _ReActState
    from tools.search_cs import search_cs

    return create_react_agent(
        model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
        tools=[search_cs],
        prompt=prompt,
        state_schema=_ReActState,
    )


def _system_prompts() -> dict[str, str]:
    from graph.graph import CS_SYSTEM_PROMPT

    return {"baseline": CS_SYSTEM_PROMPT, "grounded": GROUNDED_CS_PROMPT}


# CS 데이터는 상담원용 처리 절차라서, 고객 행동 대신 BBQ가 할 처리를 문서 그대로 전하게 한다.
GROUNDED_CS_PROMPT = """당신은 BBQ 치킨 고객센터 AI 어시스턴트입니다.

답변 순서:
1. search_cs(query)로 관련 CS 사례를 검색합니다.
2. 고객 문의와 맞는 사례의 '대응 방법'과 '조치 사항'만 근거로 답합니다.

답변 원칙:
- 항상 한국어로, 짧고 정중하게 답합니다.
- 사례의 처리 절차를 고객이 이해할 수 있는 말로 바꿔 "BBQ가 이렇게 확인·처리합니다"로 안내합니다.
- 검색 결과에 없는 내용은 절대 쓰지 않습니다. 특히 전화번호·연락처, 환불·교환·보상 약속, 처리 기한, 고객이 따로 해야 할 행동(사진 촬영, 앱 신고 등)은 사례에 적혀 있을 때만 씁니다.
- 맞는 사례가 없으면 추측하지 말고, 확인 후 안내드리겠다고만 답합니다.
- 브라우저 자동화나 주문 도구는 사용하지 않습니다."""


async def _answer(agent, query: str) -> tuple[str, list[str]]:
    from langchain_core.messages import HumanMessage, ToolMessage

    from graph.graph import _extract_response

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=query)], "menu_results": {}, "cs_results": {}, "selected_order": None}
    )
    retrieved = []
    for message in result["messages"]:
        if isinstance(message, ToolMessage):
            try:
                retrieved += [r["cs_category"] for r in json.loads(message.content).get("results", [])]
            except (json.JSONDecodeError, AttributeError):
                continue
    return str(_extract_response(result["messages"]).get("message", "")), retrieved


def _judge(answer: str, reference: str) -> list[dict]:
    from langchain_openai import ChatOpenAI

    from benchmarks.run_groundedness import GroundednessAssessment

    judge = ChatOpenAI(model=JUDGE_MODEL, temperature=0).with_structured_output(GroundednessAssessment)
    assessment = judge.invoke(JUDGE_PROMPT.format(answer=answer, reference=reference))
    return [verdict.model_dump() for verdict in assessment.verdicts]


def _coverage(answer: str, reference: str) -> list[dict]:
    """근거성만 보면 말을 줄인 답변이 이기므로, 문서의 핵심 처리를 전했는지도 잰다."""
    from langchain_openai import ChatOpenAI
    from pydantic import BaseModel

    class StepCheck(BaseModel):
        step: str
        covered: bool

    class CoverageAssessment(BaseModel):
        steps: list[StepCheck]

    judge = ChatOpenAI(model=JUDGE_MODEL, temperature=0).with_structured_output(CoverageAssessment)
    assessment = judge.invoke(COVERAGE_PROMPT.format(answer=answer, reference=reference))
    return [step.model_dump() for step in assessment.steps]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--system", default="baseline")
    args = parser.parse_args()
    output_path = RESULTS_DIR / f"cs_grounding_{args.split}_{args.system}.json"
    # test는 최종 비교에서 시스템마다 한 번만 돌린다.
    if args.split == "test" and output_path.exists():
        raise SystemExit(f"test 결과가 이미 있습니다: {output_path}")

    load_dotenv()
    references = _load_reference_rows()
    agent = _build_agent(_system_prompts()[args.system])
    cases = json.loads((EVAL_DIR / "cs_golden_queries.json").read_text(encoding="utf-8"))
    cases = [c for c in cases if c["split"] == args.split]

    rows = []
    for case in cases:
        answer, retrieved = await _answer(agent, case["query"])
        reference = "\n\n".join(f"[{i}] {references[c]}" for i, c in enumerate(case["gold_categories"], start=1))
        verdicts = _judge(answer, reference)
        unsupported = sum(v["verdict"] == "unsupported" for v in verdicts)
        # 포괄성은 대표 문서 하나를 기준으로 본다. 겹치는 문서까지 요구하면 과하다.
        steps = _coverage(answer, references[case["gold_categories"][0]])
        rows.append({
            **case,
            "answer": answer,
            "retrieved": retrieved,
            "retrieval_hit": any(c in retrieved for c in case["gold_categories"]),
            "verdicts": verdicts,
            "claim_count": len(verdicts),
            "unsupported_count": unsupported,
            # 주장이 하나도 없는 답변은 근거를 따질 수 없어 성공으로 치지 않는다.
            "fully_grounded": bool(verdicts) and unsupported == 0,
            "coverage_steps": steps,
            "coverage": sum(s["covered"] for s in steps) / len(steps) if steps else 0.0,
        })

    RESULTS_DIR.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    claims = sum(r["claim_count"] for r in rows)
    unsupported = sum(r["unsupported_count"] for r in rows)
    print(f"{args.split}/{args.system} n={len(rows)} → {output_path}")
    print(f"근거 없는 주장이 없는 답변: {sum(r['fully_grounded'] for r in rows)}/{len(rows)}")
    print(f"주장 지지율: {claims - unsupported}/{claims} = {(claims - unsupported) / max(claims, 1):.1%}")
    print(f"핵심 처리 포괄성 평균: {sum(r['coverage'] for r in rows) / len(rows):.1%}")
    print(f"검색 적중: {sum(r['retrieval_hit'] for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
