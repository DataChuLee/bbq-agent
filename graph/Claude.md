# graph/ — 작업 내역

## 파일 목록

| 파일 | 역할 |
|---|---|
| `__init__.py` | 패키지 초기화 |
| `state.py` | LangGraph 공유 상태 (`AgentState`) 정의 |
| `graph.py` | LangGraph StateGraph 구성 (Intent Classifier → Menu/CS/Fallback Node + ReAct 루프) |

---

## state.py

```python
class AgentState(TypedDict):
    messages: List[BaseMessage]   # 전체 대화 이력 (Human + AI + Tool)
    intent: Optional[str]         # "menu" | "cs" | "unknown"
    response: dict                # 최종 응답
```

### 필드 설명

| 필드 | 타입 | 역할 |
|---|---|---|
| `messages` | `List[BaseMessage]` | Human / AI / ToolMessage 전체 이력. 모든 Node가 읽고 씀 |
| `intent` | `Optional[str]` | Intent Classifier Node가 설정. `"menu"` / `"cs"` / `"unknown"` |
| `response` | `dict` | 최종 응답. 메뉴 카드 JSON 또는 `{"type": "text", "message": "..."}` |

---

## graph.py

### 그래프 구조
```
START
  └─► intent_classifier (LLM 의도 분류)
        ├─► menu_agent  (create_react_agent wrapper)  ─► END
        ├─► cs_agent    (create_react_agent wrapper)  ─► END
        └─► fallback    (안내 메시지)                  ─► END
```

### Node 역할

| Node | 역할 | 사용 Tool |
|---|---|---|
| `intent_classifier` | LLM 프롬프트로 menu/cs/unknown 분류 | 없음 (직접 LLM 호출) |
| `menu_agent` | `create_react_agent` 호출 후 response 추출 | search_menu, ask_clarification, final_answer_menu |
| `cs_agent` | `create_react_agent` 호출 후 response 추출 | search_cs, final_answer_cs |
| `fallback` | unknown 의도 → 안내 문구 반환 | 없음 |

### ReAct 루프 구현 방식 (리팩토링)

**변경 전**: `for _ in range(MAX_ITERATIONS)` 수동 루프 + 직접 tool 실행 (~50줄/노드)

**변경 후**: `langgraph.prebuilt.create_react_agent` 사용 (~5줄/노드)

```python
from langgraph.prebuilt import create_react_agent

_menu_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=_menu_tools,
    prompt=MENU_SYSTEM_PROMPT,
)

def menu_agent_node(state):
    result = _menu_agent.invoke({"messages": state["messages"]})
    return {"messages": result["messages"], "response": _extract_response(result["messages"])}
```

### ReAct 루프 종료 조건 (create_react_agent 내장)
- LLM이 tool_calls 없는 AIMessage 반환 시 → 자동 종료
- `final_answer_*` / `ask_clarification` 실행 후 LLM은 자연스럽게 tool_calls 없이 종료

### response 추출 방식
messages를 역순 탐색 → `ToolMessage.content`에서 `"type"` 키가 있는 JSON 반환
```python
def _extract_response(messages):
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            data = json.loads(msg.content)
            if "type" in data:   # menu_cards / text / clarification
                return data
```

### 싱글턴 인스턴스
```python
# FastAPI에서 바로 import해서 사용
from graph.graph import graph
result = graph.invoke({"messages": [...], "intent": None, "response": {}})
```

---

### state.py 설계 결정

- `messages`를 LangChain `BaseMessage` 타입으로 유지 → `create_react_agent`와 자연스럽게 연결
- `intent`는 Optional로 선언 → 초기 State 생성 시 None으로 시작 가능
- `response`는 dict → 메뉴(카드 JSON)와 CS(텍스트) 두 형태를 하나의 필드로 처리
