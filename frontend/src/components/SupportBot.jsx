import React, { useState, useRef, useEffect } from 'react';
import { useSupportBot } from '../hooks/useSupportBot';
import { useTheme } from '../hooks/useTheme';

const SupportBot = () => {
  const { 
    conversation, 
    isLoading, 
    error, 
    sendMessage, 
    startNewChat, 
    clearError, 
    isAuthenticated
  } = useSupportBot();
  
  const { isDarkMode } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const [inputMessage, setInputMessage] = useState('');
  const [isMinimized, setIsMinimized] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Start new chat when opening
  useEffect(() => {
    if (isOpen) {
      startNewChat();
    }
  }, [isOpen, startNewChat]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const message = inputMessage;
    setInputMessage('');
    await sendMessage(message);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(e);
    }
  };

  const toggleChat = () => {
    setIsOpen(!isOpen);
    setIsMinimized(false);
    if (error) clearError();
  };

  const minimizeChat = () => {
    setIsMinimized(true);
  };

  const expandChat = () => {
    setIsMinimized(false);
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* Chat Widget */}
      {isOpen && (
        <div 
          className={`transition-all duration-300 ease-in-out ${
            isMinimized 
              ? 'w-80 h-16' 
              : 'w-80 h-[600px]'
          } rounded-lg shadow-2xl border flex flex-col ${
            isDarkMode 
              ? 'bg-gray-800 border-gray-700' 
              : 'bg-white border-gray-200'
          }`}
        >
          {/* Header */}
          <div className={`flex items-center justify-between p-4 border-b ${
            isDarkMode ? 'bg-gray-700 border-gray-600' : 'bg-gradient-to-r from-blue-600 to-blue-700 border-gray-200'
          }`}>
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-semibold text-sm">Interview Coach Support</h3>
                  <p className="text-blue-100 text-xs">AI Assistant</p>
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={isMinimized ? expandChat : minimizeChat}
                className="text-white hover:text-blue-200 transition-colors p-1 rounded-full hover:bg-white/10"
                title={isMinimized ? "Expand" : "Minimize"}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={isMinimized ? "M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" : "M20 12H4"} />
                </svg>
              </button>
              <button
                onClick={toggleChat}
                className="text-white hover:text-blue-200 transition-colors p-1 rounded-full hover:bg-white/10"
                title="Close"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content Area */}
          {!isMinimized && (
            <>
              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {conversation.length === 0 ? (
                  <div className="text-center text-gray-500 mt-8">
                    <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-blue-100 to-blue-200 rounded-full flex items-center justify-center">
                      <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                    </div>
                    <h4 className="font-semibold text-gray-700 mb-2">Hello! 👋</h4>
                    <p className="text-sm text-gray-600 mb-1">I'm your AI support assistant.</p>
                    <p className="text-xs text-gray-500">How can I help you today?</p>
                  </div>
                ) : (
                  conversation.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-xs px-4 py-3 rounded-2xl text-sm ${
                          msg.type === 'user'
                            ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white'
                            : msg.type === 'error'
                            ? 'bg-red-50 text-red-800 border border-red-200'
                            : isDarkMode
                            ? 'bg-gray-700 text-gray-100'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        <p className="whitespace-pre-wrap leading-relaxed">{msg.message}</p>
                        {msg.retrievedSections && msg.retrievedSections.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-gray-300">
                            <p className="text-xs text-gray-500">
                              📚 Sources: {msg.retrievedSections.join(', ')}
                            </p>
                          </div>
                        )}
                        <p className="text-xs opacity-70 mt-1">
                          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                    </div>
                  ))
                )}
                
                {isLoading && (
                  <div className="flex justify-start">
                    <div className={`max-w-xs px-4 py-3 rounded-2xl text-sm ${
                      isDarkMode ? 'bg-gray-700 text-gray-100' : 'bg-gray-100 text-gray-800'
                    }`}>
                      <div className="flex items-center space-x-2">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                        <span className="text-xs">Typing...</span>
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>

              {/* Error Message */}
              {error && (
                <div className="px-4 py-3 bg-red-50 border-t border-red-200">
                  <div className="flex items-start space-x-2">
                    <svg className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div className="flex-1">
                      <p className="text-red-800 text-sm">{error}</p>
                      <button
                        onClick={clearError}
                        className="text-red-600 hover:text-red-800 text-xs underline mt-1"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Input */}
              <div className="p-4 border-t border-gray-200">
                <form onSubmit={handleSendMessage} className="flex space-x-2">
                  <input
                    ref={inputRef}
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Type your message..."
                    disabled={isLoading}
                    className={`flex-1 px-4 py-3 rounded-full border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all ${
                      isDarkMode
                        ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400'
                        : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500'
                    }`}
                  />
                  <button
                    type="submit"
                    disabled={!inputMessage.trim() || isLoading}
                    className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 ${
                      inputMessage.trim() && !isLoading
                        ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white hover:from-blue-700 hover:to-blue-800 shadow-lg hover:shadow-xl transform hover:scale-105'
                        : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    }`}
                  >
                    {isLoading ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                      </svg>
                    )}
                  </button>
                </form>
              </div>
            </>
          )}
        </div>
      )}

      {/* Small Toggle Button - Only shows when chat is closed */}
      {!isOpen && (
        <button
          onClick={toggleChat}
          className="w-12 h-12 rounded-full shadow-lg flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-xl bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800"
          title="Open Support Chat"
        >
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      )}
    </div>
  );
};

export default SupportBot;
