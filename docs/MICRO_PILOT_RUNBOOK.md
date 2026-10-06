# Micro-Pilot Runbook v1

Status: **Operational baseline for the 25-case Pause Intelligence Micro-Pilot**

## Purpose

Validate the annotation/evaluation process before scaling to the 200-260 case Main Pilot.
This runbook does not establish numerical release gates or production accuracy.

## Fixed inputs

Use the approved:
- Benchmark Sampling Manifest v1
- Annotation Guide v1
- Micro-Pilot Annotation Sheet v1
- ADR-018 Pause/Dialogue Editing v1
- ADR-019 Evaluation Data Contract v1

Micro-Pilot size:
- 25 total cases
- 15 Naturalistic
- 10 Challenge
- 5 spoken-content source archetypes
- 2 independent annotators per case

## Run sequence

1. **Source lock**
   - Select the 5 source materials.
   - Record opaque Source IDs.
   - Do not use final AI results to choose sources.

2. **Sampling lock**
   - Freeze Naturalistic ranges before pause indexing.
   - Index eligible pauses.
   - Select 3 Naturalistic + 2 Challenge cases per source.
   - Freeze the 25 Case IDs and sampling manifest.

3. **Blind annotation**
   - Annotator A and B work independently.
   - Show the common benchmark brief and Annotation Guide v1.
   - Do not reveal AI proposals, the other annotator's answers, or adjudicated references.
   - Record Action, Confidence, Difficulty, Reasons, TIGHTEN range, context expansion and optional decision time.

4. **Annotation freeze**
   - Validate all required fields.
   - Validate every TIGHTEN range.
   - Freeze both annotation sets under an annotation-batch version.
   - Do not edit the frozen batch after AI results are revealed.

5. **Agreement review**
   - Compute exact action agreement.
   - Flag severe disagreement.
   - Check TIGHTEN range overlap.
   - Produce the adjudication queue.

6. **Adjudication**
   - Resolve required cases using source context.
   - Allow AMBIGUOUS references.
   - Do not force KEEP/TIGHTEN/REMOVE when multiple editorial judgments remain reasonably valid.
   - Freeze Reference Judgment v0/v1 before revealing AI outputs.

7. **AI reveal**
   - Generate or import TASK-007 deterministic baseline proposals only after reference freeze.
   - Bind one explicit proposal to each evaluated case.
   - Never rewrite human references to match AI output.

8. **Evaluation**
   - Use TASK-008 pure metrics.
   - Report at minimum:
     - Critical False Removal
     - action confusion
     - TIGHTEN In-Range
     - Review Load
     - annotation disagreement/adjudication rate
   - Keep Naturalistic and Challenge results separately identifiable.

9. **Protocol review**
   - Review repeated annotation difficulties, missing reason categories, context-expansion frequency,
     severe disagreement patterns and TIGHTEN-range usability.
   - Record protocol issues before changing the guide.

10. **Go / Revise decision**
    - Proceed to Main Pilot only if the annotation language is sufficiently consistent,
      severe disagreements are explainable, TIGHTEN ranges are usable, and the workload can scale.
    - Otherwise revise the protocol to v1.1 and re-annotate affected Micro-Pilot cases.

## Stop conditions

Pause the Pilot and revise the protocol before scaling if any of the following repeats materially:
- annotators interpret KEEP/TIGHTEN/REMOVE/REVIEW differently
- KEEP vs REMOVE or REVIEW vs REMOVE disagreement is common and not explainable
- TIGHTEN ranges cannot be assigned consistently
- default context is frequently insufficient without a clear expansion rule
- OTHER reasons recur because the reason taxonomy is missing a common concept
- annotation workload is too high to scale to 200-260 cases
- sampling rules allow subjective cherry-picking

## Data rules

- Sampling data, annotations, references and AI proposals remain separate records.
- Benchmark reference is never overwritten by product feedback or AI output.
- Missing timing/data is missing, not zero.
- Use opaque source/annotator references; raw media/user identity is not required in the evaluation schema.
- Micro-Pilot evidence does not imply training consent.

## Completion checklist

- [ ] 5 sources locked
- [ ] 25 cases frozen
- [ ] 50 independent annotations complete
- [ ] all TIGHTEN ranges valid
- [ ] agreement report complete
- [ ] adjudication complete
- [ ] Reference Judgment version frozen
- [ ] AI proposals revealed only after freeze
- [ ] TASK-008 evaluation generated
- [ ] protocol issue log completed
- [ ] Go / Revise decision recorded

## Success definition

The Micro-Pilot succeeds if it proves that human editorial judgments, disagreements and AI evaluation
can be recorded reproducibly enough to support a larger pilot. High AI accuracy is not required for
Micro-Pilot success.
