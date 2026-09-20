import React, { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { apiFetch, isDemoMode } from '../api';
import { LUMINA_ASK_EVENT } from '../luminaAskBus';
import { IconSparkle } from '../icons';

// Page label + (when on a report) the report id the assistant should ground
// its answer in -- kept in one place so every route this shell renders gets
// a sensible label without each page having to pass one down.
const pageLabelFromPath = (pathname) => {
  const reportMatch = pathname.match(/^\/reports\/(\d+)$/);
  if (reportMatch) return { label: 'Report Detail', reportId: Number(reportMatch[1]) };
  const labels = {
    '/': 'Production Hub', '/data-hub': 'Data Hub', '/data-sources': 'Data Sources',
    '/templates': 'Templates', '/reports': 'Reports', '/queue': 'My Queue',
    '/marketing': 'Fact Sheets & Marketing', '/pitch-books': 'Pitch Books & Meeting Packs',
    '/clients': 'Clients & Contacts', '/disclosures': 'Disclosures', '/activity': 'Activity Log',
    '/users': 'Users & Roles', '/workflow-groups': 'Workflow Groups',
    '/client-portal': 'Client Portal', '/internal-portal': 'Internal Portal',
  };
  return { label: labels[pathname] || pathname, reportId: null };
};

const demoReply = "I'm running on demo data right now, so I can't call out to Claude -- but " +
  "once ANTHROPIC_API_KEY is set, I'll answer grounded in your firm's real book of business, " +
  "report statuses, and templates, right from wherever you're working in Lumina.";

const LuminaAssistant = () => {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  // Ids another page asked the assistant to ground its answer in. Cleared
  // when the panel closes, so a question typed later isn't silently
  // answered about a client the user has since navigated away from.
  const [seededContext, setSeededContext] = useState(null);
  const scrollRef = useRef(null);

  // A page can open the panel with a question pre-filled -- see luminaAskBus.
  // It never sends: the draft is populated and focus handed over, and a
  // human still presses Send.
  useEffect(() => {
    const handleAsk = (event) => {
      const { question, context } = event.detail || {};
      setOpen(true);
      setSeededContext(context || null);
      if (question) setDraft(question);
    };
    window.addEventListener(LUMINA_ASK_EVENT, handleAsk);
    return () => window.removeEventListener(LUMINA_ASK_EVENT, handleAsk);
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, open]);

  const send = async (event) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    const { label, reportId } = pageLabelFromPath(location.pathname);

    setMessages((current) => [...current, { role: 'user', text }]);
    setDraft('');
    setError('');
    setSending(true);

    try {
      if (isDemoMode) {
        await new Promise((resolve) => setTimeout(resolve, 400));
        setMessages((current) => [...current, { role: 'assistant', text: demoReply }]);
      } else {
        const result = await apiFetch('/api/ai/ask', {
          method: 'POST',
          body: JSON.stringify({
            message: text, page: label,
            // A page-seeded id wins over the one inferred from the URL: the
            // user explicitly asked about that record.
            reportId: seededContext?.reportId ?? reportId,
            clientId: seededContext?.clientId ?? null,
          }),
        });
        setMessages((current) => [...current, { role: 'assistant', text: result.reply, configured: result.configured }]);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="lumina-ai">
      {open && (
        <div className="lumina-ai-panel panel">
          <div className="lumina-ai-panel-header">
            <div>
              <div className="lumina-ai-panel-title"><IconSparkle /><span>Lumina AI</span></div>
              <div className="lumina-ai-panel-subtitle">Grounded in your firm's real data. Always human-reviewed before anything is sent.</div>
            </div>
            <button
              type="button" className="lumina-ai-close"
              onClick={() => { setOpen(false); setSeededContext(null); }}
              aria-label="Close Lumina AI"
            >×</button>
          </div>
          <div className="lumina-ai-messages" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="lumina-ai-empty">
                Ask about your book of business, a report's status, or for a starting point on a
                template or summary. I can't approve, edit, or send anything myself.
              </div>
            )}
            {messages.map((message, index) => (
              <div key={index} className={`lumina-ai-bubble lumina-ai-bubble-${message.role}`}>
                {message.text}
              </div>
            ))}
            {sending && <div className="lumina-ai-bubble lumina-ai-bubble-assistant lumina-ai-thinking">Thinking…</div>}
          </div>
          {error && <p className="form-message">{error}</p>}
          <form className="lumina-ai-input-row" onSubmit={send}>
            <input
              type="text" placeholder="Ask Lumina AI…" value={draft}
              onChange={(event) => setDraft(event.target.value)} disabled={sending}
            />
            <button type="submit" className="btn btn-primary" disabled={sending || !draft.trim()}>Send</button>
          </form>
        </div>
      )}
      <button type="button" className="lumina-ai-fab" onClick={() => setOpen((current) => !current)} aria-label="Open Lumina AI">
        <IconSparkle />
      </button>
    </div>
  );
};

export default LuminaAssistant;
