// A one-way channel from any page to the Lumina AI panel.
//
// The panel lives in AuthenticatedShell, a sibling of whatever route is
// rendered, so there's no parent to thread a callback through and no shared
// store in this app to put one in. A window event is the smallest thing that
// works without introducing either -- the page fires, the panel listens, and
// neither imports the other.
//
// `context` carries only ids the backend already accepts on /api/ai/ask
// (clientId, reportId). Nothing here sends a message on its own; it opens
// the panel with a question pre-filled, and a human still presses Send.
export const LUMINA_ASK_EVENT = 'lumina-ai-ask';

export const askLumina = (question, context = {}) => {
  window.dispatchEvent(new CustomEvent(LUMINA_ASK_EVENT, { detail: { question, context } }));
};
