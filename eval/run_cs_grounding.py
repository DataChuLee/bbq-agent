"""CS 답변의 주장이 정답 CS 문서로 뒷받침되는지 평가한다.

실행 방법:
    venv\\Scripts\\python.exe -m eval.run_cs_grounding --split dev --system baseline
    venv\\Scripts\\python.exe -m eval.run_cs_grounding --split dev --system baseline --rescore

시스템:
    baseline  기존 프롬프트 + 상담원용 원문 검색 결과
    grounded  근거 제한 프롬프트 + 상담원용 원문 검색 결과
    customer  고객 문구 프롬프트 + 검수한 고객 안내 문구 검색 결과(현재 서비스)
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
CUSTOMER_PATH = EVAL_DIR.parent / "Data" / "BBQ_CS_customer.csv"
# 상담원용 원문에만 있는 내부 정책 용어다. 고객 답변에 나오면 내부 정보가 샌 것으로 본다.
LEAK_TERMS = ("보상", "강성", "보험", "사제", "차림비", "계도", "미수긍", "미 수긍")
# 생성 모델(gpt-4o-mini)과 다른 모델로 채점해야 자기 답에 후한 점수를 주지 않는다.
# 사람 판정 113개와 비교해 고른 모델이다(eval.score_cs_judge_calibration).
JUDGE_MODEL = "gpt-5.4-mini"
# 주장 나누기와 근거 판정을 분리해야 같은 주장 목록으로 사람과 채점자를 비교할 수 있다.
CLAIMS_PROMPT = """아래 [답변]을 검증 가능한 주장 단위로 나누세요.
인사말, 사과, 공감, "도움이 되었으면 합니다" 같은 표현은 제외하세요. 주장이 없으면 빈 목록입니다.

[답변]
{answer}
"""
VERIFY_PROMPT = """당신은 고객센터 답변의 근거를 검증하는 평가자입니다.

[주장 목록]의 각 주장이 [정답 문서]로 직접 뒷받침되면 supported, 문서에 없거나 문서와 다르면 unsupported로 판정하세요.

규칙:
- 외부 지식이나 상식으로 보완하지 마세요.
- 답변이 문서보다 더 구체적이면(연락처, 기한, 보상 약속, 문서에 없는 절차) unsupported입니다.
- 고객에게 사진 촬영, 앱 신고, 전화 문의 등을 안내했는데 문서에 그 행동이 없으면 unsupported입니다.
- 문서는 상담원용 처리 절차입니다. 상담원이 고객에게 받는 것(사진, 계좌번호 등)을 고객에게 준비·제공해 달라고 안내하면 supported입니다. 상담원·BBQ가 직접 하는 일(매장에 전화, 운영부서 전달, 보상 제안)을 고객이 직접 하거나 요청하라고 바꾸면 unsupported입니다.
- 한 주장 안에 문서에 없는 내용이 일부라도 섞여 있으면(추가로 준비할 정보, 바뀐 조건, 과장) 주장 전체가 unsupported입니다.
- 연락처나 절차를 문서에 적힌 용도와 다른 용도로 안내하면 unsupported입니다.
- 문서와 같은 뜻을 다른 말로 표현한 것은 supported입니다.
- supported일 때만 evidence_indexes에 문서 번호를 넣으세요.
- 주장 목록과 같은 순서, 같은 개수로 판정하고 claim에는 주장을 그대로 적으세요.

[주장 목록]
{claims}

[정답 문서]
{reference}
"""


COVERAGE_PROMPT = """당신은 고객센터 답변을 평가하는 평가자입니다.

[정답 안내]를 고객에게 꼭 전해야 할 핵심 내용 2~6개로 나누세요.
각 내용이 [답변]에 같은 뜻으로 들어 있으면 covered=true, 없으면 false로 판정하세요.

[답변]
{answer}

