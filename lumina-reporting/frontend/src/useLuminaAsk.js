import { useCallback, useState } from 'react';
import { apiFetch, isDemoMode } from './api';

export const demoReply = "I'm running on demo data right now, so I can't call out to Claude -- but " +
  "once ANTHROPIC_API_KEY is set, I'll answer grounded in your firm's real book of business, " +
  "report statuses, and templates, right from wherever you're working in Lumina.";

// The request half of the assistant, shared by the corner panel and the
// Audit Trail's inline console. Both send to the same endpoint with the same
// demo fallback and the same error handling; only their chrome differs, so
// only their chrome is written twice.
//
// Read-only by construction: the only call it makes is POST /api/ai/ask,
// which the backend answers from a fact snapshot and never writes through.
export default function useLuminaAsk() {
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  // Server-computed description of the snapshot the last answer was grounded
  // in. Computed there, not here, so the chips and the answer can't describe
  // different data.
  const [contextSummary, setContextSummary] = useState(null);

  const ask = useCallback(async (text, { page, reportId = null, clientId = null } = {}) => {
    const message = (text || '').trim();
    if (!message || sending) return;

    setMessages(current => [...current, { role: 'user', text: message }]);
    setError('');
    setSending(true);
    try {
      if (isDemoMode) {
        await new Promise(resolve => setTimeout(resolve, 400));
        setMessages(current => [...current, { role: 'assistant', text: demoReply }]);
      } else {
        const result = await apiFetch('/api/ai/ask', {
          method: 'POST',
          body: JSON.stringify({ message, page, reportId, clientId }),
        });
        setMessages(current => [...current, {
          role: 'assistant', text: result.reply, configured: result.configured,
          // Additive keys -- absent on an older backend, which renders as a
          // plain reply rather than an error.
          actions: result.actions || [], followUps: result.followUps || [],
        }]);
        if (result.contextSummary) setContextSummary(result.contextSummary);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSending(false);
    }
  }, [sending]);

  const reset = useCallback(() => { setMessages([]); setError(''); }, []);

  return { messages, sending, error, contextSummary, ask, reset };
}
