import React from 'react';
import {
  ChatBubbleLeftIcon,
  TrashIcon,
  PlusIcon,
} from '@heroicons/react/24/outline';

export default function QuinnSessionList({
  sessions,
  activeSessionId,
  onSelect,
  onDelete,
  onNew,
  onClose,
}) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-gray-200 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-fg-navy">Chat History</h4>
        <button
          onClick={onNew}
          className="flex items-center gap-1 text-xs text-fg-teal hover:text-fg-tealDark font-medium"
        >
          <PlusIcon className="w-3.5 h-3.5" />
          New
        </button>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {sessions.length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-8">No conversations yet</p>
        ) : (
          sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => onSelect(s.id)}
              className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer border-b border-gray-50 transition-colors group
                ${s.id === activeSessionId ? 'bg-fg-tealLight' : 'hover:bg-gray-50'}`}
            >
              <ChatBubbleLeftIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-fg-dark truncate">
                  {s.title || 'New conversation'}
                </p>
                <p className="text-xxs text-gray-400">
                  {s.message_count || 0} messages
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(s.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-all"
                title="Delete"
              >
                <TrashIcon className="w-3.5 h-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
      <div className="p-2 border-t border-gray-200">
        <button
          onClick={onClose}
          className="w-full text-xs text-gray-500 hover:text-fg-dark py-1"
        >
          Back to chat
        </button>
      </div>
    </div>
  );
}