[정답 안내]
{reference}
"""


def _load_reference_rows() -> dict[str, str]:
    df = pd.read_excel(CS_DATA_PATH)
    return {
        str(row["CS 구분"]): "\n".join(f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col]))
        for _, row in df.iterrows()
    }


def _load_customer_answers() -> dict[str, str]:
    df = pd.read_csv(CUSTOMER_PATH, encoding="utf-8-sig", keep_default_na=False)
    return {str(r["CS 구분"]): f"{r['고객 안내']}\n고객에게 받을 것: {r['고객에게 받을 것']}" for _, r in df.iterrows()}


def _raw_search_cs():
    """고객 문구로 바꾸기 전의 search_cs다. 이전 시스템을 같은 조건으로 다시 재기 위해 남긴다."""
    from langchain_core.tools import tool

    from tools.cs_query_rules import keep_cs_query
    from tools.cs_retrieval import build_cs_retriever
    from tools.search_cs import search_cs

    @tool("search_cs", description=search_cs.description)
    def raw_search_cs(query: str) -> str:
        docs = build_cs_retriever().invoke(keep_cs_query(query))
        results = [
            {
                "content": d.page_content,
                "cs_category": d.metadata.get("cs_category", ""),
                "claim_category": d.metadata.get("claim_category", ""),
            }
            for d in docs
        ]
        return json.dumps({"results": results}, ensure_ascii=False)

    return raw_search_cs


def _build_agent(system: str):
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    from graph.graph import CS_SYSTEM_PROMPT, _ReActState
    from tools.search_cs import search_cs

    prompt, tool = {
        "baseline": (BASELINE_CS_PROMPT, _raw_search_cs()),
        "grounded": (GROUNDED_CS_PROMPT, _raw_search_cs()),
        "customer": (CS_SYSTEM_PROMPT, search_cs),
    }[system]
    return create_react_agent(
        model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
        tools=[tool],
        prompt=prompt,
        state_schema=_ReActState,
    )


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


# 고객 문구로 바꾸기 전 graph의 CS 프롬프트다. 기준선을 같은 조건으로 다시 재기 위해 사본으로 고정한다.
BASELINE_CS_PROMPT = """당신은 BBQ 치킨 고객센터 AI 어시스턴트입니다. 고객의 문의에 친절하고 실용적으로 답변합니다.

답변 순서:
1. search_cs(query)로 관련 CS 사례를 검색합니다.
2. 검색 결과를 바탕으로 고객에게 명확하게 안내합니다.

