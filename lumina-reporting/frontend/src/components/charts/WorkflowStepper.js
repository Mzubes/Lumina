import React from 'react';

const LEGACY_STEPS = [
  { key: 'draft', label: 'Draft' },
  { key: 'review', label: 'Review' },
  { key: 'compliance', label: 'Compliance' },
  { key: 'approved', label: 'Approved' },
  { key: 'distributed', label: 'Distributed' },
];

const computeLegacyStepStates = (status, complianceRequired) => {
  const order = complianceRequired
    ? LEGACY_STEPS.map(step => step.key)
    : LEGACY_STEPS.filter(step => step.key !== 'compliance').map(step => step.key);
  const currentIndex = order.indexOf(status);

  return LEGACY_STEPS.map((step) => {
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
// business rule is legible instead of just silently absent. Only used for a
// legacy (non-diagram) report -- see WorkflowStepper below.
const LegacyWorkflowStepper = ({ status, complianceRequired }) => {
  const steps = computeLegacyStepStates(status, complianceRequired);

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

// 'start' and 'parallel_gateway' nodes auto-complete the instant they're
// entered and immediately fan out (see workflow_engine.py's
// _STRUCTURAL_NODE_TYPES) -- they're never something a user waits on or
// acts on, so they're never worth a slot in this display.
const isStructural = (node) => node.type === 'start' || node.type === 'parallel_gateway';

// Groups the diagram's real (non-structural) nodes into left-to-right
// columns using the x/y layout the diagram was actually authored or
// auto-arranged with (WorkflowCanvas.js / autoLayout.js) -- nodes sharing a
// column's x are parallel siblings, stacked top to bottom by y. Reusing the
// diagram's own coordinates avoids re-deriving a layout algorithm here, and
// keeps this stepper visually consistent with what the diagram looks like
// in the editor.
const buildColumns = (nodes) => {
  const displayNodes = nodes.filter(node => !isStructural(node));
  const columnXs = [...new Set(displayNodes.map(node => node.position?.x ?? 0))].sort((a, b) => a - b);
  return columnXs.map(x => displayNodes
    .filter(node => (node.position?.x ?? 0) === x)
    .sort((a, b) => (a.position?.y ?? 0) - (b.position?.y ?? 0)));
};

const CATEGORICAL_COLORS = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)', 'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)'];

// Deterministic hash-to-categorical-color, keyed by node id (stable across
// renders) -- same idiom used for firm-custom names elsewhere (ReportsTable,
// dashboardWidgets), since a diagram's step names/colors aren't otherwise
// known ahead of time.
const colorForNode = (nodeId) => {
  let hash = 0;
  for (let i = 0; i < nodeId.length; i += 1) hash = (hash * 31 + nodeId.charCodeAt(i)) >>> 0;
  return CATEGORICAL_COLORS[hash % CATEGORICAL_COLORS.length];
};

// `steps` is the report's full ReportStepInstance history (GET
// .../reports/:id/steps), already ordered oldest-first -- a node can appear
// more than once (a "request changes" loop back to Draft, say), so the last
// matching row is this node's current state.
const stateForNode = (node, steps) => {
  const visits = steps.filter(step => step.node_id === node.id);
  if (visits.length === 0) return 'upcoming';
  const latest = visits[visits.length - 1];
  if (latest.state === 'skipped') return 'skipped';
  if (latest.state === 'done') return 'done';
  // A terminal node that's 'active' IS the report's final resting state
  // (nothing ever completes it) -- render that as reached/done, not as a
  // step still waiting on someone.
  return node.is_terminal ? 'done' : 'current';
};

// Renders a report's actual pinned diagram -- parallel branches (multiple
// nodes sharing a column) appear as a bracketed sub-row within that column,
// reflecting workflow_engine.py's AND-join semantics (every branch must
// reach 'done' before the join fires) instead of the fixed 5-step linear
// display LegacyWorkflowStepper uses for reports with no diagram.
const DiagramWorkflowStepper = ({ diagram, steps }) => {
  const columns = buildColumns(diagram.nodes);

  return (
    <div className="workflow-stepper" role="list" aria-label="Workflow progress">
      {columns.map((column, columnIndex) => (
        <React.Fragment key={column.map(node => node.id).join('+')}>
          <div className={`stepper-column ${column.length > 1 ? 'is-parallel' : ''}`}>
            {column.map((node) => {
              const state = stateForNode(node, steps);
              return (
                <div className={`stepper-step is-${state}`} role="listitem" key={node.id}>
                  <span
                    className="stepper-node"
                    style={(state === 'done' || state === 'current') ? { '--stepper-color': colorForNode(node.id) } : undefined}
                  >
                    {state === 'done' && '✓'}
                    {state === 'skipped' && '–'}
                  </span>
                  <span className="stepper-label">{node.name}</span>
                </div>
              );
            })}
          </div>
          {columnIndex < columns.length - 1 && <div className="stepper-connector" />}
        </React.Fragment>
      ))}
    </div>
  );
};

// diagram/steps are only passed for a diagram-backed report (see
// ReportDetail.js) -- a legacy report falls back to the fixed linear
// display, unchanged from before this diagram-aware rendering existed.
const WorkflowStepper = ({ status, complianceRequired, diagram, steps }) => {
  if (diagram) return <DiagramWorkflowStepper diagram={diagram} steps={steps || []} />;
  return <LegacyWorkflowStepper status={status} complianceRequired={complianceRequired} />;
};

export default WorkflowStepper;
