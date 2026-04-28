import { useState, useCallback } from 'react';
import { getSession } from '../lib/authClient';
import { getBackendOrigin } from '../utils/apiConfig';

const normalizeChatSpeaker = (speaker = '') => {
  const normalized = String(speaker).trim().toLowerCase();
  if (['assistant', 'interviewer', 'bot'].includes(normalized)) return 'interviewer';
  if (['user', 'candidate', 'you'].includes(normalized)) return 'candidate';
  return normalized || 'system';
};

export const useChatHistory = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load chat history from database
  const loadChatHistory = useCallback(async (interviewId) => {
    if (!interviewId) return null;

    setLoading(true);
    setError(null);

    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const response = await fetch(
        `${getBackendOrigin()}/functions/v1/chat-history?interview_id=${interviewId}`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to load chat history: ${response.status}`);
      }

      const data = await response.json();
      
      if (data.history && data.history.length > 0) {
        // Parse the content string back to conversation array
        const content = data.history[0].content;
        console.log('🔍 Raw content from DB:', content);
        
        // ✅ FIXED: Better parsing to handle multi-line messages
        const lines = content.split('\n');
        const conversation = [];
        
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue; // Skip empty lines
          
          // Find the first colon to separate speaker from message
          const colonIndex = line.indexOf(':');
          if (colonIndex === -1) {
            // If no colon found, this might be a continuation of the previous message
            if (conversation.length > 0) {
              const lastMessage = conversation[conversation.length - 1];
              lastMessage.message += '\n' + line;
            }
            continue;
          }
          
          const speaker = normalizeChatSpeaker(line.substring(0, colonIndex));
          const message = line.substring(colonIndex + 1).trim();

          const previous = conversation[conversation.length - 1];
          if (previous?.speaker === speaker && previous?.message === message) {
            continue;
          }
          
          conversation.push({
            id: conversation.length + 1,
            speaker: speaker,
            message: message,
            timestamp: new Date().toLocaleTimeString()
          });
        }

        console.log(`Loaded ${conversation.length} messages from database:`, conversation);
        return conversation;
      }

      // ✅ FIXED: If no history exists, return a local-only welcome message (do NOT write)
      console.log('No chat history found. Returning local welcome message only (no DB write).');
      return [{
        id: 1,
        speaker: 'interviewer',
        message: 'Speak to start the interview.',
        timestamp: new Date().toLocaleTimeString()
      }];

    } catch (err) {
      console.error('Error loading chat history:', err);
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  // Save chat history to database
  const saveChatHistory = useCallback(async (interviewId, conversation) => {
    if (!interviewId || !conversation || conversation.length === 0) return false;

    setLoading(true);
    setError(null);

    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      // Convert conversation array to string format
      const content = conversation
        .map(msg => `${msg.speaker}:${msg.message}`)
        .join('\n');

      const response = await fetch(
        `${getBackendOrigin()}/functions/v1/chat-history`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            interview_id: interviewId,
            content: content
          })
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to save chat history: ${response.status}`);
      }

      console.log('Chat history saved successfully');
      return true;

    } catch (err) {
      console.error('Error saving chat history:', err);
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  // Append new message to existing chat history
  const appendToChatHistory = useCallback(async (interviewId, speaker, message) => {
    if (!interviewId || !speaker || !message) return false;

    setLoading(true);
    setError(null);

    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const newContent = `${speaker}:${message}`;

      const response = await fetch(
        `${getBackendOrigin()}/functions/v1/chat-history`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            interview_id: interviewId,
            content: newContent
          })
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to append to chat history: ${response.status}`);
      }

      console.log('Message appended to chat history');
      return true;

    } catch (err) {
      console.error('Error appending to chat history:', err);
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  // ✅ NEW: Delete chat history for an interview
  const deleteChatHistory = useCallback(async (interviewId) => {
    if (!interviewId) {
      console.error('❌ No interview ID provided for deletion');
      return false;
    }

    console.log('🗑️ Starting chat history deletion for interview:', interviewId);
    setLoading(true);
    setError(null);

    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      console.log('🔑 Session found, making DELETE request...');
      const response = await fetch(
        `${getBackendOrigin()}/functions/v1/chat-history?interview_id=${interviewId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      console.log('📡 DELETE response status:', response.status);
      const responseData = await response.json();
      console.log('📡 DELETE response data:', responseData);

      if (!response.ok) {
        throw new Error(`Failed to delete chat history: ${response.status} - ${responseData.error || responseData.message}`);
      }

      console.log('✅ Chat history deleted successfully');
      return true;

    } catch (err) {
      console.error('❌ Error deleting chat history:', err);
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    loadChatHistory,
    saveChatHistory,
    appendToChatHistory,
    deleteChatHistory // ✅ NEW: Export delete function
  };
};
