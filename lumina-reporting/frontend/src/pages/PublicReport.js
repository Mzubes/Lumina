import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { apiBaseUrl, isDemoMode, publicFetch, publicFetchBlobUrl } from '../api';

const EXPORT_FORMATS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'pptx', label: 'PowerPoint' },
  { value: 'xlsx', label: 'Excel' },
];

const PublicReport = () => {
  const { token } = useParams();
  const [content, setContent] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (isDemoMode) { setNotFound(true); return; }
    publicFetch(`/api/public/reports/${token}`).then(setContent).catch(() => setNotFound(true));
  }, [token]);

  useEffect(() => {
    if (isDemoMode || !content) return;
    let cancelled = false;
    let objectUrl = null;
    publicFetchBlobUrl(`/api/public/reports/${token}/export?format=pdf`).then(url => {
      if (cancelled) { window.URL.revokeObjectURL(url); return; }
      objectUrl = url;
      setPreviewUrl(url);
    }).catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) window.URL.revokeObjectURL(objectUrl);
    };
  }, [content, token]);

  return (
    <div className="public-report">
      <div className="public-report-brand">
        <div className="brand-mark">L</div>
        <span>Lumina</span>
      </div>

      {notFound && (
        <div className="public-report-body">
          <p className="form-message">
            This link is invalid, has been revoked, or is no longer active. Contact the sender for a current link.
          </p>
        </div>
      )}

      {!notFound && !content && <div className="public-report-body" />}

      {!notFound && content && (
        <div className="public-report-body">
          {content.header_config && content.header_config.title ? (
            <div className="public-report-header">
              <span className="eyebrow">{content.header_config.subtitle}</span>
              <h1>{content.header_config.title}</h1>
            </div>
          ) : <h1>{content.report_title}</h1>}

          <div className="public-report-export">
            {EXPORT_FORMATS.map(({ value, label }) => (
              <a
                key={value}
                href={`${apiBaseUrl}/api/public/reports/${token}/export?format=${value}`}
                target="_blank" rel="noreferrer"
              >
                Download {label}
              </a>
            ))}
          </div>

          {previewUrl
            ? <iframe src={previewUrl} title="Report preview" className="document-preview-frame" />
            : <p className="panel-subtitle">Loading preview…</p>}

          {content.footer_config && content.footer_config.text && (
            <p className="public-report-footer">{content.footer_config.text}</p>
          )}
        </div>
      )}
    </div>
  );
};

export default PublicReport;
