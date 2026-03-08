import React from 'react';
import { ChatBubbleLeftRightIcon } from '@heroicons/react/24/solid';

export default function QuinnFAB({ onClick, isOpen }) {
  if (isOpen) return null;

  return (
    <button
      onClick={onClick}
      className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full
        bg-gradient-to-r from-fg-teal to-fg-green
        text-white shadow-lg hover:shadow-xl
        flex items-center justify-center
        transition-all duration-300 hover:scale-105
        animate-fade-in group"
      title="Chat with Quinn"
    >
      <ChatBubbleLeftRightIcon className="w-6 h-6 group-hover:scale-110 transition-transform" />
      <span className="absolute -top-1 -right-1 w-3 h-3 bg-fg-green rounded-full animate-pulse" />
    </button>
  );
}
