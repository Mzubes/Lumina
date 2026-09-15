import React from 'react';

const DocumentBlock = ({ component }) => {
  if (component.type === 'text_block') {
    return (
      <div className="document-block">
        <h3 className="document-block-title">{component.title}</h3>
        <p>{component.text}</p>
      </div>
    );
  }
  if (component.type === 'people_grid') {
    return (
      <div className="document-block">
        <h3 className="document-block-title">{component.title}</h3>
        <div className="people-grid-preview">
          {component.people.map((person, index) => (
            <div className="people-grid-preview-row" key={index}>
              <strong>{person.name}</strong>
              <span>{[person.title, person.detail].filter(Boolean).join(' · ')}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="document-block">
      <h3 className="document-block-title">{component.title}</h3>
      <table className="data-table">
        <thead><tr>{component.columns.map(col => <th key={col}>{col}</th>)}</tr></thead>
        <tbody>
          {component.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className={cellIndex === 0 ? '' : 'num'}>
                  {typeof cell === 'number' ? cell.toLocaleString(undefined, { maximumFractionDigits: 2 }) : (cell || '—')}
                </td>
              ))}
            </tr>
          ))}
          {component.rows.length === 0 && (
            <tr><td colSpan={component.columns.length} className="reports-table-empty">No data for this section yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default DocumentBlock;
