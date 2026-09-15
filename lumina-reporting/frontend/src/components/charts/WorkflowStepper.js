import React from 'react';

const STEPS = [
  { key: 'draft', label: 'Draft' },
  { key: 'review', label: 'Review' },
  { key: 'compliance', label: 'Compliance' },
  { key: 'approved', label: 'Approved' },
  { key: 'distributed', label: 'Distributed' },
];

const computeStepStates = (status, complianceRequired) => {
  const order = complianceRequired
    ? STEPS.map(step => step.key)
    : STEPS.filter(step => step.key !== 'compliance').map(step => step.key);
  const currentIndex = order.indexOf(status);

  return STEPS.map((step) => {
    if (step.key === 'compliance' && !complianceRequired) return { ...step, state: 'skipped' };
    const index = order.indexOf(step.key);
    if (index === -1 || currentIndex === -1) return { ...step, state: 'upcoming' };
    if (index < currentIndex) return { ...step, state: 'done' };
    if (index === currentIndex) return { ...step, state: 'current' };
    return { ...step, state: 'upcoming' };
  });
};

// Draft -> Review -> Compliance -> Approved -> Distributed. Compliance renders
// visibly "skipped" (dashed, muted) for report types that bypass it, so the
// business rule is legible instead of just silently absent.
const WorkflowStepper = ({ status, complianceRequired }) => {
  const steps = computeStepStates(status, complianceRequired);

  return (
    <div className="workflow-stepper" role="list" aria-label={`Workflow progress: currently ${status}`}>
      {steps.map((step, index) => (
        <React.Fragment key={step.key}>
          <div className={`stepper-step is-${step.state}`} role="listitem">
            <span
              className="stepper-node"
              style={(step.state === 'done' || step.state === 'current') ? { '--stepper-color': `var(--c-${step.key})` } : undefined}
            >
              {step.state === 'done' && '✓'}
              {step.state === 'skipped' && '–'}
            </span>
            <span className="stepper-label">{step.label}</span>
            {step.state === 'skipped' && <span className="stepper-sublabel">Not required for this type</span>}
          </div>
          {index < steps.length - 1 && (
            <div className={`stepper-connector ${
              (step.state === 'skipped' || steps[index + 1].state === 'skipped') ? 'is-skipped' : (step.state === 'done' ? 'is-done' : '')
            }`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
};

export default WorkflowStepper;
