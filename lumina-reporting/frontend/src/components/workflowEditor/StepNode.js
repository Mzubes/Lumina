import React from 'react';
import { Handle, Position } from '@xyflow/react';

const TYPE_LABEL = { start: 'Start', step: 'Step', parallel_gateway: 'Split', join: 'Join', terminal: 'End' };

// Purely presentational -- editing happens in WorkflowCanvas's inspector
// panel once a node is selected, not inline here, so a controlled input
// living inside a draggable/selectable React Flow node never fights focus
// with the canvas's own drag/select handling.
const StepNode = ({ data, selected }) => (
  <div className={`workflow-node workflow-node-${data.nodeType} ${selected ? 'is-selected' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <div className="workflow-node-top">
      <span className="workflow-node-badge">{TYPE_LABEL[data.nodeType] || data.nodeType}</span>
      {data.groupName && (
        <span className={`workflow-group-swatch swatch-${data.groupColor || 'cat-other'}`} title={data.groupName} />
      )}
    </div>
    <div className="workflow-node-name">{data.name}</div>
    {data.isDistributionGate && <div className="workflow-node-gate-badge">Distribution gate</div>}
    <Handle type="source" position={Position.Right} />
  </div>
);

export default StepNode;
