import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { apiBaseUrl, isDemoMode, publicFetch } from '../api';
import DocumentBlock from '../components/DocumentBlock';

const EXPORT_FORMATS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'pptx', label: 'PowerPoint' },
  { value: 'xlsx', label: 'Excel' },
];

const PublicReport = () => {
  const { token } = useParams();
  const [content, setContent] = useState(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (isDemoMode) { setNotFound(true); return; }
    publicFetch(`/api/public/reports/${token}`).then(setContent).catch(() => setNotFound(true));
  }, [token]);

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
          {content.header_config && content.header_config.title && (
            <div className="public-report-header">
              <span className="eyebrow">{content.header_config.subtitle}</span>
              <h1>{content.header_config.title}</h1>
            </div>
          )}
          {!content.header_config?.title && <h1>{content.report_title}</h1>}

          {content.legacy_pdf_only ? (
            <p className="panel-subtitle">This report is only available as a PDF.</p>
          ) : (
            <>
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
              <div className="document-preview">
                {content.components.map((component, index) => <DocumentBlock component={component} key={index} />)}
              </div>
            </>
          )}

          {content.footer_config && content.footer_config.text && (
            <p className="public-report-footer">{content.footer_config.text}</p>
          )}
        </div>
      )}
    </div>
  );
};

export default PublicReport;
