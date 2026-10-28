# Tests

## 폴더 목적

애플리케이션 계약과 회귀 위험이 큰 동작을 자동 검증한다.

## 주요 엔트리포인트

- `test_sse_error_stream.py`: SSE 오류 이벤트와 부분 응답 저장 방지 계약을 검증한다.
- `test_search_preview_api.py`: OpenAPI 검색 경로와 search-preview 요청·응답 계약을 검증한다.

## 로컬 계약

- 외부 네트워크나 실제 OpenAI 호출 없이 실행 가능해야 한다.
- 오류 시 SSE는 `error` 이벤트를 내보내고 assistant 메시지를 저장하지 않는다.

## 수정 원칙

- HTTP·SSE 계약을 변경하면 성공·오류 경로를 모두 테스트한다.
- 테스트 더블은 필요한 메서드만 구현해 외부 의존성을 격리한다.

## 검증 방법

```powershell
venv\Scripts\python.exe -m pytest tests\test_sse_error_stream.py -q
```
