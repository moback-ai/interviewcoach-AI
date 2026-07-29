import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Code } from 'lucide-react';
import { uploadFile, apiPost, apiDelete } from '../../api';
import { apiPostInterviewStream } from '../../api/interviewStream';
import { useChatHistory } from '../../hooks/useChatHistory';

import { trackEvents } from '../../services/mixpanel';
import CodeEditorPopup from './CodeEditorPopup';
import { getMediaAccessErrorMessage, requestUserMedia } from '../../utils/mediaDevices';
import { devLog } from '../../utils/devLog';
import { createAuthenticatedAudioElement } from '../../hooks/useAuthenticatedBlobUrl';
import { revokeBlobUrl } from '../../utils/protectedFiles';

const GENERATE_RESPONSE_TIMEOUT_MS = 120000;

const END_INTERVIEW_LATER_STAGES = new Set([
  'custom_questions',
  'candidate_questions',
  'wrapup_evaluation',
  'manual_end',
]);

function resolveEndInterviewState(stage, hasAnsweredResumeQuestion) {
  const interviewStage = stage || 'introduction';
  const answeredResume = !!hasAnsweredResumeQuestion;
  const canEndInterview =
    END_INTERVIEW_LATER_STAGES.has(interviewStage) ||
    (interviewStage === 'resume_discussion' && answeredResume);

  return {
    interviewStage,
    hasAnsweredResumeQuestion: answeredResume,
    canEndInterview,
  };
}

