import React, { useMemo } from 'react';
import QuinnToolResult from './QuinnToolResult';

// Simple markdown-like rendering without external dependency
function renderMarkdown(text) {
  if (!text) return null;

  const lines = text.split('\n');
  const elements = [];
  let inCodeBlock = false;
  let codeContent = '';
  let codeLanguage = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code blocks
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={`code-${i}`} className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs overflow-x-auto my-2">
            <code>{codeContent.trimEnd()}</code>
          </pre>
        );
        codeContent = '';
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
        codeLanguage = line.slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeContent += line + '\n';
      continue;
    }

    // Empty line
    if (!line.trim()) {
      elements.push(<div key={`br-${i}`} className="h-2" />);
      continue;
    }

    // Headers
    if (line.startsWith('### ')) {
      elements.push(<h4 key={i} className="font-semibold text-sm text-fg-navy mt-2 mb-1">{processInline(line.slice(4))}</h4>);
      continue;
    }
    if (line.startsWith('## ')) {
      elements.push(<h3 key={i} className="font-bold text-sm text-fg-navy mt-3 mb-1">{processInline(line.slice(3))}</h3>);
      continue;
    }
    if (line.startsWith('# ')) {
      elements.push(<h2 key={i} className="font-bold text-base text-fg-navy mt-3 mb-1">{processInline(line.slice(2))}</h2>);
      continue;
    }

    // List items
    if (line.match(/^\s*[-*]\s/)) {
      const indent = line.search(/\S/);
      elements.push(
        <div key={i} className="flex gap-1.5 text-sm" style={{ paddingLeft: Math.max(0, indent - 2) * 4 }}>
          <span className="text-fg-teal mt-0.5 flex-shrink-0">&#x2022;</span>
          <span>{processInline(line.replace(/^\s*[-*]\s/, ''))}</span>
        </div>
      );
      continue;
    }

    // Numbered list
    if (line.match(/^\s*\d+\.\s/)) {
      const num = line.match(/^\s*(\d+)\./)[1];
      elements.push(
        <div key={i} className="flex gap-1.5 text-sm">
          <span className="text-fg-teal flex-shrink-0 font-medium">{num}.</span>
          <span>{processInline(line.replace(/^\s*\d+\.\s/, ''))}</span>
        </div>
      );
      continue;
    }

    // Table rows
    if (line.includes('|') && line.trim().startsWith('|')) {
      const cells = line.split('|').filter(Boolean).map((c) => c.trim());
      if (cells.every((c) => c.match(/^[-:]+$/))) continue; // separator
      const isHeader = i + 1 < lines.length && lines[i + 1]?.includes('---');
      elements.push(
        <div key={i} className={`grid gap-2 text-xs py-1 px-2 ${isHeader ? 'font-semibold bg-gray-50 rounded' : 'border-b border-gray-100'}`}
          style={{ gridTemplateColumns: `repeat(${cells.length}, minmax(0, 1fr))` }}>
          {cells.map((cell, j) => <span key={j}>{processInline(cell)}</span>)}
        </div>
      );
      continue;
    }

    // Regular paragraph
    elements.push(<p key={i} className="text-sm">{processInline(line)}</p>);
  }

  // Handle unclosed code block
  if (inCodeBlock && codeContent) {
    elements.push(
      <pre key="code-end" className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs overflow-x-auto my-2">
        <code>{codeContent.trimEnd()}</code>
      </pre>
    );
  }

  return elements;
}

function processInline(text) {
  if (!text) return text;

  // Process inline formatting
  const parts = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Bold
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    // Inline code
    const codeMatch = remaining.match(/`([^`]+)`/);

    let earliest = null;
    let earliestIndex = Infinity;

    if (boldMatch && boldMatch.index < earliestIndex) {
      earliest = { type: 'bold', match: boldMatch };
      earliestIndex = boldMatch.index;
    }
    if (codeMatch && codeMatch.index < earliestIndex) {
      earliest = { type: 'code', match: codeMatch };
      earliestIndex = codeMatch.index;
    }

    if (!earliest) {
      parts.push(remaining);
      break;
    }

    // Text before match
    if (earliestIndex > 0) {
      parts.push(remaining.slice(0, earliestIndex));
    }

    if (earliest.type === 'bold') {
      parts.push(<strong key={key++} className="font-semibold">{earliest.match[1]}</strong>);
    } else if (earliest.type === 'code') {
      parts.push(
        <code key={key++} className="bg-gray-100 text-fg-tealDark px-1 py-0.5 rounded text-xs font-mono">
          {earliest.match[1]}
        </code>
      );
    }

    remaining = remaining.slice(earliestIndex + earliest.match[0].length);
  }

  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : parts;
}


export default function QuinnMessage({ message }) {
  const { role, content, metadata } = message;

  // Tool call message
  if (role === 'tool_call') {
    try {
      const data = JSON.parse(content);
      return (
        <div className="flex justify-start mb-2 animate-fade-in">
          <div className="max-w-[90%] px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs">
            <div className="flex items-center gap-1.5 text-amber-700">
              <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40" strokeDashoffset="10" />
              </svg>
              <span className="font-medium">Using tool:</span>
              <code className="font-mono">{data.tool}</code>
            </div>
          </div>
        </div>
      );
    } catch {
      return null;
    }
  }

  // Tool result message
  if (role === 'tool_result') {
    try {
      const result = JSON.parse(content);
      const toolName = metadata?.tool || '';
      return (
        <div className="flex justify-start mb-2 animate-fade-in">
          <div className="max-w-[90%]">
            <QuinnToolResult toolName={toolName} result={result} />
          </div>
        </div>
      );
    } catch {
      return null;
    }
  }

  const isUser = role === 'user';

  const rendered = useMemo(() => {
    if (isUser) return null;
    return renderMarkdown(content);
  }, [content, isUser]);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3 animate-fade-in`}>
      <div
        className={`max-w-[85%] px-3.5 py-2.5 rounded-xl text-sm leading-relaxed
          ${isUser
            ? 'bg-fg-teal/10 text-fg-dark rounded-br-sm'
            : 'bg-white border border-gray-100 shadow-sm rounded-bl-sm text-fg-dark'
          }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="quinn-markdown space-y-0.5">{rendered}</div>
        )}
      </div>
    </div>
  );
}
