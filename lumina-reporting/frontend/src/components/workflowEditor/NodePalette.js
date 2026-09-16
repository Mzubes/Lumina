import React from 'react';

const PALETTE = [
  { type: 'step', label: 'Step', hint: 'A single sign-off' },
  { type: 'parallel_gateway', label: 'Split (parallel)', hint: 'Fans out into simultaneous branches' },
  { type: 'join', label: 'Join', hint: 'Waits for every branch to finish (AND)' },
  { type: 'terminal', label: 'End', hint: 'A resting state, e.g. Distributed' },
];

const NodePalette = () => (
  <div className="component-library workflow-node-palette">
    <div className="library-category">
      <h4>Steps</h4>
      {PALETTE.map(item => (
        <div
          key={item.type}
          className="library-preset-card"
          draggable
          onDragStart={(event) => {
            event.dataTransfer.setData('application/lumina-workflow-node-type', item.type);
            event.dataTransfer.effectAllowed = 'move';
          }}
        >
          <div className="library-preset-card-body">
            <strong>{item.label}</strong>
            <span>{item.hint}</span>
          </div>
        </div>
      ))}
    </div>
    <p className="field-hint">
      Drag a step onto the canvas, then draw a connection from its right edge to the next step's left edge.
      Select a step or connection to name it and assign a workflow group.
    </p>
  </div>
);

export default NodePalette;
