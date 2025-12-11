'use client';

import { useState } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: Array<{ title: string; url?: string }>;
}

interface ApiResponse {
  answer: string;
  sources?: Array<{ title: string; url?: string }>;
  conversation_id?: string;
}

export default function Home() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (message.trim().length < 10) {
      return;
    }

    const userMessage: Message = {
      role: 'user',
      content: message,
      timestamp: new Date(),
    };

    const currentMessage = message;

    setMessages((prev) => [...prev, userMessage]);
    setMessage('');
    setIsLoading(true);
    setError(null);

    try {
      // Backend handles conversation memory, so we only send the current question
      // Include conversation_id if we have one to track the conversation
      const payload: { question: string; conversation_id?: string } = {
        question: currentMessage,
      };

      if (conversationId) {
        payload.conversation_id = conversationId;
      }

      // Log the current question
      console.log('=== Current Question ===');
      console.log(`Question: ${currentMessage}`);
      console.log(`Conversation ID: ${conversationId || 'New conversation'}`);
      console.log('========================');

      // const response = await fetch('http://localhost:8001/api/rag/query', {
      // const response = await fetch('https://41dor7gjde.execute-api.ca-central-1.amazonaws.com/api/rag/query', {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/rag/query`, {


        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(300000), // 30 second timeout to match Python
      });

      if (!response.ok) {
        // Try to get error details from response
        let errorDetails = '';
        try {
          const errorData = await response.json();
          errorDetails = errorData.detail || errorData.error?.message || errorData.message || '';
        } catch {
          // If response is not JSON, use status text
          errorDetails = response.statusText;
        }
        throw new Error(`API request failed with status ${response.status}${errorDetails ? `: ${errorDetails}` : ''}`);
      }

      const data: ApiResponse = await response.json();

      // Store conversation_id from response if provided
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
      }

      const aiMessage: Message = {
        role: 'assistant',
        content: data.answer || 'I apologize, but I could not generate a response.',
        timestamp: new Date(),
        sources: data.sources,
      };

      // Log the response
      console.log('=== AI Response ===');
      console.log(`Answer: ${aiMessage.content}`);
      if (data.conversation_id) {
        console.log(`Conversation ID: ${data.conversation_id}`);
      }
      if (aiMessage.sources && aiMessage.sources.length > 0) {
        console.log(`Sources (${aiMessage.sources.length}):`);
        aiMessage.sources.forEach((source, index) => {
          console.log(`  [${index + 1}] ${source.title}${source.url ? ` - ${source.url}` : ''}`);
        });
      }
      console.log('===================');

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred. Please try again.';
      setError(errorMessage);
      
      const errorMessageObj: Message = {
        role: 'assistant',
        content: `I'm sorry, I encountered an error: ${errorMessage}. Please check your connection and try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessageObj]);
    } finally {
      setIsLoading(false);
    }
  };

  const canSend = message.trim().length >= 10;

  const startNewConversation = () => {
    setMessages([]);
    setConversationId(null);
    setMessage('');
    setError(null);
  };

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 font-sans dark:bg-black">
      {/* Header */}
      <header className="border-b border-black/[.08] bg-white px-6 py-4 dark:border-white/[.145] dark:bg-zinc-950">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <h1 className="text-xl font-semibold text-black dark:text-zinc-50">
            SuperHRAI Chat
          </h1>
          <div className="flex gap-2">
            {messages.length > 0 && (
              <button
                onClick={startNewConversation}
                className="rounded-md px-4 py-2 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
              >
                New Chat
              </button>
            )}
            <button className="rounded-md px-4 py-2 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900">
              Settings
            </button>
          </div>
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-4xl">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center py-16 text-center">
                <h2 className="mb-4 text-2xl font-semibold text-black dark:text-zinc-50">
                  Welcome to SuperHRAI Chat
                </h2>
                <p className="max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-400">
                  Ask me anything about your company policies, HR procedures, or employee benefits. I'll help you find the information you need.
                </p>
                <div className="mt-8 flex flex-wrap gap-2">
                  <button
                    onClick={() => setMessage('What are the company vacation policies?')}
                    className="rounded-full border border-black/[.08] bg-white px-4 py-2 text-sm text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-white/[.145] dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  >
                    Vacation policies
                  </button>
                  <button
                    onClick={() => setMessage('How do I request time off?')}
                    className="rounded-full border border-black/[.08] bg-white px-4 py-2 text-sm text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-white/[.145] dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  >
                    Time off request
                  </button>
                  <button
                    onClick={() => setMessage('What benefits are available?')}
                    className="rounded-full border border-black/[.08] bg-white px-4 py-2 text-sm text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-white/[.145] dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  >
                    Employee benefits
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-3 ${
                        msg.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-white text-black dark:bg-zinc-900 dark:text-zinc-50'
                      }`}
                    >
                      <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {msg.sources.map((source, idx) => (
                            <span
                              key={idx}
                              className="rounded-md bg-blue-100 px-2 py-1 text-xs text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                            >
                              {source.title}
                            </span>
                          ))}
                        </div>
                      )}
                      <p
                        className={`mt-1 text-xs ${
                          msg.role === 'user'
                            ? 'text-blue-100'
                            : 'text-zinc-500 dark:text-zinc-400'
                        }`}
                      >
                        {msg.timestamp.toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="rounded-lg bg-white px-4 py-3 dark:bg-zinc-900">
                      <div className="flex gap-1">
                        <div className="h-2 w-2 animate-bounce rounded-full bg-zinc-400 [animation-delay:-0.3s]"></div>
                        <div className="h-2 w-2 animate-bounce rounded-full bg-zinc-400 [animation-delay:-0.15s]"></div>
                        <div className="h-2 w-2 animate-bounce rounded-full bg-zinc-400"></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-black/[.08] bg-white px-4 py-4 dark:border-white/[.145] dark:bg-zinc-950">
          <div className="mx-auto max-w-4xl">
            <form onSubmit={handleSubmit} className="flex gap-2">
              <div className="flex flex-1 items-end gap-2 rounded-lg border border-black/[.08] bg-white p-2 dark:border-white/[.145] dark:bg-zinc-900">
                <button
                  type="button"
                  className="flex h-10 w-10 items-center justify-center rounded-md text-zinc-600 transition-colors hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
                  title="Upload file"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="h-5 w-5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.121 2.121l7.81-7.81a1.5 1.5 0 00-2.121-2.121z"
                    />
                  </svg>
                </button>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && canSend) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                  placeholder="Ask a question about company policies, HR procedures, employee benefits, and more... (minimum 10 characters)"
                  rows={1}
                  className="max-h-32 flex-1 resize-none border-0 bg-transparent px-2 py-2 text-base text-black placeholder-zinc-500 focus:outline-none dark:text-zinc-50 dark:placeholder-zinc-400"
                />
                <div className="flex items-center gap-1 px-2">
                  <span
                    className={`text-xs ${
                      message.length < 10
                        ? 'text-zinc-400 dark:text-zinc-600'
                        : 'text-zinc-600 dark:text-zinc-400'
                    }`}
                  >
                    {message.length}/10
                  </span>
                </div>
              </div>
              <button
                type="submit"
                disabled={!canSend || isLoading}
                className="flex h-14 w-14 items-center justify-center rounded-lg bg-blue-600 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-blue-600"
                title="Send message"
              >
                {isLoading ? (
                  <svg
                    className="h-5 w-5 animate-spin"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                ) : (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="h-5 w-5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                    />
                  </svg>
                )}
              </button>
            </form>
            {message.length > 0 && message.length < 10 && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                Please enter at least 10 characters to send a message.
              </p>
            )}
            {error && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
