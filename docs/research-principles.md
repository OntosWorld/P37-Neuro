# Research Principles

## Capability claims require holdouts

A system is not cross-embodiment if evaluation uses only body variants seen during training. Report morphology holdouts explicitly.

## Do not optimize for demos

Demos are useful communication artifacts, not the benchmark. Maintain fixed evaluation suites with failure taxonomy and intervention counts.

## Separate adaptation from retraining

When measuring in-context adaptation, model weights must remain unchanged during the evaluation window.

## Track negative results

Record architecture, dataset and control approaches that fail. Repeating an expensive negative result is a process failure.

## Reproduce before scaling

Each major scale increase should be preceded by a smaller controlled run that validates data, loss, evaluation and checkpoint recovery.

## Physical truth wins

When simulation and real hardware disagree, treat the discrepancy as a research problem rather than tuning the benchmark to simulation.
