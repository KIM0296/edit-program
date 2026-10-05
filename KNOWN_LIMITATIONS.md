# Known Limitations

현재는 구현 전 단계이므로 아래 항목을 지원한다고 가정하지 않는다.

## Resolve API 미검증 영역

- persistent TimelineItem identity
- precise ripple behavior via scripting
- arbitrary trim behavior
- nested timeline write
- multicam internal write
- Fusion dependency preservation
- full effect/keyframe serialization
- transaction-level native undo grouping

## 초기 Safety Core에서 REVIEW-only 가능성이 높은 영역

- Variable Frame Rate
- complex speed ramp
- nested multicam
- compound clip internal edits
- offline media
- render-in-place replacement
- complex Fusion composition

## 원칙

미지원 상태를 숨기지 않는다.

```text
unknown → REVIEW
unsupported → explicit limitation
unsafe → reject
```
