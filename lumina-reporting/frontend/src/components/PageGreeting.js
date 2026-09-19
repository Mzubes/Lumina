import React from 'react';

// Derived from the real logged-in email's local-part (e.g. 'admin' from
// 'admin@lumina.test') rather than a fabricated display name -- there's no
// separate name field on User yet, and this reads naturally as a greeting
// without inventing data.
export const displayNameFromEmail = (email) => {
  const localPart = (email || '').split('@')[0];
  if (!localPart) return null;
  return localPart.charAt(0).toUpperCase() + localPart.slice(1);
};

export const greetingForHour = (hour) => {
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
};

// The small line that sits *above* a page's <h1> -- "Hi, Mikhail 👋 —
// Wednesday, September 16". Deliberately separate from the heading itself so
// the page still announces what it is; this only says who and when.
// `variant="hero"` is the larger, centred treatment the start screen uses.
const PageGreeting = ({ variant = 'line', className = '' }) => {
  const now = new Date();
  const displayName = displayNameFromEmail(window.localStorage.getItem('lumina_email'));
  const dateLabel = now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

  if (variant === 'hero') {
    return (
      <div className={`page-greeting page-greeting--hero ${className}`.trim()}>
        <h1>{greetingForHour(now.getHours())}{displayName ? `, ${displayName}` : ''}.</h1>
      </div>
    );
  }

  return (
    <div className={`page-greeting ${className}`.trim()}>
      {displayName ? `Hi, ${displayName} 👋` : 'Hi 👋'} <span className="page-greeting-date">— {dateLabel}</span>
    </div>
  );
};

export default PageGreeting;
