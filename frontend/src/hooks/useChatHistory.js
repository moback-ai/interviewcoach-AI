import { useState, useCallback } from 'react';
import { getSession } from '../lib/authClient';
import { getBackendOrigin } from '../utils/apiConfig';
import {
  mapStructuredMessages,
  parseHistoryContent,
} from '../utils/chatHistoryParse';

const defaultInterviewUiState = () => ({
  interviewStage: 'introduction',
  hasAnsweredResumeQuestion: false,
  canEndInterview: false,
  awaitingManualEnd: false,
});

export { mapStructuredMessages, parseHistoryContent } from '../utils/chatHistoryParse';

export const useChatHistory = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
            Authorization: `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        },
      );

      if (!response.ok) {
        throw new Error(`Failed to load chat history: ${response.status}`);
      }

      const data = await response.json();
      const uiState = {
        interviewStage: data.interview_stage || 'introduction',
        hasAnsweredResumeQuestion: !!data.has_answered_resume_question,
        canEndInterview: !!data.can_end_interview,
        awaitingManualEnd: !!data.awaiting_manual_end,
      };

      const structured = mapStructuredMessages(data.messages);
      if (structured.length > 0) {
        return { conversation: structured, ...uiState };
      }

      if (data.history && data.history.length > 0) {
        const content = data.history[0].content;
        const conversation = parseHistoryContent(content);
        return { conversation, ...uiState };
      }

      return {
        conversation: [{
          id: 1,
          speaker: 'interviewer',
          message: 'Speak to start the interview.',
          timestamp: new Date().toLocaleTimeString(),
        }],
        ...uiState,
      };
    } catch (err) {
      console.error('Error loading chat history:', err);
      setError(err.message);
      return {
        conversation: [],
        ...defaultInterviewUiState(),
      };
    } finally {
      setLoading(false);
    }
  }, []);

  const saveChatHistory = useCallback(async (interviewId, conversation) => {
    if (!interviewId || !conversation || conversation.length === 0) return false;

    setLoading(true);
    setError(null);

    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const messages = conversation.map((msg) => ({
        role:
          msg.speaker === 'interviewer'
            ? 'assistant'
            : msg.speaker === 'candidate'
              ? 'user'
              : (msg.speaker || 'system'),
        content: msg.message ?? '',
      }));

      const response = await fetch(
        `${getBackendOrigin()}/functions/v1/chat-history`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            interview_id: interviewId,
            messages,
          }),
        },
      );

      if (!response.ok) {
        throw new Error(`Failed to save chat history: ${response.status}`);
      }

      return true;
    } catch (err) {
      console.error('Error saving chat history:', err);
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const appendToChatHistory = useCallback(async (interviewId, speaker, message) => {
    if (!interviewId || !speaker || !message) return false;

    setLoading(true);
    setError(null);

    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const role =
        speaker === 'interviewer'
          ? 'assistant'
          : speaker === 'candidate'
            ? 'user'
            : speaker;

      const response = await fetch(
        `${getBackendOrigin()}/functions/v1/chat-history`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            interview_id: interviewId,
            messages: [{ role, content: message }],
            append: true,
          }),
        },
      );

      if (!response.ok) {
        throw new Error(`Failed to append to chat history: ${response.status}`);
      }

      return true;
    } catch (err) {
      console.error('Error appending to chat history:', err);
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteChatHistory = useCallback(async (interviewId) => {
    if (!interviewId) {
      console.error('❌ No interview ID provided for deletion');
      return false;
    }

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
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        },
      );

      const responseData = await response.json();

      if (!response.ok) {
        throw new Error(
          `Failed to delete chat history: ${response.status} - ${responseData.error || responseData.message}`,
        );
      }

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
    deleteChatHistory,
  };
};
