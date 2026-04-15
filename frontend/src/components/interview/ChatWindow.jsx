import React, { useState, useRef, useEffect, useContext, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Square, Code } from 'lucide-react'; // ✅ Add Square icon for end button
import { uploadFile, apiPost, apiDelete } from '../../api';
import { useAuth } from '../../contexts/AuthContext'; // ✅ Use useAuth hook
import { supabase } from '../../supabaseClient'; // ✅ Import supabase client

import { useChatHistory } from '../../hooks/useChatHistory';

import { trackEvents } from '../../services/mixpanel';
import CodeEditorPopup from './CodeEditorPopup';

function ChatWindow({ conversation, setConversation, isLoading, setIsLoading, isAudioPlaying, setIsAudioPlaying, onStateChange }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isButtonDisabled, setIsButtonDisabled] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  
  // ✅ Use useAuth hook to get user
  const { user } = useAuth();

  // Add this state for loading
  const [isEndingInterview, setIsEndingInterview] = useState(false);
  const [currentAudioElement, setCurrentAudioElement] = useState(null);
  const [canEndInterview, setCanEndInterview] = useState(false); // Start disabled
  const [isResponseInProgress, setIsResponseInProgress] = useState(false);
  
  // ✅ NEW: Add state for timeout modal
  const [showTimeoutModal, setShowTimeoutModal] = useState(false);
  
  // ✅ NEW: Add state to track interview stage and resume question answers
  const [interviewStage, setInterviewStage] = useState('introduction');
  const [hasAnsweredResumeQuestion, setHasAnsweredResumeQuestion] = useState(false);

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
    // ✅ FIXED: Scroll only the messages container
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  }, [conversation]);

  // Cleanup function to stop media stream when component unmounts
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      // ✅ NEW: Clean up audio state
      if (currentAudioElement) {
        currentAudioElement.pause();
        currentAudioElement.currentTime = 0;
      }
      setIsAudioPlaying(false);
      setCurrentAudioElement(null);
      // ✅ FIXED: Don't unconditionally enable button - let stage logic handle it
    };
  }, []);

  // Debug loading state changes
  useEffect(() => {
    console.log('🔄 Loading state changed to:', isLoading);
  }, [isLoading]);

  // Notify parent component of state changes for head tracking toggle
  useEffect(() => {
    if (onStateChange) {
      onStateChange({
        isRecording,
        isResponseInProgress,
        canEndInterview
      });
    }
  }, [isRecording, isResponseInProgress, canEndInterview, onStateChange]);

  // Function to call Interview Manager API
  const callInterviewManager = async (userInput) => {
    try {
      console.log('🤖 Calling Interview Manager API with:', userInput);
      console.log('🔍 Current state before API call:', {
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
      
      const response = await apiPost('/api/generate-response', {
        message: userInput,
        interview_id: interviewId // ✅ Send interview_id to backend
      });

      console.log('📥 Interview Manager response:', response);
      
      if (response.success) {
        const { response: textResponse, audio_url, should_delete_audio, stage, interview_done, requires_code, code_language } = response.data;
        
        console.log('🔍 Response data:', {
          stage,
          interview_done,
          userInput: userInput.trim(),
          currentInterviewStage: interviewStage
        });

        console.log('Question Requires Code: ', requires_code);
        
        // ✅ NEW: Track when user answers resume questions (check current stage before updating)
        if (interviewStage === 'resume_discussion' && userInput.trim().length > 0) {
          console.log('✅ User answered resume question - marking as answered');
          setHasAnsweredResumeQuestion(true);
        }

        if (requires_code) {
            console.log('🔧 Coding question detected, auto-opening code editor');
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
          console.log('📊 Interview stage updated from', interviewStage, 'to:', stage);
          setInterviewStage(stage);
          
          // ✅ NEW: Auto-trigger end interview flow when timeout is detected
          if (stage === 'timeout') {
            console.log('⏰ Timeout detected - showing timeout modal...');
            // Show timeout modal first
            setShowTimeoutModal(true);
            return; // Exit early to prevent normal message handling
          }
          
          // Enable End Interview button only when user has answered at least one resume question
          if (stage === 'resume_discussion' && hasAnsweredResumeQuestion) {
            console.log('✅ Resume question answered - enabling End Interview button');
            setCanEndInterview(true);
          } else if (stage === 'custom_questions' || stage === 'candidate_questions' || stage === 'wrapup_evaluation' || stage === 'manual_end' || stage === 'timeout') {
            console.log('✅ Later stage reached - enabling End Interview button');
            setCanEndInterview(true);
          } else {
            console.log('⏳ Waiting for resume question answer - keeping End Interview button disabled');
            console.log('🔍 Debug info:', {
              stage,
              hasAnsweredResumeQuestion,
              isResumeDiscussion: stage === 'resume_discussion'
            });
            setCanEndInterview(false);
          }
        }
        
        // ✅ FIXED: Preload audio first, then show text and play simultaneously
        if (audio_url) {
          console.log('🔊 Preloading audio response:', audio_url);
          const audio = new Audio(audio_url);
          
          // Preload the audio
          audio.preload = 'auto';
          
          // ✅ FIX: Add flag to prevent duplicate message addition
          let messageAdded = false;
          
          // Wait for audio to be ready, then show text and play simultaneously
          const playAudioWhenReady = () => {
            // ✅ Prevent duplicate calls
            if (messageAdded) {
              console.log('⚠️ playAudioWhenReady already called, skipping duplicate');
              return;
            }
            messageAdded = true;
            
            // ✅ Remove thinking message right before showing the response
            setConversation(prev => {
              const filtered = prev.filter(msg => !msg.isThinking);
              return filtered;
            });
            
            // Add message and start playing at the same time
            addMessageToConversation('interviewer', textResponse).then(() => {
              console.log('✅ Interviewer response added, starting audio playback');
              
              // Track audio playback state
              setIsAudioPlaying(true);
              setCurrentAudioElement(audio);
              
              // Start playing immediately
              audio.play().catch(error => {
                console.error('❌ Failed to play audio:', error);
                setIsAudioPlaying(false);
                setCurrentAudioElement(null);
                setIsResponseInProgress(false);
              });
            });
          };
          
          // If audio is already loaded, play immediately
          if (audio.readyState >= 2) { // HAVE_CURRENT_DATA or higher
            playAudioWhenReady();
          } else {
            // Wait for audio to be ready
            audio.addEventListener('canplaythrough', playAudioWhenReady, { once: true });
            
            // Fallback: if canplaythrough doesn't fire, wait a bit then play
            setTimeout(() => {
              if (audio.readyState >= 2 && !messageAdded) {
                playAudioWhenReady();
              }
            }, 100);
          }
          
          // ✅ NEW: Delete audio file after playback
          audio.onended = async () => {
            console.log('✅ Audio playback completed');
            setIsAudioPlaying(false);
            setCurrentAudioElement(null);
            setIsResponseInProgress(false);
            
            if (should_delete_audio) {
              try {
                console.log('🗑️ Deleting audio file after playback...');
                console.log('🗑️ Audio URL to delete:', audio_url);
                
                await apiDelete('/api/delete-audio', {
                  body: { audio_url }
                });
                console.log('✅ Audio file deleted successfully');
              } catch (error) {
                console.error('❌ Failed to delete audio file:', error);
                console.error('❌ Error details:', error.message);
              }
            } else {
              console.log('ℹ️ Audio deletion skipped (should_delete_audio is false)');
            }
          };
          
          // ✅ NEW: Handle audio play errors
          audio.onerror = (error) => {
            console.error('❌ Audio playback failed:', error);
            setIsAudioPlaying(false);
            setCurrentAudioElement(null);
            setIsResponseInProgress(false);
            
            // ✅ Remove thinking message before showing text
            setConversation(prev => {
              const filtered = prev.filter(msg => !msg.isThinking);
              return filtered;
            });
            
            // Still show the text even if audio fails
            addMessageToConversation('interviewer', textResponse);
          };
        } else {
          console.log('ℹ️ No audio URL provided in response');
          
          // ✅ Remove thinking message before showing text
          setConversation(prev => {
            const filtered = prev.filter(msg => !msg.isThinking);
            return filtered;
          });
          
          // No audio, just show text
          await addMessageToConversation('interviewer', textResponse);
          setIsResponseInProgress(false);
        }
      } else {
        console.error('❌ Interview Manager API error:', response.message);
      }
    } catch (error) {
      console.error('❌ Error calling Interview Manager:', error);
    }
  };

  // Update the handleEndInterview function
  const handleEndInterview = async () => {
    const confirmed = window.confirm('Are you sure you want to end the interview? This action cannot be undone.');
    
    if (confirmed) {
      console.log('✅ User confirmed ending interview');
      
      // ✅ NEW: Delete chat history for this interview
      const urlParams = new URLSearchParams(window.location.search);
      const interviewId = urlParams.get('interview_id');
      
      if (interviewId) {
        try {
          console.log('🗑️ Deleting chat history for interview:', interviewId);
          await deleteChatHistory(interviewId);
          console.log('✅ Chat history deleted successfully');
        } catch (error) {
          console.error('❌ Failed to delete chat history:', error);
          // Continue with interview ending even if chat history deletion fails
        }
      }
      
      // ✅ NEW: Show loading state
      setIsEndingInterview(true);
      
      try {
        // ✅ NEW: Send END_INTERVIEW command to backend
        console.log('📤 Sending END_INTERVIEW command to backend...');
        
        // Get interview_id from URL
        const urlParams = new URLSearchParams(window.location.search);
        const interviewId = urlParams.get('interview_id');
        
        if (!interviewId) {
          console.error('❌ No interview_id found in URL');
          setIsEndingInterview(false); // Hide loading
          return;
        }
        
        // ✅ Use the same apiPost function that works for normal responses
        const response = await apiPost('/api/generate-response', {
          message: 'END_INTERVIEW',
          interview_id: interviewId
        });
        
        console.log('📥 End interview response:', response);
        
        if (response.success) {
          const { response: textResponse, audio_url, should_delete_audio, interview_done, feedback_saved_successfully } = response.data;
          
          // ✅ FIXED: Track events only when interview is done AND feedback is successfully saved
          if (interview_done) {
            console.log('🎯 Interview completed, tracking events...');
            
            // Track interview completion
            console.log('📊 Tracking participatedInMockInterview...');
            trackEvents.participatedInMockInterview({
              interview_id: interviewId,
              completion_timestamp: new Date().toISOString(),
              completion_method: 'backend_confirmed'
            });
            
            // ✅ FIXED: Only track feedback generation when feedback is actually saved to database
            if (feedback_saved_successfully) {
              console.log('✅ Feedback successfully saved to database, tracking feedback generation...');
              setTimeout(() => {
                console.log('📊 Tracking mockInterviewFeedbackGenerated...');
                trackEvents.mockInterviewFeedbackGenerated({
                  interview_id: interviewId,
                  generation_timestamp: new Date().toISOString(),
                  generation_method: 'backend_confirmed'
                });
              }, 100); // 100ms delay
            } else {
              console.log('⚠️ Interview completed but feedback not saved yet, skipping feedback generation tracking');
            }
          }
          
          // ✅ FIXED: Preload audio first, then show text and play simultaneously
          if (audio_url) {
            console.log('🔊 Preloading final audio response:', audio_url);
            const audio = new Audio(audio_url);
            
            // Preload the audio
            audio.preload = 'auto';
            
            // Wait for audio to be ready, then show text and play simultaneously
            const playFinalAudioWhenReady = () => {
              // ✅ Remove thinking message right before showing the final response
              setConversation(prev => {
                const filtered = prev.filter(msg => !msg.isThinking);
                return filtered;
              });
              
              // Add final message and start playing at the same time
              const finalMessage = {
                id: Date.now(),
                speaker: 'interviewer',
                message: textResponse,
                timestamp: new Date().toLocaleTimeString()
              };
              setConversation(prev => [...prev, finalMessage]);
              
              console.log('✅ Final response added, starting audio playback');
              
              // Track final audio playback state
              setIsAudioPlaying(true);
              setCurrentAudioElement(audio);
              setCanEndInterview(false); // Disable end interview button while final audio plays
              
              // Start playing immediately
              audio.play().catch(error => {
                console.error('❌ Failed to play final audio:', error);
                setIsAudioPlaying(false);
                setCurrentAudioElement(null);
                // Still redirect even if audio fails
                if (interview_done) {
                  window.location.href = `/interview-feedback?interview_id=${interviewId}`;
                }
              });
            };
            
            // If audio is already loaded, play immediately
            if (audio.readyState >= 2) { // HAVE_CURRENT_DATA or higher
              playFinalAudioWhenReady();
            } else {
              // Wait for audio to be ready
              audio.addEventListener('canplaythrough', playFinalAudioWhenReady, { once: true });
              
              // Fallback: if canplaythrough doesn't fire, wait a bit then play
              setTimeout(() => {
                if (audio.readyState >= 2) {
                  playFinalAudioWhenReady();
                }
              }, 100);
            }
            
            audio.onended = async () => {
              console.log('✅ Final audio playback completed');
              setIsAudioPlaying(false);
              setCurrentAudioElement(null);
              setCanEndInterview(true); // Re-enable end interview button
              
              if (should_delete_audio) {
                try {
                  console.log('🗑️ Deleting final audio file after playback...');
                  console.log('🗑️ Final audio URL to delete:', audio_url);
                  
                  await apiDelete('/api/delete-audio', {
                    body: { audio_url }
                  });
                  console.log('✅ Final audio file deleted successfully');
                } catch (error) {
                  console.error('❌ Failed to delete final audio file:', error);
                  console.error('❌ Error details:', error.message);
                }
              }
              
              // ✅ NEW: Redirect to feedback page after audio finishes
              if (interview_done) {
                console.log('🎯 Interview completed, redirecting to feedback...');
                
                // Add a small delay to ensure audio deletion completes
                setTimeout(() => {
                  window.location.href = `/interview-feedback?interview_id=${interviewId}`;
                }, 1000);
              }
            };
            
            // Handle audio errors
            audio.onerror = (error) => {
              console.error('❌ Final audio playback failed:', error);
              setIsAudioPlaying(false);
              setCurrentAudioElement(null);
              
              // ✅ Remove thinking message before showing text
              setConversation(prev => {
                const filtered = prev.filter(msg => !msg.isThinking);
                return filtered;
              });
              
              // Still show the text even if audio fails
              const finalMessage = {
                id: Date.now(),
                speaker: 'interviewer',
                message: textResponse,
                timestamp: new Date().toLocaleTimeString()
              };
              setConversation(prev => [...prev, finalMessage]);
              // Redirect if interview is done
              if (interview_done) {
                window.location.href = `/interview-feedback?interview_id=${interviewId}`;
              }
            };
          } else if (interview_done) {
            // ✅ Remove thinking message before showing final message
            setConversation(prev => {
              const filtered = prev.filter(msg => !msg.isThinking);
              return filtered;
            });
            
            // ✅ NEW: If no audio but interview is done, show message and redirect immediately
            const finalMessage = {
              id: Date.now(),
              speaker: 'interviewer',
              message: textResponse,
              timestamp: new Date().toLocaleTimeString()
            };
            setConversation(prev => [...prev, finalMessage]);
            console.log('🎯 Interview completed (no audio), redirecting to feedback...');
            window.location.href = `/interview-feedback?interview_id=${interviewId}`;
          }
          
        } else {
          console.error('❌ End interview API error:', response.message);
          // ✅ NEW: Hide loading on error
          setIsEndingInterview(false);
        }
      } catch (error) {
        console.error('❌ Error ending interview:', error);
        // ✅ NEW: Hide loading on error
        setIsEndingInterview(false);
      }
    }
  };

  // Update the toggleRecording function (around line 266)
  const toggleRecording = async () => {
    if (isRecording) {
      // Stop recording
      console.log('🛑 Stopping recording...');
      setIsRecording(false);
      setCanEndInterview(true); // ✅ NEW: Re-enable end interview button when recording stops
      setIsLoading(true);
      console.log('🔄 Loading state set to true');
      
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
        
        console.log('🎵 Audio recording completed, blob size:', audioBlob.size, 'bytes');
        
        // Send audio to backend for transcription
        console.log('📤 Sending audio to backend for transcription...');
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
          
          console.log('📥 Backend response:', result);
          
          if (result.success) {
            const transcription = result.data.transcription;
            setCodeToAppend('');
            setLanguage('javascript');
            if (transcription && transcription.trim()) {
              // Add candidate's response to conversation
              await addMessageToConversation('candidate', transcription);
              console.log('✅ Candidate message added');
              setIsLoading(false); // Stop loading immediately after user message appears
              
              // Add thinking indicator before backend call
              const thinkingMessage = {
                id: `thinking-${Date.now()}`,
                speaker: 'interviewer',
                message: 'Thinking...',
                timestamp: new Date().toLocaleTimeString(),
                isThinking: true
              };
              setConversation(prev => [...prev, thinkingMessage]);
              
              // Call Interview Manager API to get the next question/response
              setIsResponseInProgress(true); // ✅ NEW: Start response process
              await callInterviewManager(transcription);
              
            } else {
              // No speech detected
              console.log('⚠️ No speech detected');
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
      console.log('🎙️ Starting recording...');
      setIsRecording(true);
      setCanEndInterview(false); // ✅ NEW: Disable end interview button when recording starts
      
      // ✅ RESTORED: Disable button for 3 seconds to prevent edge cases
      setIsButtonDisabled(true);
      setTimeout(() => {
        setIsButtonDisabled(false);
      }, 1500);
      
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
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
        console.log('✅ Recording started successfully');
        
      } catch (error) {
        console.error('❌ Failed to start recording:', error);
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
  const { loadChatHistory, appendToChatHistory, deleteChatHistory } = useChatHistory();

  // Load chat history when component mounts
  useEffect(() => {
    const loadHistory = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const interviewId = urlParams.get('interview_id');
      if (interviewId) {
        const history = await loadChatHistory(interviewId);
        if (history && history.length > 0) {
          setConversation(history);
        }
      }
    };
    
    loadHistory();
  }, [loadChatHistory]);

  // Function to add message and save to database
  const addMessageToConversation = useCallback(async (speaker, message) => {
    // Add to local state immediately
    const newMessage = {
      id: Date.now(),
      speaker,
      message,
      timestamp: new Date().toLocaleTimeString()
    };
    
    setConversation(prev => [...prev, newMessage]);
    
    // Save to database
    const urlParams = new URLSearchParams(window.location.search);
    const interviewId = urlParams.get('interview_id');
    if (interviewId) {
      await appendToChatHistory(interviewId, speaker, message);
    }
  }, [appendToChatHistory]);

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
      
      console.log('💾 Saving code:', code);
      
      // Trim the code
      const trimmedCode = code.trim();
      
      setCodeToAppend(''); // Clear the code for next question
      
      // Format code with markdown
      const formattedCode = '\n``` \n\n' + trimmedCode + '\n\n```\n';
      
      // Add user message to conversation
      await addMessageToConversation('candidate', formattedCode);
      console.log('✅ Candidate message added');
      
      setIsLoading(false); // Stop loading immediately after user message appears

      // Add thinking indicator before backend call
      const thinkingMessage = {
          id: `thinking-${Date.now()}`,
          speaker: 'interviewer',
          message: 'Thinking...',
          timestamp: new Date().toLocaleTimeString(),
          isThinking: true
      };
      setConversation(prev => [...prev, thinkingMessage]);

      // ✅ ENSURE: Call Interview Manager API to get the next question/response
      setIsResponseInProgress(true);
      
      try {
        await callInterviewManager(formattedCode);
        console.log('✅ Interview Manager API called successfully');
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
        console.log("Code to Append: ", code);
        setCodeToAppend(code);
        console.log(newLanguage);
        setLanguage(newLanguage);
  };

  // ✅ NEW: Auto-end interview when timeout is detected (no confirmation popup)
  const handleEndInterviewAutomatically = async () => {
    console.log('✅ Auto-ending interview due to timeout...');
    
    // ✅ NEW: Show loading state
    setIsEndingInterview(true);
    
    try {
      // ✅ Send END_INTERVIEW command to backend (same as manual end)
      console.log('📤 Sending END_INTERVIEW command to backend...');
      
      const urlParams = new URLSearchParams(window.location.search);
      const interviewId = urlParams.get('interview_id');
      
      if (!interviewId) {
        console.error('❌ No interview_id found in URL');
        setIsEndingInterview(false);
        return;
      }
      
      // ✅ Use the same apiPost function that works for normal responses
      const response = await apiPost('/api/generate-response', {
        message: 'END_INTERVIEW',
        interview_id: interviewId
      });
      
      // ✅ Now handle the response exactly like handleEndInterview does
      // (Copy all the logic from handleEndInterview starting from line 316)
      if (response.success) {
        const { response: textResponse, audio_url, should_delete_audio, interview_done, feedback_saved_successfully } = response.data;
        
        // ✅ FIXED: Track events only when interview is done AND feedback is successfully saved
        if (interview_done) {
          console.log('🎯 Interview completed, tracking events...');
          
          // Track interview completion
          console.log('📊 Tracking participatedInMockInterview...');
          trackEvents.participatedInMockInterview({
            interview_id: interviewId,
            completion_timestamp: new Date().toISOString(),
            completion_method: 'timeout_auto'
          });
          
          // ✅ FIXED: Only track feedback generation when feedback is actually saved to database
          if (feedback_saved_successfully) {
            console.log('✅ Feedback successfully saved to database, tracking feedback generation...');
            setTimeout(() => {
              console.log('📊 Tracking mockInterviewFeedbackGenerated...');
              trackEvents.mockInterviewFeedbackGenerated({
                interview_id: interviewId,
                generation_timestamp: new Date().toISOString(),
                generation_method: 'timeout_auto'
              });
            }, 100); // 100ms delay
          } else {
            console.log('⚠️ Interview completed but feedback not saved yet, skipping feedback generation tracking');
          }
        }
        
        // ✅ FIXED: Preload audio first, then show text and play simultaneously
        if (audio_url) {
          console.log('🔊 Preloading final audio response:', audio_url);
          const audio = new Audio(audio_url);
          
          // Preload the audio
          audio.preload = 'auto';
          
          // Wait for audio to be ready, then show text and play simultaneously
          const playFinalAudioWhenReady = () => {
            // ✅ Remove thinking message right before showing the final response
            setConversation(prev => {
              const filtered = prev.filter(msg => !msg.isThinking);
              return filtered;
            });
            
            // Add final message and start playing at the same time
            const finalMessage = {
              id: Date.now(),
              speaker: 'interviewer',
              message: textResponse,
              timestamp: new Date().toLocaleTimeString()
            };
            setConversation(prev => [...prev, finalMessage]);
            
            console.log('✅ Final response added, starting audio playback');
            
            // Track final audio playback state
            setIsAudioPlaying(true);
            setCurrentAudioElement(audio);
            setCanEndInterview(false); // Disable end interview button while final audio plays
            
            // Start playing immediately
            audio.play().catch(error => {
              console.error('❌ Failed to play final audio:', error);
              setIsAudioPlaying(false);
              setCurrentAudioElement(null);
              // Still redirect even if audio fails
              if (interview_done) {
                window.location.href = `/interview-feedback?interview_id=${interviewId}`;
              }
            });
          };
          
          // If audio is already loaded, play immediately
          if (audio.readyState >= 2) { // HAVE_CURRENT_DATA or higher
            playFinalAudioWhenReady();
          } else {
            // Wait for audio to be ready
            audio.addEventListener('canplaythrough', playFinalAudioWhenReady, { once: true });
            
            // Fallback: if canplaythrough doesn't fire, wait a bit then play
            setTimeout(() => {
              if (audio.readyState >= 2) {
                playFinalAudioWhenReady();
              }
            }, 100);
          }
          
          audio.onended = async () => {
            console.log('✅ Final audio playback completed');
            setIsAudioPlaying(false);
            setCurrentAudioElement(null);
            setCanEndInterview(true); // Re-enable end interview button
            
            if (should_delete_audio) {
              try {
                console.log('🗑️ Deleting final audio file after playback...');
                console.log('🗑️ Final audio URL to delete:', audio_url);
                
                await apiDelete('/api/delete-audio', {
                  body: { audio_url }
                });
                console.log('✅ Final audio file deleted successfully');
              } catch (error) {
                console.error('❌ Failed to delete final audio file:', error);
                console.error('❌ Error details:', error.message);
              }
            }
            
            // ✅ NEW: Redirect to feedback page after audio finishes
            if (interview_done) {
              console.log('🎯 Interview completed, redirecting to feedback...');
              
              // Add a small delay to ensure audio deletion completes
              setTimeout(() => {
                window.location.href = `/interview-feedback?interview_id=${interviewId}`;
              }, 1000);
            }
          };
          
          // Handle audio errors
          audio.onerror = (error) => {
            console.error('❌ Final audio playback failed:', error);
            setIsAudioPlaying(false);
            setCurrentAudioElement(null);
            
            // ✅ Remove thinking message before showing text
            setConversation(prev => {
              const filtered = prev.filter(msg => !msg.isThinking);
              return filtered;
            });
            
            // Still show the text even if audio fails
            const finalMessage = {
              id: Date.now(),
              speaker: 'interviewer',
              message: textResponse,
              timestamp: new Date().toLocaleTimeString()
            };
            setConversation(prev => [...prev, finalMessage]);
            // Redirect if interview is done
            if (interview_done) {
              window.location.href = `/interview-feedback?interview_id=${interviewId}`;
            }
          };
        } else if (interview_done) {
          // ✅ Remove thinking message before showing final message
          setConversation(prev => {
            const filtered = prev.filter(msg => !msg.isThinking);
            return filtered;
          });
          
          // ✅ NEW: If no audio but interview is done, show message and redirect immediately
          const finalMessage = {
            id: Date.now(),
            speaker: 'interviewer',
            message: textResponse,
            timestamp: new Date().toLocaleTimeString()
          };
          setConversation(prev => [...prev, finalMessage]);
          console.log('🎯 Interview completed (no audio), redirecting to feedback...');
          window.location.href = `/interview-feedback?interview_id=${interviewId}`;
        }
        
      } else {
        console.error('❌ End interview API error:', response.message);
        setIsEndingInterview(false);
      }
    } catch (error) {
      console.error('❌ Error auto-ending interview:', error);
      setIsEndingInterview(false);
    }
  };

  // ✅ NEW: Timeout Modal Component
  const TimeoutModal = () => {
    if (!showTimeoutModal) return null;
    
    const handleContinue = () => {
      console.log('✅ User acknowledged timeout, ending interview...');
      setShowTimeoutModal(false);
      // Now trigger the end interview flow
      handleEndInterviewAutomatically();
    };
    
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-3 sm:p-4"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ type: "spring", duration: 0.5 }}
            className="relative rounded-2xl p-6 sm:p-8 max-w-md w-full shadow-2xl border"
            style={{ 
              backgroundColor: 'var(--color-card)',
              borderColor: 'var(--color-border)'
            }}
          >
            {/* Decorative corner elements */}
            <div className="absolute top-4 right-4">
              <div className="w-2 h-2 bg-orange-400/50 rounded-full animate-pulse" style={{ animationDelay: '0ms' }}></div>
            </div>
            <div className="absolute bottom-4 left-4">
              <div className="w-2 h-2 bg-amber-400/50 rounded-full animate-pulse" style={{ animationDelay: '200ms' }}></div>
            </div>
            <div className="absolute top-4 left-4">
              <div className="w-2 h-2 bg-yellow-400/50 rounded-full animate-pulse" style={{ animationDelay: '400ms' }}></div>
            </div>
            <div className="absolute bottom-4 right-4">
              <div className="w-2 h-2 bg-orange-500/50 rounded-full animate-pulse" style={{ animationDelay: '600ms' }}></div>
            </div>

            <div className="text-center">
              {/* Animated Clock Icon */}
              <div className="relative mb-6">
                <div className="w-20 h-20 mx-auto relative">
                  {/* Outer pulsing ring */}
                  <motion.div
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute inset-0 rounded-full border-4 border-orange-200 dark:border-orange-900/50"
                  />
                  {/* Inner circle with gradient */}
                  <div className="absolute inset-2 rounded-full bg-gradient-to-br from-orange-50 via-amber-50 to-yellow-50 dark:from-orange-900/30 dark:via-amber-900/30 dark:to-yellow-900/30 flex items-center justify-center shadow-inner">
                    {/* Clock SVG */}
                    <svg 
                      className="w-10 h-10 text-orange-600 dark:text-orange-400" 
                      fill="none" 
                      stroke="currentColor" 
                      viewBox="0 0 24 24"
                    >
                      <circle cx="12" cy="12" r="10" strokeWidth="2" className="opacity-20"/>
                      <path 
                        strokeLinecap="round" 
                        strokeLinejoin="round" 
                        strokeWidth="2.5" 
                        d="M12 6v6l4 2" 
                      />
                      <motion.circle
                        cx="12"
                        cy="12"
                        r="1.5"
                        fill="currentColor"
                        animate={{ opacity: [1, 0.5, 1] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Title with gradient */}
              <motion.h3
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="text-2xl sm:text-3xl font-bold mb-3 bg-gradient-to-r from-orange-600 via-amber-600 to-yellow-600 dark:from-orange-400 dark:via-amber-400 dark:to-yellow-400 bg-clip-text text-transparent"
              >
                Time's Up!
              </motion.h3>

              {/* Subtitle */}
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
                className="text-sm font-medium mb-4"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Interview Time Limit Reached
              </motion.p>

              {/* Message */}
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="mb-8 leading-relaxed text-sm sm:text-base px-2"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Your interview time limit has been reached. We'll now wrap up the interview and generate your comprehensive feedback.
              </motion.p>
              
              {/* Action Button with gradient */}
              <motion.button
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                onClick={handleContinue}
                className="w-full bg-gradient-to-r from-orange-500 via-amber-500 to-yellow-500 hover:from-orange-600 hover:via-amber-600 hover:to-yellow-600 text-white font-semibold py-3.5 px-6 rounded-xl transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-105 active:scale-95 text-sm sm:text-base relative overflow-hidden group"
              >
                {/* Shine effect on hover */}
                <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000"></span>
                
                <span className="relative flex items-center justify-center gap-2">
                  <svg 
                    className="w-5 h-5" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path 
                      strokeLinecap="round" 
                      strokeLinejoin="round" 
                      strokeWidth={2} 
                      d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" 
                    />
                  </svg>
                  Continue to Feedback
                </span>
              </motion.button>

              {/* Info text */}
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                className="text-xs mt-4"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Your responses have been saved
              </motion.p>
            </div>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    );
  };

  return (
    <div 
      className="h-full flex flex-col p-3 sm:p-4 lg:p-6 min-h-0"
      style={{ 
        backgroundColor: 'var(--color-card)',
        borderLeft: '1px solid var(--color-border)'
      }}
    >
      {/* Header with Title and Buttons */}
      <div className="flex flex-col gap-3 sm:gap-4 mb-3 sm:mb-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-3">
          <h2 
            className="text-lg sm:text-xl md:text-2xl font-bold tracking-tight"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Interview Conversation
          </h2>
          
          {/* End Interview Button */}
          <button
            onClick={handleEndInterview}
            disabled={!canEndInterview || isAudioPlaying || isRecording || isLoading || isResponseInProgress}
            className={`w-full sm:w-auto px-3 sm:px-4 md:px-6 py-2 sm:py-2.5 text-xs sm:text-sm md:text-base font-semibold rounded-full transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 whitespace-nowrap ${
              !canEndInterview || isAudioPlaying || isRecording || isLoading || isResponseInProgress
                ? 'bg-[var(--color-error)]/10 border-2 border-[var(--color-error)]/30 text-[var(--color-error)]/70 cursor-not-allowed'
                : 'bg-[var(--color-error)]/10 border-2 border-[var(--color-error)] text-[var(--color-error)] hover:bg-[var(--color-error)] hover:text-white hover:border-[var(--color-error)]'
            }`}
            title={
              !canEndInterview || isAudioPlaying || isRecording || isLoading || isResponseInProgress
                ? (isRecording ? "Wait for recording to finish" : 
                   isLoading ? "Wait for response to generate" : 
                   isResponseInProgress ? "Response in progress..." : 
                   isAudioPlaying ? "Wait for audio to finish" :
                   interviewStage === 'introduction' ? "Complete the introduction first" : 
                   interviewStage === 'resume_discussion' && !hasAnsweredResumeQuestion ? "Answer at least one resume & JD related question to end interview" : "Wait for resume questions to begin")
                : "End Interview"
            }
            onMouseEnter={() => {
              console.log('🔍 Button hover - Current state:', {
                canEndInterview,
                isAudioPlaying,
                isRecording,
                isLoading,
                isResponseInProgress,
                interviewStage,
                hasAnsweredResumeQuestion
              });
            }}
          >
            <span className="hidden sm:inline">
              End Interview
            </span>
            <span className="sm:hidden">
              End
            </span>
          </button>
        </div>
        
        {/* Pill-shaped Recording Button */}
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={toggleRecording}
            disabled={isButtonDisabled || isAudioPlaying || isLoading || isResponseInProgress} // ✅ NEW: Also disable during response process
            className={`w-full px-4 sm:px-6 md:px-8 py-3 sm:py-4 rounded-full flex items-center justify-center gap-2 sm:gap-3 text-white font-semibold transition-all duration-300 shadow-xl hover:shadow-xl hover:scale-105 active:scale-95 ${
              isButtonDisabled || isAudioPlaying || isLoading || isResponseInProgress
                ? 'bg-gray-400 cursor-not-allowed opacity-60' // ✅ NEW: Disabled state for all conditions
                : isRecording 
                  ? 'bg-red-500 hover:bg-red-600' 
                  : 'bg-blue-500 hover:bg-blue-600'
            }`}
            title={
              isButtonDisabled || isAudioPlaying || isLoading || isResponseInProgress
                ? (isAudioPlaying ? 'Wait for audio to finish' : 
                   isLoading ? 'Generating response...' : 
                   isResponseInProgress ? 'Response in progress...' : 'Button temporarily disabled')
                : (isRecording ? 'Stop Recording' : 'Speak Now')
            } // ✅ NEW: Dynamic tooltip for all disabled states
          >
            {isRecording ? <MicOff size={18} className="sm:w-5 sm:h-5" /> : <Mic size={18} className="sm:w-5 sm:h-5" />}
            <span className="text-xs sm:text-sm font-medium">
              {isButtonDisabled || isAudioPlaying || isLoading || isResponseInProgress
                ? (isAudioPlaying ? 'Audio Playing...' : 
                   isLoading ? 'Generating...' : 
                   isResponseInProgress ? 'Response in progress...' : 'Please Wait...')
                : (isRecording ? 'Stop Recording' : 'Speak Now')
              } {/* ✅ NEW: Dynamic text for all disabled states */}
            </span>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div 
        ref={messagesContainerRef}  // ✅ NEW: Add ref to messages container
        className="flex-1 overflow-y-auto space-y-3 sm:space-y-4 mb-4 sm:mb-6 pr-1 sm:pr-2 min-h-0"
      >
        <AnimatePresence>
          {conversation.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 20 }}
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
          {isRecording 
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
            disabled={isButtonDisabled || isAudioPlaying || isLoading || isResponseInProgress}
            className={`w-full px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 text-white font-semibold transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 ${
              isButtonDisabled || isAudioPlaying || isLoading || isResponseInProgress
                ? 'bg-gray-400 cursor-not-allowed opacity-60'
                : 'bg-purple-500 hover:bg-purple-600'
            }`}
            title={
              isButtonDisabled || isAudioPlaying || isLoading || isResponseInProgress
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

      {/* ✅ NEW: Timeout modal */}
      <TimeoutModal />
    </div>
  );
}

export default ChatWindow;
