# Implementation Plan — readme-mermaid-arch

## Change
`README.md` 라인 19~33의 ASCII 아키텍처 다이어그램을 Mermaid `graph TD`로 교체한다.

## Target File
- `README.md` (lines 19–33)

## Mermaid Diagram Design

```mermaid
graph TD
    A[사용자 입력] --> B[Intent Classifier\nGPT-4o-mini]
    B -->|menu| C[Menu Agent Node\nReAct + SelfQueryRetriever + ChromaDB]
    B -->|cs| D[CS Agent Node\nReAct + EnsembleRetriever + FAISS/BM25]
    B -->|unknown| E[Fallback Node\n대화 이력 기반 안내]
    C --> F[FastAPI\n/chat · /chat/stream · /session]
    D --> F
    E --> F
    F --> G[Next.js Chat UI\n메뉴 카드 · 텍스트 · 재질문 렌더링]
```

## Validation
- README.md가 올바른 Mermaid 코드블록(```mermaid ... ```)을 포함하는지 육안 확인
- GitHub/GitLab 렌더링 확인 (push 후)

## Rollback
- git checkout README.md
