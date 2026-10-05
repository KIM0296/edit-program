# Product Spec

## 제품 정의

DaVinci Resolve에서 작업 중인 영상을 AI가 이해하고, 자연어 요청을 안전한 편집 명령으로 변환하여 반복적인 탐색·판단·러프컷 시간을 줄이는 AI Assistant Editor.

## 초기 타깃

DaVinci Resolve를 이미 사용하면서 편집 시간이 비용으로 직결되는 사용자.

- YouTube 편집자
- 인터뷰 / 팟캐스트 편집자
- 1인 제작자
- 영상 외주 편집자
- 소규모 프로덕션
- 콘텐츠 팀

## 장기 사용자 경험

### Expert Assist
전문가가 결정을 유지한다.

- 선택 영역 기반 명령
- 정확한 timecode / frame
- preview / approve
- conservative automation
- 기존 편집 보존

### Guided Edit
일반 사용자가 결과 옵션을 경험한다.

- Conservative
- Balanced
- Aggressive
- 장르 preset
- 여러 edit version preview

초기 제품은 Expert Assist에 우선한다.

## 핵심 가치

North Star Metric:

**Net Editing Time Saved**

```text
기존 예상 편집 시간
- AI 사용 시간
- AI 결과 검수 시간
- AI 오류 수정 시간
= 실제 절감 시간
```

AI가 빠르게 결과를 만들었다는 사실만으로 성공으로 보지 않는다.

## 핵심 품질 철학

- Zero-shot Quality Floor
- Style Bootstrap
- Confidence-gated Autonomy
- Shadow Learning
- Pause Intelligence
- Timeline Integrity

개인화는 낮은 품질을 구제하는 수단이 아니다.

```text
나쁜 첫 결과 → 학습 → 좋은 결과
```

가 아니라:

```text
쓸 만한 첫 결과 → 조용한 학습 → 사용자 스타일에 가까운 결과
```

이어야 한다.


## Preserve Editability / Native Editing Environment Preservation

Approved in TASK-004 user instruction: AI edits must retain the native Track/Layer/Object
structure so the user can continue individual editing. Preview/render output may flatten,
but must not replace editable project state or become the editable source of truth.
Track additions/removals/moves require explicit expected topology changes (INV-019).

## Preferred Effects Implementation Path (future product boundary only)

1. Editorial effects: prefer Edit Page / Resolve FX.
2. Motion graphics, tracking and simple compositing: consider Fusion first when feasible.
3. Fusion is preferred, not required.
4. Unrestricted full Fusion automation is not initial scope.
5. Future effect automation should prioritize editable, reversible, inspectable structures.
6. Complex specialist VFX: prioritize VFX Assist / Handoff over direct automation.
7. External VFX integrations are later priorities, considered only when they preserve the
   native editing environment. These notes authorize no TASK-004 effect implementation.
