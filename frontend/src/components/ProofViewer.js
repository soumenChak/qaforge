import React from 'react';

const STATUS_COLOR = code => (code >= 200 && code < 300 ? '#22c55e' : '#ef4444');
const PASS_FAIL = status => (status === 'PASS' ? '#22c55e' : '#ef4444');
const DQ_COLOR = v => (v >= 95 ? '#22c55e' : v >= 80 ? '#eab308' : '#ef4444');

const overlay = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
};
const modal = {
  background: '#fff', borderRadius: 8, maxWidth: 800, width: '90%',
  maxHeight: '80vh', overflowY: 'auto', position: 'relative', padding: 24,
  boxShadow: '0 8px 30px rgba(0,0,0,0.25)',
};
const closeBtn = {
  position: 'absolute', top: 8, right: 12, background: 'none', border: 'none',
  fontSize: 22, cursor: 'pointer', color: '#666', lineHeight: 1,
};
const badge = {
  display: 'inline-block', padding: '2px 8px', borderRadius: 4,
  background: '#e0e7ff', color: '#3730a3', fontSize: 12, fontWeight: 600, marginRight: 8,
};
const pre = {
  background: '#f3f4f6', padding: 12, borderRadius: 6, overflowX: 'auto',
  fontSize: 13, fontFamily: 'monospace', whiteSpace: 'pre-wrap', margin: '8px 0',
};
const label = { fontWeight: 600, fontSize: 13, color: '#555', marginTop: 12, display: 'block' };
const kvRow = { display: 'flex', gap: 8, padding: '2px 0', fontSize: 13 };

function ApiResponse({ content }) {
  const c = typeof content === 'string' ? JSON.parse(content) : content;
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontWeight: 700, fontFamily: 'monospace' }}>{c.method}</span>
        <span style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{c.url}</span>
        <span style={{ fontWeight: 700, color: STATUS_COLOR(c.status) }}>{c.status}</span>
      </div>
      {c.duration_ms != null && <span style={{ fontSize: 12, color: '#888' }}>{c.duration_ms}ms</span>}
      {c.headers && (
        <>
          <span style={label}>Headers</span>
          {Object.entries(c.headers).map(([k, v]) => (
            <div key={k} style={kvRow}><span style={{ fontWeight: 600 }}>{k}:</span><span>{v}</span></div>
          ))}
        </>
      )}
      <span style={label}>Body</span>
      <pre style={pre}>{typeof c.body === 'string' ? c.body : JSON.stringify(c.body, null, 2)}</pre>
    </>
  );
}

function Screenshot({ content, file_path }) {
  const c = typeof content === 'string' ? JSON.parse(content) : content;
  const src = c?.image_base64
    ? `data:image/png;base64,${c.image_base64}`
    : file_path || null;
  if (!src) return <p>No image available.</p>;
  return <img src={src} alt="screenshot" style={{ maxWidth: '100%', borderRadius: 4 }} />;
}

function TestOutput({ content }) {
  const c = typeof content === 'string' ? JSON.parse(content) : content;
  return (
    <>
      <span style={{ fontWeight: 700, color: c.exit_code === 0 ? '#22c55e' : '#ef4444' }}>
        Exit code: {c.exit_code}
      </span>
      {c.stdout && (<><span style={label}>stdout</span><pre style={pre}>{c.stdout}</pre></>)}
      {c.stderr && (
        <><span style={label}>stderr</span><pre style={{ ...pre, background: '#fef2f2', color: '#b91c1c' }}>{c.stderr}</pre></>
      )}
    </>
  );
}

