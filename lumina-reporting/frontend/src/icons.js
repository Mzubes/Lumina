import React from 'react';

const base = {
  width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round',
};

export const IconDashboard = () => (
  <svg {...base}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></svg>
);

export const IconDatabase = () => (
  <svg {...base}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" /><path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" /></svg>
);

export const IconPlug = () => (
  <svg {...base}><path d="M9 2v4M15 2v4" /><rect x="6" y="6" width="12" height="7" rx="2" /><path d="M12 13v3a4 4 0 0 1-4 4H6" /><circle cx="6" cy="20" r="1.6" /></svg>
);

export const IconLayout = () => (
  <svg {...base}><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 9v12" /></svg>
);

export const IconDocument = () => (
  <svg {...base}><path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z" /><path d="M14 2v5h5" /><path d="M8 13h8M8 17h5" /></svg>
);

export const IconCheckCircle = () => (
  <svg {...base}><circle cx="12" cy="12" r="9" /><path d="m8.5 12.5 2.4 2.4L16 10" /></svg>
);

export const IconUsers = () => (
  <svg {...base}><circle cx="9" cy="8" r="3.2" /><path d="M2.5 20c0-3.3 2.9-6 6.5-6s6.5 2.7 6.5 6" /><path d="M16.5 4.3a3.2 3.2 0 0 1 0 6.2" /><path d="M21.5 20c0-2.8-2-5.1-4.8-5.8" /></svg>
);

export const IconLogIn = () => (
  <svg {...base}><path d="M14 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><path d="M10 17l5-5-5-5" /><path d="M15 12H3" /></svg>
);

export const IconLogOut = () => (
  <svg {...base}><path d="M10 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h4" /><path d="M15 17l5-5-5-5" /><path d="M20 12H8" /></svg>
);

export const IconBadge = () => (
  <svg {...base}><circle cx="12" cy="9" r="6" /><path d="m8.5 14-1.8 7 5.3-3 5.3 3-1.8-7" /></svg>
);

export const IconPresentation = () => (
  <svg {...base}><rect x="2.5" y="4" width="19" height="12" rx="1.5" /><path d="M8 20h8M12 16v4" /><path d="M7 12l3-3 2.5 2.5L17 7" /></svg>
);

export const IconShield = () => (
  <svg {...base}><path d="M12 2.5 4.5 5.5v6c0 5 3.2 8.4 7.5 10 4.3-1.6 7.5-5 7.5-10v-6Z" /><path d="m8.5 12 2.4 2.4L16 9" /></svg>
);
