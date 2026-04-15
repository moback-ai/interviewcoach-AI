import { useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { apiPost } from '../api';

export const useSupportBot = () => {
  const { user, isAuthenticated } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [conversation, setConversation] = useState([]);

  const sendMessage = useCallback(async (message) => {
    if (!isAuthenticated || !message.trim()) {
      return;
    }

    setIsLoading(true);
    setError(null);

    // Add user message to conversation
    const userMessage = {
      id: Date.now(),
      type: 'user',
      message: message.trim(),
      timestamp: new Date().toISOString()
    };

    setConversation(prev => [...prev, userMessage]);

    try {
      const response = await apiPost('/api/support-bot', {
        message: message.trim()
      });

      if (response.success) {
        const botMessage = {
          id: Date.now() + 1,
          type: 'bot',
          message: response.data.response,
          timestamp: new Date().toISOString(),
          retrievedSections: response.data.retrieved_sections || []
        };

        setConversation(prev => [...prev, botMessage]);
      } else {
        throw new Error(response.message || 'Failed to get support response');
      }
    } catch (err) {
      console.error('Support bot error:', err);
      setError(err.message);
      
      // Add error message to conversation
      const errorMessage = {
        id: Date.now() + 1,
        type: 'error',
        message: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString()
      };
      
      setConversation(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const startNewChat = useCallback(() => {
    // Reset current conversation
    setConversation([]);
    setError(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    conversation,
    isLoading,
    error,
    sendMessage,
    startNewChat,
    clearError,
    isAuthenticated
  };
};
