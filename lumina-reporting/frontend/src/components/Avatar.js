import React from 'react';
import { colorForLabel } from './dashboardWidgets';

// Initials from a client or person name. Two words -> two letters, one word
// -> one; a name that's only punctuation or empty falls back to '?' rather
// than rendering a blank circle that reads as a loading state.
export const initialsFor = (name) => {
  const words = (name || '').trim().split(/\s+/).filter(Boolean);
  const letters = words.slice(0, 2).map(word => word[0]).join('');
  return letters.toUpperCase() || '?';
};

const Avatar = ({ name }) => (
  <span className="avatar-initials" style={{ background: colorForLabel(name || '') }} aria-hidden="true">
    {initialsFor(name)}
  </span>
);

export default Avatar;