function QueryResult({ content }) {
  const c = typeof content === 'string' ? JSON.parse(content) : content;
  return (
    <>
      <span style={label}>SQL</span>
      <pre style={pre}>{c.sql}</pre>
      {c.columns && c.rows && (
        <div style={{ overflowX: 'auto', margin: '8px 0' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>
            <thead>
              <tr>{c.columns.map(col => (
                <th key={col} style={{ border: '1px solid #ddd', padding: '6px 8px', background: '#f9fafb', textAlign: 'left' }}>{col}</th>
              ))}</tr>
            </thead>
            <tbody>
              {c.rows.map((row, i) => (
                <tr key={i}>{c.columns.map((col, j) => (
                  <td key={j} style={{ border: '1px solid #ddd', padding: '6px 8px' }}>{row[col] ?? row[j] ?? ''}</td>
                ))}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {c.row_count != null && <span style={{ fontSize: 12, color: '#888' }}>{c.row_count} row(s)</span>}
    </>
  );
}

function DataComparison({ content }) {
  const c = typeof content === 'string' ? JSON.parse(content) : content;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={kvRow}><span style={{ fontWeight: 600 }}>Source count:</span><span>{c.source_count}</span></div>
      <div style={kvRow}><span style={{ fontWeight: 600 }}>Target count:</span><span>{c.target_count}</span></div>
      <div style={kvRow}><span style={{ fontWeight: 600 }}>Diff:</span><span>{c.diff}</span></div>
      <span style={{ fontWeight: 700, color: PASS_FAIL(c.status) }}>{c.status}</span>
    </div>
  );
}

function DqScorecard({ content }) {
  const c = typeof content === 'string' ? JSON.parse(content) : content;
  const metrics = Object.entries(c).filter(([, v]) => typeof v === 'number');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {metrics.map(([k, v]) => (
        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 120, fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>{k}</span>
          <div style={{ flex: 1, background: '#e5e7eb', borderRadius: 4, height: 18, position: 'relative' }}>
            <div style={{ width: `${Math.min(v, 100)}%`, background: DQ_COLOR(v), height: '100%', borderRadius: 4 }} />
          </div>
          <span style={{ width: 45, textAlign: 'right', fontSize: 13, fontWeight: 600, color: DQ_COLOR(v) }}>{v}%</span>
        </div>
      ))}
    </div>
  );
}

function LogViewer({ content }) {
  const text = typeof content === 'string' ? content : content?.text || JSON.stringify(content, null, 2);
  return <pre style={{ ...pre, maxHeight: 400, overflowY: 'auto' }}>{text}</pre>;
}

function CodeDiff({ content }) {
  const text = typeof content === 'string' ? content : content?.diff || '';
  return (
    <pre style={{ ...pre, maxHeight: 400, overflowY: 'auto' }}>
      {text.split('\n').map((line, i) => {
        let color = 'inherit';
        let bg = 'transparent';
        if (line.startsWith('+')) { color = '#16a34a'; bg = '#f0fdf4'; }
        else if (line.startsWith('-')) { color = '#dc2626'; bg = '#fef2f2'; }
        return <div key={i} style={{ color, background: bg }}>{line}</div>;
      })}
    </pre>
  );
}

const RENDERERS = {
  api_response: ApiResponse,
  screenshot: Screenshot,
  test_output: TestOutput,
  query_result: QueryResult,
  data_comparison: DataComparison,
  dq_scorecard: DqScorecard,
  log: LogViewer,
  code_diff: CodeDiff,
};

export default function ProofViewer({ proof, onClose, visible }) {
  if (!visible || !proof) return null;

  const Renderer = RENDERERS[proof.proof_type] || LogViewer;

  return (
    <div style={overlay} onClick={onClose}>
      <div style={modal} onClick={e => e.stopPropagation()}>
        <button style={closeBtn} onClick={onClose} aria-label="Close">&times;</button>
        <div style={{ marginBottom: 16 }}>
          <span style={badge}>{proof.proof_type}</span>
          <span style={{ fontSize: 16, fontWeight: 600 }}>{proof.title || 'Proof Artifact'}</span>
          {proof.created_at && (
            <span style={{ fontSize: 11, color: '#999', marginLeft: 8 }}>
              {new Date(proof.created_at).toLocaleString()}
            </span>
          )}
        </div>
        <Renderer content={proof.content} file_path={proof.file_path} />
      </div>
    </div>
  );
}
