# P37 Neuro Test Report Template

## Result classification

Choose exactly one:

- software validation
- synthetic smoke validation
- simulation capability evidence
- hardware-in-the-loop evidence
- physical capability evidence
- production/fleet evidence

## Test identity

- Test ID:
- Tester:
- Date:
- P37 commit SHA:
- Checkpoint/artifact ID:
- Dataset/version:
- Test level:
- P37 stage:

## Question

What capability was tested?

## Frozen protocol

Link to or reproduce the pre-run test plan.

## Train/evaluation split

### Training

- embodiments:
- tasks:
- episodes:

### Held out

- embodiments:
- tasks:
- episodes:
- demonstrations available during evaluation:
- evaluation gradient updates:

## Environment

- simulator/hardware:
- version:
- robot description:
- seed(s):
- control rate:
- randomization:
- perturbations:

## Results

### Primary metric

- result:
- required threshold:
- pass/fail:

### Secondary metrics

| Metric | Result |
| --- | --- |
| success rate | |
| progress | |
| interventions | |
| recovery rate | |
| safety rejections | |
| p95 latency | |

## Per-embodiment results

Do not report only an aggregate.

| Embodiment | Task set | Episodes | Success | Interventions | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| | | | | | |

## Ablation

- comparison:
- full result:
- ablated result:
- interpretation:

## Failures

List representative failure modes and episode IDs.

## Evidence

- metrics:
- logs:
- checkpoint:
- videos:
- simulator configuration:
- artifact digest:

## Conclusion

State only what the evidence supports.

## Next action

What should change before the next test?
