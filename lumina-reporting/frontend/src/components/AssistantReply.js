import React from 'react';
import { Link } from 'react-router-dom';

// A deliberately tiny Markdown subset: **bold**, "- " bullets, and blank-line
// paragraphs. That's exactly what the system prompt asks Claude for, and
// nothing more -- no links, no images, no raw HTML. Everything is rendered as
// React elements from parsed text, so model output is never injected as
// markup and there's no sanitizer to get wrong.
const BOLD = /\*\*(.+?)\*\*/g;

const withBold = (text) => {
  const parts = [];
  let cursor = 0;
  let match;
  BOLD.lastIndex = 0;
  while ((match = BOLD.exec(text)) !== null) {
    if (match.index > cursor) parts.push(text.slice(cursor, match.index));
    parts.push(<strong key={`${match.index}-b`}>{match[1]}</strong>);
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts.length ? parts : text;
};

export const renderMarkdown = (text) => {
  const blocks = [];
  let bullets = [];

  const flushBullets = () => {
    if (bullets.length === 0) return;
    blocks.push(<ul key={`ul-${blocks.length}`}>{bullets.map((item, i) => <li key={i}>{withBold(item)}</li>)}</ul>);
    bullets = [];
  };

  (text || '').split('\n').forEach((line) => {
    const trimmed = line.trim();
    const bullet = trimmed.match(/^[-*]\s+(.*)$/);
    if (bullet) { bullets.push(bullet[1]); return; }
    flushBullets();
    if (trimmed) blocks.push(<p key={`p-${blocks.length}`}>{withBold(trimmed)}</p>);
  });
  flushBullets();
  return blocks;
};

// An action is always a <Link> to an in-app path, never a button that calls
// an endpoint. The backend allow-lists every `to` before it gets here
// (see backend/ai_actions.py); this side simply never offers any other shape,
// so there is no code path from an assistant reply to a write.
const AssistantReply = ({ message, onFollowUp }) => (
  <div className="lumina-ai-bubble lumina-ai-bubble-assistant">
    <div className="assistant-reply-body">{renderMarkdown(message.text)}</div>

    {message.actions?.length > 0 && (
      <div className="assistant-actions">
        {message.actions.map(action => (
          <Link key={`${action.to}-${action.label}`} className="assistant-action" to={action.to}>
            {action.label} →
          </Link>
        ))}
      </div>
    )}

    {message.followUps?.length > 0 && (
      <div className="assistant-followups">
        <span className="assistant-followups-label">You might also ask</span>
        {message.followUps.map(question => (
          <button key={question} type="button" className="assistant-followup" onClick={() => onFollowUp?.(question)}>
            {question}
          </button>
        ))}
      </div>
    )}
  </div>
);

export default AssistantReply;