답변 원칙:
- 항상 한국어로 답변합니다.
- **고객 관점**으로 작성합니다. "저희가 처리해드립니다"가 아니라 "고객님이 취하실 수 있는 조치"를 중심으로 설명합니다.
- CS 내부 처리 절차를 그대로 나열하지 말고, 고객이 실제로 해야 할 행동(연락 방법, 준비할 정보, 요청 방법 등)을 구체적으로 알려주세요.
- 사진 촬영·보관, 앱 또는 전화로 신고하기, 준비할 정보 등 실질적인 다음 행동을 포함합니다.
- 검색 결과에 없는 정보는 만들어내지 않습니다.
- 브라우저 자동화나 주문 도구는 사용하지 않습니다."""


def leaked_terms(answer: str) -> list[str]:
    return [term for term in LEAK_TERMS if term in answer]


assert leaked_terms("매장 미수긍시 보상 제안") == ["보상", "미수긍"]
assert leaked_terms("매장에 확인해 안내드리겠습니다.") == []


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


def _judge_llm(model: str):
    from langchain_openai import ChatOpenAI

    # 추론 모델(gpt-5 계열)은 temperature를 바꿀 수 없다.
    return ChatOpenAI(model=model, temperature=0) if model.startswith("gpt-4") else ChatOpenAI(model=model)


def extract_claims(answer: str, model: str = JUDGE_MODEL) -> list[str]:
    from pydantic import BaseModel

    class Claims(BaseModel):
        claims: list[str]

    return _judge_llm(model).with_structured_output(Claims).invoke(CLAIMS_PROMPT.format(answer=answer)).claims


def verify_claims(claims: list[str], reference: str, model: str = JUDGE_MODEL) -> list[dict]:
    from benchmarks.run_groundedness import GroundednessAssessment

    if not claims:
        return []
    numbered = "\n".join(f"{i}. {claim}" for i, claim in enumerate(claims, start=1))
    judge = _judge_llm(model).with_structured_output(GroundednessAssessment)
    verdicts = judge.invoke(VERIFY_PROMPT.format(claims=numbered, reference=reference)).verdicts
    if len(verdicts) != len(claims):
        raise ValueError(f"주장 {len(claims)}개에 판정 {len(verdicts)}개가 돌아왔습니다.")
    # 채점자가 주장 문구를 바꿔 적어도 원래 주장 기준으로 저장한다.
    return [{**v.model_dump(), "claim": claim} for v, claim in zip(verdicts, claims)]


def _judge(answer: str, reference: str) -> list[dict]:
    return verify_claims(extract_claims(answer), reference)


def _coverage(answer: str, reference: str) -> list[dict]:
    """근거성만 보면 말을 줄인 답변이 이기므로, 문서의 핵심 처리를 전했는지도 잰다."""
    from pydantic import BaseModel

    class StepCheck(BaseModel):
        step: str
        covered: bool

    class CoverageAssessment(BaseModel):
        steps: list[StepCheck]

    judge = _judge_llm(JUDGE_MODEL).with_structured_output(CoverageAssessment)
    assessment = judge.invoke(COVERAGE_PROMPT.format(answer=answer, reference=reference))
    return [step.model_dump() for step in assessment.steps]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--system", choices=("baseline", "grounded", "customer"), required=True)
    # 채점 기준만 바뀌었을 때 답변은 그대로 두고 다시 채점한다.
    parser.add_argument("--rescore", action="store_true")
    args = parser.parse_args()
    output_path = RESULTS_DIR / f"cs_grounding_{args.split}_{args.system}.json"
    # test는 최종 비교에서 시스템마다 한 번만 돌린다.
    if args.split == "test" and output_path.exists():
        raise SystemExit(f"test 결과가 이미 있습니다: {output_path}")

    load_dotenv()
    references = _load_reference_rows()
    customer_answers = _load_customer_answers()
    if args.rescore:
        answered = json.loads(output_path.read_text(encoding="utf-8"))
    else:
        agent = _build_agent(args.system)
        cases = json.loads((EVAL_DIR / "cs_golden_queries.json").read_text(encoding="utf-8"))
        answered = []
        for case in (c for c in cases if c["split"] == args.split):
            answer, retrieved = await _answer(agent, case["query"])
            answered.append({**case, "answer": answer, "retrieved": retrieved})

    rows = []
    for row in answered:
        case = {k: row[k] for k in ("id", "query", "gold_categories", "split") if k in row}
        answer, retrieved = row["answer"], row["retrieved"]
        # 근거성은 원문 전체로 본다. 고객 문구도 원문에 있는 사실만 썼기 때문이다.
        reference = "\n\n".join(f"[{i}] {references[c]}" for i, c in enumerate(case["gold_categories"], start=1))
        verdicts = _judge(answer, reference)
        unsupported = sum(v["verdict"] == "unsupported" for v in verdicts)
        # 포괄성은 고객에게 전해야 할 안내 기준이다. 원문 기준이면 내부 절차를 빼는 시스템이 손해를 본다.
        steps = _coverage(answer, customer_answers[case["gold_categories"][0]])
        rows.append({
            **case,
            "answer": answer,
            "retrieved": retrieved,
            "leaked_terms": leaked_terms(answer),
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
    print(f"내부 정보 노출 답변: {sum(bool(r['leaked_terms']) for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