function ChatWindow({ conversation, setConversation, isLoading, setIsLoading, isAudioPlaying, setIsAudioPlaying, onStateChange }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isButtonDisabled, setIsButtonDisabled] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  
  // Add this state for loading
  const [isEndingInterview, setIsEndingInterview] = useState(false);
  const [currentAudioElement, setCurrentAudioElement] = useState(null);
  const [canEndInterview, setCanEndInterview] = useState(false); // Start disabled
  const [isResponseInProgress, setIsResponseInProgress] = useState(false);

  const { loadChatHistory, deleteChatHistory } = useChatHistory();

  const buildGenerateResponsePayload = useCallback((message) => {
    const urlParams = new URLSearchParams(window.location.search);
    const interviewId = urlParams.get('interview_id');
    return {
      message,
      interview_id: interviewId,
    };
  }, []);

  // ✅ NEW: Add state to track interview stage and resume question answers
  const [interviewStage, setInterviewStage] = useState('introduction');
  const [hasAnsweredResumeQuestion, setHasAnsweredResumeQuestion] = useState(false);
  const [awaitingManualEnd, setAwaitingManualEnd] = useState(false);

  const [showCodeEditor, setShowCodeEditor] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [isCodingQuestion, setIsCodingQuestion] = useState(false);
  const [codeToAppend, setCodeToAppend] = useState('');
  const [language, setLanguage] = useState('javascript');

  // Auto-scroll to bottom when new messages are added
  const scrollToBottom = () => {
    // ✅ FIXED: Scroll only the messages container
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation, isLoading, isAudioPlaying]);

  useEffect(() => {
    if (!messagesEndRef.current) return undefined;
    const frame = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    });
    return () => cancelAnimationFrame(frame);
  }, [conversation.length, isLoading]);

  // Cleanup function to stop media stream when component unmounts
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (currentAudioElement) {
        currentAudioElement.pause();
        currentAudioElement.currentTime = 0;
      }
      setIsAudioPlaying(false);
      setCurrentAudioElement(null);
    };
  }, [currentAudioElement, setIsAudioPlaying]);

  // Debug loading state changes
  useEffect(() => {
    devLog('🔄 Loading state changed to:', isLoading);
  }, [isLoading]);

  // Notify parent component of state changes for head tracking toggle
  useEffect(() => {
    if (onStateChange) {
      onStateChange({
        isRecording,
        isResponseInProgress,
        canEndInterview,
        isSpeakCooldown: isButtonDisabled,
      });
    }
  }, [isRecording, isResponseInProgress, canEndInterview, isButtonDisabled, onStateChange]);

  const deleteGeneratedAudio = useCallback(async (audioUrl, shouldDeleteAudio) => {
    if (!audioUrl || !shouldDeleteAudio) return;

    try {
      await apiDelete('/api/delete-audio', {
        body: { audio_url: audioUrl }
      });
    } catch (error) {
      console.error('❌ Failed to delete audio file:', error);
    }
  }, []);

  const playServerAudio = useCallback(async (audioUrl) => {
    const { audio, blobUrl } = await createAuthenticatedAudioElement(audioUrl);
    audio.preload = 'auto';
    setCurrentAudioElement(audio);

    const cleanupAudio = () => {
      audio.onended = null;
      audio.onerror = null;
      audio.oncanplaythrough = null;
      revokeBlobUrl(blobUrl);
    };

    try {
      await new Promise((resolve, reject) => {
        const startPlayback = () => {
          audio.play().catch((error) => {
            cleanupAudio();
            reject(error);
          });
        };

        if (audio.readyState >= 2) {
          startPlayback();
        } else {
          audio.oncanplaythrough = startPlayback;
          setTimeout(() => {
            if (audio.readyState >= 2) {
              startPlayback();
            }
          }, 100);
        }

        audio.onended = () => {
          cleanupAudio();
          resolve();
        };

        audio.onerror = (error) => {
          cleanupAudio();
          reject(error);
        };
      });
    } catch (error) {
      revokeBlobUrl(blobUrl);
      throw error;
    }
  }, [setCurrentAudioElement]);

  const playInterviewerResponseAudio = useCallback(async (audioUrl, shouldDeleteAudio) => {
    if (!audioUrl) {
      return;
    }

    setIsAudioPlaying(true);

    try {
      await playServerAudio(audioUrl);
    } finally {
      setIsAudioPlaying(false);
      setCurrentAudioElement(null);
      await deleteGeneratedAudio(audioUrl, shouldDeleteAudio);
    }
  }, [deleteGeneratedAudio, playServerAudio, setIsAudioPlaying]);

  const processEndInterviewResponse = useCallback(({
    interviewId,
    textResponse,
    audio_url,
    should_delete_audio,
    interview_done,
  }) => {
    const run = async () => {
      if (audio_url) {
        devLog('🔊 Preloading final audio response:', audio_url);
        let blobUrl = null;
        let audio;
        try {
          ({ audio, blobUrl } = await createAuthenticatedAudioElement(audio_url));
        } catch (error) {
          console.error('❌ Failed to load final audio:', error);
          if (interview_done) {
            window.location.href = `/interview-feedback?interview_id=${interviewId}`;
          }
          return;
        }

        audio.preload = 'auto';

        let messageAdded = false;

        const playFinalAudioWhenReady = () => {
          if (messageAdded) {
            return;
          }
          messageAdded = true;

          setConversation((prev) => prev.filter((msg) => !msg.isThinking));
          const finalMessage = {
            id: Date.now(),
            speaker: 'interviewer',
            message: textResponse,
            timestamp: new Date().toLocaleTimeString(),
          };
          setConversation((prev) => [...prev, finalMessage]);

          setIsAudioPlaying(true);
          setCurrentAudioElement(audio);
          setCanEndInterview(false);

          audio.play().catch((error) => {
            console.error('❌ Failed to play final audio:', error);
            setIsAudioPlaying(false);
            setCurrentAudioElement(null);
            revokeBlobUrl(blobUrl);
            if (interview_done) {
              window.location.href = `/interview-feedback?interview_id=${interviewId}`;
            }
          });
        };

        if (audio.readyState >= 2) {
          playFinalAudioWhenReady();
        } else {
          audio.addEventListener('canplaythrough', playFinalAudioWhenReady, { once: true });
          setTimeout(() => {
            if (audio.readyState >= 2 && !messageAdded) {
              playFinalAudioWhenReady();
            }
          }, 100);
        }

        audio.onended = async () => {
          devLog('✅ Final audio playback completed');
          setIsAudioPlaying(false);
          setCurrentAudioElement(null);
          setCanEndInterview(true);
          revokeBlobUrl(blobUrl);

          if (should_delete_audio) {
            try {
              await apiDelete('/api/delete-audio', {
                body: { audio_url },
              });
            } catch (error) {
              console.error('❌ Failed to delete final audio file:', error);
            }
          }

          if (interview_done) {
            setTimeout(() => {
              window.location.href = `/interview-feedback?interview_id=${interviewId}`;
            }, 1000);
          }
        };

        audio.onerror = (error) => {
          console.error('❌ Final audio playback failed:', error);
          setIsAudioPlaying(false);
          setCurrentAudioElement(null);
          revokeBlobUrl(blobUrl);

          setConversation((prev) => {
            const filtered = prev.filter((msg) => !msg.isThinking);
            const finalMessage = {
              id: Date.now(),
              speaker: 'interviewer',
              message: textResponse,
              timestamp: new Date().toLocaleTimeString(),
            };
            return [...filtered, finalMessage];
          });

          if (interview_done) {
            window.location.href = `/interview-feedback?interview_id=${interviewId}`;
          }
        };
        return;
      }

      if (interview_done) {
        setConversation((prev) => {
          const filtered = prev.filter((msg) => !msg.isThinking);
          const finalMessage = {
            id: Date.now(),
            speaker: 'interviewer',
            message: textResponse,
            timestamp: new Date().toLocaleTimeString(),
          };
          return [...filtered, finalMessage];
        });
        devLog('🎯 Interview completed (no audio), redirecting to feedback...');
        window.location.href = `/interview-feedback?interview_id=${interviewId}`;
      }
    };

    run();
  }, [setConversation, setCurrentAudioElement, setIsAudioPlaying]);

  const trackInterviewCompletionEvents = useCallback((interviewId, interview_done, feedback_saved_successfully, completionMethod) => {
    if (!interview_done) {
      return;
    }

    trackEvents.participatedInMockInterview({
      interview_id: interviewId,
      completion_timestamp: new Date().toISOString(),
      completion_method: completionMethod,
    });

    if (feedback_saved_successfully) {
      setTimeout(() => {
        trackEvents.mockInterviewFeedbackGenerated({
          interview_id: interviewId,
          generation_timestamp: new Date().toISOString(),
          generation_method: completionMethod,
        });
      }, 100);
    }
  }, []);

  // Function to call Interview Manager API
  const callInterviewManager = async (userInput) => {
    try {
      devLog('🤖 Calling Interview Manager API with:', userInput);
      devLog('🔍 Current state before API call:', {
        interviewStage,
        hasAnsweredResumeQuestion,
        canEndInterview
      });
      
      // ✅ Get interview_id from URL
      const urlParams = new URLSearchParams(window.location.search);
      const interviewId = urlParams.get('interview_id');
      
      if (!interviewId) {
        console.error('❌ No interview_id found in URL');
        return;
      }
      
      let response = null;
      const liveStreamId = `stream-${Date.now()}`;
      let sawStreamTokens = false;

      const upsertLiveStreamMessage = (prev, patch) => {
        const cleaned = prev.filter((msg) => !msg.isThinking);
        const idx = cleaned.findIndex((msg) => msg.id === liveStreamId);
        if (idx === -1) {
          return [
            ...cleaned,
            {
              speaker: 'interviewer',
              id: liveStreamId,
              timestamp: new Date().toLocaleTimeString(),
              message: '',
              ...patch,
            },
          ];
        }
        const next = [...cleaned];
        next[idx] = { ...next[idx], ...patch };
        return next;
      };

      try {
        response = await apiPostInterviewStream(
          '/generate-response-stream',
          buildGenerateResponsePayload(userInput),
          {
            onEvent: (eventName, payload) => {
              if (eventName === 'started') {
                devLog('Interview stream started');
                return;
              }
              if (eventName === 'queued') {
                setConversation((prev) =>
                  upsertLiveStreamMessage(prev, {
                    message: payload.message || 'Waiting for interview AI…',
                  }),
                );
                return;
              }
              if (eventName === 'token' && payload.text) {
                sawStreamTokens = true;
                setConversation((prev) => {
                  const existing = prev.find((msg) => msg.id === liveStreamId);
                  const prior = existing?.message || '';
                  const waitingPlaceholder =
                    prior === 'Waiting for interview AI…' ||
                    prior === 'Waiting for interview AI...';
                  const baseMessage = waitingPlaceholder ? '' : prior;
                  return upsertLiveStreamMessage(prev, {
                    message: `${baseMessage}${payload.text}`,
                  });
                });
              }
            },
          },
        );
      } catch (streamErr) {
        if (streamErr.busy) {
          throw streamErr;
        }
        devLog('Stream unavailable, falling back to POST', streamErr.message);
      }

      if (!response) {
        response = await apiPost(
          '/generate-response',
          buildGenerateResponsePayload(userInput),
          { timeoutMs: GENERATE_RESPONSE_TIMEOUT_MS },
        );
      }

      devLog('📥 Interview Manager response:', response);
      
      if (response.success) {
        const {
          response: textResponse,
          audio_url,
          should_delete_audio,
          stage,
          interview_done,
          requires_code,
          code_language,
          awaiting_manual_end,
        } = response.data;
        
        devLog('🔍 Response data:', {
          stage,
          interview_done,
          awaiting_manual_end,
          userInput: userInput.trim(),
          currentInterviewStage: interviewStage
        });

        devLog('Question Requires Code: ', requires_code);
        
        const answeredResumeQuestion = interviewStage === 'resume_discussion' && userInput.trim().length > 0;
        const nextHasAnsweredResumeQuestion = hasAnsweredResumeQuestion || answeredResumeQuestion;
        const nextAwaitingManualEnd = !!awaiting_manual_end;

        // ✅ NEW: Track when user answers resume questions (check current stage before updating)
        if (answeredResumeQuestion) {
          devLog('✅ User answered resume question - marking as answered');
          setHasAnsweredResumeQuestion(true);
        }

        setAwaitingManualEnd(nextAwaitingManualEnd);
        if (nextAwaitingManualEnd) {
          setCanEndInterview(true);
          setIsRecording(false);
        }

        if (requires_code) {
            devLog('🔧 Coding question detected, auto-opening code editor');
            setCurrentQuestion({
                question_text: textResponse,
                requires_code: true,
                code_language: code_language
            });
            setIsCodingQuestion(true);
            setShowCodeEditor(true);
        } else {
            setCurrentQuestion(null);
            setIsCodingQuestion(false);
            setCodeToAppend('');
            setLanguage('javascript');
        }
        
        // ✅ NEW: Update interview stage and control End Interview button
        if (stage) {
          devLog('📊 Interview stage updated from', interviewStage, 'to:', stage);

          const nextEndState = resolveEndInterviewState(stage, nextHasAnsweredResumeQuestion);
          setInterviewStage(nextEndState.interviewStage);
          setHasAnsweredResumeQuestion(nextEndState.hasAnsweredResumeQuestion);
          setCanEndInterview(nextAwaitingManualEnd || nextEndState.canEndInterview);

          if (nextAwaitingManualEnd || nextEndState.canEndInterview) {
            devLog('✅ End Interview button enabled');
          } else {
            devLog('⏳ End Interview button remains disabled', {
              stage,
              hasAnsweredResumeQuestion: nextHasAnsweredResumeQuestion,
            });
          }
        }
        
        if (!sawStreamTokens) {
          setConversation((prev) => prev.filter((msg) => !msg.isThinking && msg.id !== liveStreamId));
          await addMessageToConversation('interviewer', textResponse);
        }

        if (audio_url) {
          try {
            await playInterviewerResponseAudio(audio_url, should_delete_audio);
          } catch (error) {
            console.error('❌ Audio playback failed:', error);
          }
        } else {
          devLog('ℹ️ No audio URL provided in response');
        }

        setIsResponseInProgress(false);
      } else {
        console.error('❌ Interview Manager API error:', response.message);
        setConversation(prev => prev.filter(msg => !msg.isThinking));
        setIsResponseInProgress(false);
      }
    } catch (error) {
      console.error('❌ Error calling Interview Manager:', error);
      if (error.busy) {
        await addMessageToConversation(
          'interviewer',
          error.message || 'The interview AI is busy. Please wait a few seconds and try again.',
        );
      }
      setConversation(prev => prev.filter(msg => !msg.isThinking));
      setIsResponseInProgress(false);
    }
  };

  // Update the handleEndInterview function
  const handleEndInterview = async () => {
    const confirmed = window.confirm('Are you sure you want to end the interview? This action cannot be undone.');
    
    if (confirmed) {
      devLog('✅ User confirmed ending interview');

      const urlParams = new URLSearchParams(window.location.search);
      const interviewId = urlParams.get('interview_id');

      if (interviewId) {
        try {
          devLog('🗑️ Deleting chat history for interview:', interviewId);
          await deleteChatHistory(interviewId);
          devLog('✅ Chat history deleted successfully');
        } catch (error) {
          console.error('❌ Failed to delete chat history:', error);
        }
      }
      
      setIsEndingInterview(true);
      setAwaitingManualEnd(false);
      
      try {
        devLog('📤 Sending END_INTERVIEW command to backend...');
        
        if (!interviewId) {
          console.error('❌ No interview_id found in URL');
          setIsEndingInterview(false);
          return;
        }
        
        const response = await apiPost(
          '/generate-response',
          buildGenerateResponsePayload('END_INTERVIEW'),
          { timeoutMs: GENERATE_RESPONSE_TIMEOUT_MS },
        );
        
        devLog('📥 End interview response:', response);
        
        if (response.success) {
          const { response: textResponse, audio_url, should_delete_audio, interview_done, feedback_saved_successfully } = response.data;

          trackInterviewCompletionEvents(
            interviewId,
            interview_done,
            feedback_saved_successfully,
            'backend_confirmed',
          );

          processEndInterviewResponse({
            interviewId,
            textResponse,
            audio_url,
            should_delete_audio,
            interview_done,
          });
        } else {
          console.error('❌ End interview API error:', response.message);
          setIsEndingInterview(false);
        }
      } catch (error) {
        console.error('❌ Error ending interview:', error);
        setIsEndingInterview(false);
        const urlParamsOnError = new URLSearchParams(window.location.search);
        const interviewIdOnError = urlParamsOnError.get('interview_id');
        if (interviewIdOnError && window.confirm(
          'Ending the interview failed or timed out. Open the feedback page anyway?'
        )) {
          window.location.href = `/interview-feedback?interview_id=${interviewIdOnError}`;
        }
      }
    }
  };

  // Update the toggleRecording function (around line 266)
  const toggleRecording = async () => {
    if (awaitingManualEnd && !isRecording) {
      return;
    }
    if (isRecording) {
      // Stop recording
      devLog('🛑 Stopping recording...');
      setIsRecording(false);
      setCanEndInterview(true); // ✅ NEW: Re-enable end interview button when recording stops
      setIsLoading(true);
      devLog('🔄 Loading state set to true');
      
      try {
        // Stop the media recorder
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
          mediaRecorderRef.current.stop();
        }
        
        // Wait for the recording to finish
        await new Promise((resolve) => {
          if (mediaRecorderRef.current) {
            mediaRecorderRef.current.onstop = resolve;
          } else {
            resolve();
          }
        });
        
        // Create audio blob from chunks
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        audioChunksRef.current = []; // Reset chunks
        
        // Stop the media stream
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }
        
        devLog('🎵 Audio recording completed, blob size:', audioBlob.size, 'bytes');
        
        // Send audio to backend for transcription
        devLog('📤 Sending audio to backend for transcription...');
        try {
          const wavBlob = await convertToWav(audioBlob);
          const formData = new FormData();
          formData.append('audio', wavBlob, 'recording.wav');
          
          // Get interview_id from URL
          const urlParams = new URLSearchParams(window.location.search);
          const interviewId = urlParams.get('interview_id');

          if (interviewId) {
            formData.append('interview_id', interviewId);
          }

          const result = await uploadFile('/api/transcribe-audio', formData);
          
          devLog('📥 Backend response:', result);
          
          if (result.success) {
            const transcription = result.data.transcription;
            setCodeToAppend('');
            setLanguage('javascript');
            if (transcription && transcription.trim()) {
              // Add candidate's response to conversation
              await addMessageToConversation('candidate', transcription);
              devLog('✅ Candidate message added');
              setIsLoading(false); // Stop loading immediately after user message appears

              setIsResponseInProgress(true); // ✅ NEW: Start response process
              await callInterviewManager(transcription);
              
            } else {
              // No speech detected
              devLog('⚠️ No speech detected');
              const newMessage = {
                id: Date.now(), // Use timestamp as unique ID
                speaker: 'candidate',
                message: '[No speech detected]',
                timestamp: new Date().toLocaleTimeString()
              };
              setConversation(prev => [...prev, newMessage]);
              setIsLoading(false);
            }
          } else {
            console.error('❌ Transcription failed:', result.message);
            // Add error message to conversation
            const errorMessage = {
              id: Date.now(), // Use timestamp as unique ID
              speaker: 'system',
              message: `Transcription failed: ${result.message || 'Unknown error'}`,
              timestamp: new Date().toLocaleTimeString()
            };
            setConversation(prev => [...prev, errorMessage]);
            setIsLoading(false);
          }
        } catch (error) {
          console.error('❌ Error during transcription:', error);
          // Add error message to conversation
          const errorMessage = {
            id: Date.now(), // Use timestamp as unique ID
            speaker: 'system',
            message: `Transcription error: ${error.message || 'Unknown error'}`,
            timestamp: new Date().toLocaleTimeString()
          };
          setConversation(prev => [...prev, errorMessage]);
          setIsLoading(false);
        }
        
      } catch (error) {
        console.error('❌ Error stopping recording:', error);
        setIsLoading(false);
      }
      
    } else {
      // Start recording
      devLog('🎙️ Starting recording...');
      setIsRecording(true);
      setCanEndInterview(false); // ✅ NEW: Disable end interview button when recording starts
      
      // ✅ RESTORED: Disable button for 3 seconds to prevent edge cases
      setIsButtonDisabled(true);
      setTimeout(() => {
        setIsButtonDisabled(false);
      }, 1500);
      
      try {
        const stream = await requestUserMedia({
          audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true
          } 
        });
        
        streamRef.current = stream;
        
        // ✅ FIXED: Use audio/webm format which is more compatible
        const mediaRecorder = new MediaRecorder(stream, {
          mimeType: 'audio/webm;codecs=opus',
          audioBitsPerSecond: 128000
        });
        
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];
        
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };
        
        mediaRecorder.start();
        devLog('✅ Recording started successfully');
        
      } catch (error) {
        console.error('❌ Failed to start recording:', error);
        const errorMessage = {
          id: Date.now(),
          speaker: 'system',
          message:
            error.name === 'MediaDevicesUnsupported' || error.name === 'MediaDevicesUnavailable'
              ? getMediaAccessErrorMessage('audio')
              : `Microphone error: ${error.message || 'Unknown error'}`,
          timestamp: new Date().toLocaleTimeString()
        };
        setConversation(prev => [...prev, errorMessage]);
        setIsRecording(false);
        setCanEndInterview(true); // ✅ NEW: Re-enable button if recording fails
        setIsButtonDisabled(false); // ✅ RESTORED: Re-enable button if recording fails
      }
    }
  };

  // ✅ NEW: Add audio conversion function
  const convertToWav = async (audioBlob) => {
    try {
      // Create an audio context
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Convert blob to array buffer
      const arrayBuffer = await audioBlob.arrayBuffer();
      
      // Decode the audio
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      
      // Convert to WAV format
      const wavBuffer = audioBufferToWav(audioBuffer);
      
      return new Blob([wavBuffer], { type: 'audio/wav' });
    } catch (error) {
      console.error('❌ Audio conversion failed:', error);
      // Fallback: return original blob if conversion fails
      return audioBlob;
    }
  };

  // ✅ NEW: Audio buffer to WAV conversion with proper header
  const audioBufferToWav = (buffer) => {
    const length = buffer.length;
    const numberOfChannels = buffer.numberOfChannels;
    const sampleRate = buffer.sampleRate;
    
    // Calculate buffer size correctly
    const bufferSize = 44 + length * numberOfChannels * 2;
    const arrayBuffer = new ArrayBuffer(bufferSize);
    const view = new DataView(arrayBuffer);
    
    // Helper function to write strings
    const writeString = (offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };
    
    // Write WAV file header (44 bytes)
    writeString(0, 'RIFF');                    // Chunk ID
    view.setUint32(4, bufferSize - 8, true);  // Chunk size (file size - 8)
    writeString(8, 'WAVE');                    // Format
    writeString(12, 'fmt ');                   // Subchunk1 ID
    view.setUint32(16, 16, true);             // Subchunk1 size (16 for PCM)
    view.setUint16(20, 1, true);              // Audio format (1 = PCM)
    view.setUint16(22, numberOfChannels, true); // Number of channels
    view.setUint32(24, sampleRate, true);     // Sample rate
    view.setUint32(28, sampleRate * numberOfChannels * 2, true); // Byte rate
    view.setUint16(32, numberOfChannels * 2, true); // Block align
    view.setUint16(34, 16, true);             // Bits per sample
    writeString(36, 'data');                   // Subchunk2 ID
    view.setUint32(40, length * numberOfChannels * 2, true); // Subchunk2 size
    
    // Write audio data
    let offset = 44;
    for (let i = 0; i < length; i++) {
      for (let channel = 0; channel < numberOfChannels; channel++) {
        const sample = Math.max(-1, Math.min(1, buffer.getChannelData(channel)[i]));
        // Convert float to 16-bit integer
        const sample16 = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(offset, sample16, true);
        offset += 2;
      }
    }
    
    return arrayBuffer;
  };

  // Add the loading popup component
  const LoadingPopup = () => {
    if (!isEndingInterview) return null;
    
    return (
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-300">
        <div className="bg-white/95 backdrop-blur-md rounded-2xl p-8 max-w-md mx-4 text-center shadow-2xl border border-gray-200/50 animate-in zoom-in-95 duration-300">
          {/* Animated Icon */}
          <div className="relative mb-6">
            <div className="w-16 h-16 mx-auto relative">
              {/* Outer ring */}
              <div className="absolute inset-0 rounded-full border-4 border-blue-100 animate-pulse"></div>
              {/* Spinning ring */}
              <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-600 border-r-blue-500 animate-spin"></div>
              {/* Inner circle */}
              <div className="absolute inset-2 rounded-full bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center">
                <div className="w-3 h-3 bg-blue-600 rounded-full animate-ping"></div>
              </div>
            </div>
          </div>

          {/* Title */}
          <h3 className="text-xl font-bold text-gray-900 mb-3 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Ending Interview
          </h3>

          {/* Progress Steps */}
          <div className="space-y-3 mb-6">
            <div className="flex items-center justify-center space-x-3 text-sm">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-gray-600">Generating interview summary...</span>
            </div>
            <div className="flex items-center justify-center space-x-3 text-sm">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              <span className="text-gray-600">Saving feedback and evaluation...</span>
            </div>
            <div className="flex items-center justify-center space-x-3 text-sm">
              <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse"></div>
              <span className="text-gray-600">Preparing your results...</span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-gray-200 rounded-full h-2 mb-4 overflow-hidden">
            <div className="h-2 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 rounded-full animate-pulse" 
                 style={{ width: '100%' }}></div>
          </div>

          {/* Message */}
          <p className="text-gray-600 text-sm leading-relaxed">
            Please wait while we process your interview data and generate comprehensive feedback.
          </p>
          
          {/* Subtitle */}
          <p className="text-xs text-gray-500 mt-3 font-medium">
            This usually takes 10-15 seconds
          </p>

          {/* Decorative Elements */}
          <div className="absolute top-4 right-4">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
          </div>
          <div className="absolute bottom-4 left-4">
            <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '200ms' }}></div>
          </div>
          <div className="absolute top-4 left-4">
            <div className="w-2 h-2 bg-pink-400 rounded-full animate-bounce" style={{ animationDelay: '400ms' }}></div>
          </div>
          <div className="absolute bottom-4 right-4">
            <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '600ms' }}></div>
          </div>
        </div>
      </div>
    );
  };

  // Update the useChatHistory hook usage
  // Load chat history when component mounts
  useEffect(() => {
    const loadHistory = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const interviewId = urlParams.get('interview_id');
      if (interviewId) {
        const result = await loadChatHistory(interviewId);
        if (result?.conversation?.length > 0) {
          setConversation(result.conversation);
        }
        if (result) {
          const restored = resolveEndInterviewState(
            result.interviewStage,
            result.hasAnsweredResumeQuestion,
          );
          const nextAwaitingManualEnd = !!result.awaitingManualEnd;
          setInterviewStage(restored.interviewStage);
          setHasAnsweredResumeQuestion(restored.hasAnsweredResumeQuestion);
          setAwaitingManualEnd(nextAwaitingManualEnd);
          setCanEndInterview(nextAwaitingManualEnd || restored.canEndInterview);
          devLog('♻️ Restored interview UI state after refresh:', {
            ...restored,
            awaitingManualEnd: nextAwaitingManualEnd,
          });
        }
      }
    };
    
    loadHistory();
  }, [loadChatHistory, setConversation]);

  // Function to add a message locally. The backend owns chat-history persistence
  // for interview turns, which avoids duplicate rows after refresh.
  const addMessageToConversation = useCallback(async (speaker, message) => {
    // Add to local state immediately
    const newMessage = {
      id: Date.now(),
      speaker,
      message,
      timestamp: new Date().toLocaleTimeString()
    };
    
    setConversation(prev => [...prev, newMessage]);
  }, [setConversation]);

  // Update your existing message handling functions to use addMessageToConversation
  // The callInterviewManager function already uses addMessageToConversation internally
  // The handleEndInterview function already uses addMessageToConversation internally

  const handleSave = async (code) => {
      // ✅ ADD: Validate code is not empty
      if (!code || !code.trim()) {
        console.error('❌ Cannot save empty code');
        // Show error to user
        const errorMessage = {
          id: `error-${Date.now()}`,
          speaker: 'system',
          message: 'Please enter some code before submitting.',
          timestamp: new Date().toLocaleTimeString(),
          isError: true
        };
        setConversation(prev => [...prev, errorMessage]);
        return;
      }
      
      // ✅ ADD: Validate code is not just whitespace or comments
      const codeWithoutComments = code
        .replace(/\/\/.*$/gm, '') // Remove single-line comments
        .replace(/\/\*[\s\S]*?\*\//g, '') // Remove multi-line comments
        .trim();
      
      if (!codeWithoutComments) {
        console.error('❌ Code contains only comments');
        const errorMessage = {
          id: `error-${Date.now()}`,
          speaker: 'system',
          message: 'Please enter actual code, not just comments.',
          timestamp: new Date().toLocaleTimeString(),
          isError: true
        };
        setConversation(prev => [...prev, errorMessage]);
        return;
      }
      
      devLog('💾 Saving code:', code);
      
      // Trim the code
      const trimmedCode = code.trim();
      
      setCodeToAppend(''); // Clear the code for next question
      
      // Format code with markdown
      const formattedCode = '\n``` \n\n' + trimmedCode + '\n\n```\n';
      
      // Add user message to conversation
      await addMessageToConversation('candidate', formattedCode);
      devLog('✅ Candidate message added');
      
      setIsLoading(false); // Stop loading immediately after user message appears

      // ✅ ENSURE: Call Interview Manager API to get the next question/response
      setIsResponseInProgress(true);
      
      try {
        await callInterviewManager(formattedCode);
        devLog('✅ Interview Manager API called successfully');
      } catch (error) {
        console.error('❌ Error calling Interview Manager:', error);
        // Remove thinking message and show error
        setConversation(prev => prev.filter(msg => !msg.isThinking));
        const errorMessage = {
          id: `error-${Date.now()}`,
          speaker: 'system',
          message: 'Failed to submit code. Please try again.',
          timestamp: new Date().toLocaleTimeString(),
          isError: true
        };
        setConversation(prev => [...prev, errorMessage]);
        setIsResponseInProgress(false);
      }
  };

  const handleEditorClose = async (code, newLanguage) => {
        devLog("Code to Append: ", code);
        setCodeToAppend(code);
        devLog(newLanguage);
        setLanguage(newLanguage);
  };

  const isInputLocked = awaitingManualEnd;
  const isMicDisabled =
    isInputLocked || isButtonDisabled || isAudioPlaying || isLoading || isResponseInProgress;
  // Option B: once Q&A is done, keep End Interview clickable (only block while ending).
  const isEndInterviewDisabled = awaitingManualEnd
    ? isEndingInterview
    : !canEndInterview || isAudioPlaying || isRecording || isLoading || isResponseInProgress;

  return (
    <div 
      className="h-full flex flex-col p-4 lg:p-5 min-h-0"
      style={{ 
        backgroundColor: 'var(--color-card)',
      }}
    >
      {/* Header with Title and Buttons */}
      <div className="flex flex-col gap-3 mb-4 shrink-0">
        <div className="flex flex-row flex-wrap items-center justify-between gap-3">
          <h2 
            className="text-base sm:text-lg md:text-xl font-bold tracking-tight min-w-0"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Interview Conversation
          </h2>
          
          {/* End Interview */}
          <button
            type="button"
            onClick={handleEndInterview}
            disabled={isEndInterviewDisabled}
            className={`group relative shrink-0 inline-flex items-center justify-center gap-2 overflow-hidden rounded-full px-4 py-2 sm:px-5 sm:py-2.5 text-[13px] sm:text-sm font-medium tracking-tight transition-all duration-300 ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-error)]/35 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-card)] ${
              isEndInterviewDisabled
                ? 'cursor-not-allowed border border-[var(--color-border)]/80 bg-[var(--color-input-bg)]/25 text-[var(--color-text-secondary)]/40 shadow-none'
                : 'border border-[color-mix(in_srgb,var(--color-error)_22%,var(--color-border))] bg-[color-mix(in_srgb,var(--color-error)_8%,var(--color-card))] text-[color-mix(in_srgb,var(--color-error)_88%,var(--color-text-primary))] shadow-[inset_0_1px_0_color-mix(in_srgb,#fff_18%,transparent),0_1px_2px_color-mix(in_srgb,var(--color-error)_8%,transparent)] hover:border-[var(--color-error)] hover:bg-[var(--color-error)] hover:text-white hover:shadow-[0_8px_24px_color-mix(in_srgb,var(--color-error)_26%,transparent)] active:brightness-[0.97]'
            }`}
            title={
              isEndInterviewDisabled
                ? (isEndingInterview ? "Ending interview..." :
                   isRecording ? "Wait for recording to finish" : 
                   isLoading ? "Wait for response to generate" : 
                   isResponseInProgress ? "Response in progress..." : 
                   isAudioPlaying ? "Wait for audio to finish" :
                   interviewStage === 'introduction' ? "Complete the introduction first" : 
                   interviewStage === 'resume_discussion' && !hasAnsweredResumeQuestion ? "Answer at least one resume & JD related question to end interview" : "Wait for resume questions to begin")
                : "End Interview"
            }
          >
            <span
              aria-hidden="true"
              className={`h-1.5 w-1.5 shrink-0 rounded-full transition-all duration-300 ${
                isEndInterviewDisabled
                  ? 'bg-[var(--color-text-secondary)]/25'
                  : 'bg-[var(--color-error)] group-hover:bg-white/90 group-hover:shadow-[0_0_8px_rgba(255,255,255,0.45)]'
              }`}
            />
            <span className="hidden sm:inline">End interview</span>
            <span className="sm:hidden">End</span>
          </button>
        </div>
        
        {/* Primary speak control */}
        <div className="flex items-center justify-center">
          <button
            type="button"
            onClick={toggleRecording}
            disabled={isMicDisabled}
            className={`w-full max-w-md px-5 sm:px-8 py-3.5 sm:py-4 rounded-2xl flex items-center justify-center gap-2 sm:gap-3 text-white font-semibold transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] ${
              isMicDisabled
                ? 'bg-gray-400 cursor-not-allowed opacity-60'
                : isRecording 
                  ? 'bg-red-500 hover:bg-red-600' 
                  : 'bg-blue-500 hover:bg-blue-600'
            }`}
            title={
              isMicDisabled
                ? (isInputLocked
                    ? 'Interview finished — press End Interview for feedback'
                    : isAudioPlaying
                      ? 'Wait for audio to finish'
                      : isLoading
                        ? 'Generating response...'
                        : isResponseInProgress
                          ? 'Response in progress...'
                          : 'Button temporarily disabled')
                : (isRecording ? 'Stop Recording' : 'Speak Now')
            }
          >
            {isRecording ? <MicOff size={18} className="sm:w-5 sm:h-5" /> : <Mic size={18} className="sm:w-5 sm:h-5" />}
            <span className="text-sm font-medium">
              {isMicDisabled
                ? (isInputLocked
                    ? 'Press End Interview'
                    : isAudioPlaying
                      ? 'Audio Playing...'
                      : isLoading
                        ? 'Generating...'
                        : isResponseInProgress
                          ? 'Response in progress...'
                          : 'Please Wait...')
                : (isRecording ? 'Stop Recording' : 'Speak Now')
              }
            </span>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div 
        ref={messagesContainerRef}  // ✅ NEW: Add ref to messages container
        className="flex-1 overflow-y-auto space-y-3 sm:space-y-4 mb-3 pr-1 sm:pr-2 min-h-0"
      >
        <AnimatePresence>
          {conversation.map((message, index) => (
            <motion.div
              key={message.id ?? `msg-${index}`}
              initial={
                typeof message.id === 'string' && message.id.startsWith('stream-')
                  ? false
                  : { opacity: 0, y: 20 }
              }
              animate={{ 
                opacity: 1,
                y: message.isThinking ? [-3, 3] : 0
              }}
              transition={{ 
                duration: message.isThinking ? 1 : 0.3,
                repeat: message.isThinking ? Infinity : 0,
                ease: "easeInOut",
                repeatType: "reverse"
              }}
              className={`flex ${message.speaker === 'interviewer' ? 'justify-start' : 'justify-end'}`}
            >
              <div
                className={`max-w-[90%] sm:max-w-[85%] rounded-xl sm:rounded-2xl shadow-lg ${
                  message.isThinking
                    ? 'p-3 sm:p-4 md:p-5 border-2 sm:border-3 border-[var(--color-primary)]'
                    : 'p-3 sm:p-4 md:p-5 border border-[var(--color-border)]'
                } ${
                  message.speaker === 'candidate' ? 'border border-[var(--color-primary)]' : ''
                }`}
                style={{
                  backgroundColor: message.speaker === 'interviewer' 
                    ? 'var(--color-input-bg)' 
                    : 'var(--color-primary)',
                  color: message.speaker === 'interviewer' 
                    ? 'var(--color-text-primary)' 
                    : 'white',
                }}
              >
                <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 mb-2 sm:mb-3">
                  <span 
                    className={`text-xs font-bold px-2 sm:px-3 py-1 rounded-full tracking-wide ${
                      message.speaker === 'interviewer'
                        ? 'bg-[var(--color-border)] text-[var(--color-text-secondary)]'
                        : 'bg-white/20 text-white'
                    }`}
                  >
                    {message.speaker === 'interviewer' ? 'INTERVIEWER' : 'YOU'}
                  </span>
                  <span 
                    className="text-xs font-medium opacity-70"
                    style={{ color: message.speaker === 'interviewer' ? 'var(--color-text-secondary)' : 'rgba(255,255,255,0.7)' }}
                  >
                    {message.timestamp}
                  </span>
                </div>
                <p className="text-xs sm:text-sm md:text-base leading-relaxed font-medium">{message.message}</p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {/* Loading indicator for new messages */}
        {isLoading && (
          <motion.div
            key="loading-indicator"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex justify-end"
          >
            <div 
              className="max-w-[90%] sm:max-w-[85%] p-3 sm:p-4 rounded-lg border"
              style={{ 
                backgroundColor: 'var(--color-primary)',
                borderColor: 'var(--color-primary)',
                color: 'white'
              }}
            >
              <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 mb-2">
                <span 
                  className="text-xs font-bold px-2 sm:px-3 py-1 rounded-full tracking-wide"
                  style={{ 
                    backgroundColor: 'rgba(255,255,255,0.2)',
                    color: 'white'
                  }}
                >
                  YOU
                </span>
                <span 
                  className="text-xs"
                  style={{ color: 'rgba(255,255,255,0.8)' }}
                >
                  Processing audio...
                </span>
              </div>
              <div className="flex space-x-1">
                <div 
                  className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full animate-bounce"
                  style={{ backgroundColor: 'rgba(255,255,255,0.8)' }}
                ></div>
                <div 
                  className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full animate-bounce" 
                  style={{ 
                    backgroundColor: 'rgba(255,255,255,0.8)',
                    animationDelay: '0.1s' 
                  }}
                ></div>
                <div 
                  className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full animate-bounce" 
                  style={{ 
                    backgroundColor: 'rgba(255,255,255,0.8)',
                    animationDelay: '0.2s' 
                  }}
                ></div>
              </div>
            </div>
          </motion.div>
        )}
        
        {/* Auto-scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Instructions */}
      <div 
        className="text-center border-t pt-3 sm:pt-4"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <p 
          className="text-xs sm:text-sm"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {isInputLocked
            ? 'Interview complete — press End Interview for your feedback'
            : isRecording 
              ? 'Click to stop recording and submit your response'
              : 'Click to start recording your response'
          }
        </p>
      </div>

      {/* Session Info */}
      <div 
        className="flex items-center justify-between text-xs pt-2 border-t mt-3 sm:mt-4"
        style={{ 
          color: 'var(--color-text-secondary)',
          borderColor: 'var(--color-border)' 
        }}
      >
      </div>

      {/* Code Editor Button - Only show when current question requires code */}
      {isCodingQuestion && (
        <div className="pt-3 sm:pt-4">
          <button
            onClick={() => setShowCodeEditor(true)}
            disabled={isMicDisabled}
            className={`w-full px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 text-white font-semibold transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 ${
              isMicDisabled
                ? 'bg-gray-400 cursor-not-allowed opacity-60'
                : 'bg-purple-500 hover:bg-purple-600'
            }`}
            title={
              isMicDisabled
                ? 'Please wait...'
                : `Open Code Editor`
            }
          >
            <Code size={18} className="w-4 h-4" />
            <span className="text-sm font-medium">
              Open Code Editor {currentQuestion.code_language && `(${currentQuestion.code_language.toUpperCase()})`}
            </span>
          </button>
        </div>
      )}

      {/* ✅ NEW: Loading popup */}
      <LoadingPopup />

      {/* ✅ NEW: Code Editor Popup */}
      <AnimatePresence>
        {showCodeEditor && (
          <CodeEditorPopup
            isOpen={showCodeEditor}
            onClose={() => setShowCodeEditor(false)}
            initialLanguage={currentQuestion?.code_language || language}
            questionText={currentQuestion?.question_text}
            handleEditorSave = {handleSave}
            maintainCodeAndLang = {handleEditorClose}
            initialEditorCode = {codeToAppend}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export default React.memo(ChatWindow);
