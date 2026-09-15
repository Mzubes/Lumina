import React, { useEffect, useState } from 'react';
import { apiFetch } from '../api';

const ROLE_LABEL = { compliance: 'Compliance', admin: 'Admin', editor: 'Editor' };

const formatDate = (value) => (value ? new Date(value).toLocaleString() : '—');

const ReviewChecklistPanel = ({ reportId, role }) => {
  const [checklist, setChecklist] = useState([]);
  const [error, setError] = useState('');

  const loadChecklist = () => {
    apiFetch(`/api/reports/${reportId}/review-checklist`).then(setChecklist).catch(() => {});
  };

  useEffect(loadChecklist, [reportId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (checklist.length === 0) return null;

  const canReview = (item) => role === 'admin' || role === item.review_role;

  const handleMarkReviewed = async (item) => {
    setError('');
    try {
      const updated = await apiFetch(`/api/reports/${reportId}/components/${item.component_id}/review`, { method: 'POST' });
      setChecklist(current => current.map(row => (
        row.component_id === item.component_id
          ? { ...row, reviewed: true, reviewed_by: updated.reviewed_by, reviewed_at: updated.reviewed_at }
          : row
      )));
    } catch (requestError) { setError(requestError.message); }
  };

  const handleUndo = async (item) => {
    setError('');
    try {
      await apiFetch(`/api/reports/${reportId}/components/${item.component_id}/review`, { method: 'DELETE' });
      setChecklist(current => current.map(row => (
        row.component_id === item.component_id
          ? { ...row, reviewed: false, reviewed_by: null, reviewed_at: null }
          : row
      )));
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <section className="panel">
      <div className="panel-header"><h2>Review checklist</h2></div>
      <p className="panel-subtitle">
        Component-level sign-off — an audit trail alongside the report's own workflow, not a second gate on it.
      </p>

      {error && <p className="form-message">{error}</p>}

      <ul className="review-checklist-list">
        {checklist.map(item => (
          <li className="review-checklist-item" key={item.component_id}>
            <div className="review-checklist-main">
              <span className="review-checklist-title">{item.title}</span>
              <span className="review-checklist-role">{ROLE_LABEL[item.review_role] || item.review_role}</span>
            </div>
            <div className="review-checklist-status">
              {item.reviewed ? (
                <span className="status-badge status-approved">
                  Reviewed {formatDate(item.reviewed_at)}
                </span>
              ) : (
                <span className="status-badge status-draft">Not reviewed</span>
              )}
              {canReview(item) && (
                item.reviewed
                  ? <button type="button" onClick={() => handleUndo(item)}>Undo</button>
                  : <button type="button" onClick={() => handleMarkReviewed(item)}>Mark reviewed</button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
};

export default ReviewChecklistPanel;
