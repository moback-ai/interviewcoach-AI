import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { useHeadTracking } from '@/hooks/useHeadTracking';
import ChatWindow from '@/components/interview/ChatWindow';
import HeadTrackingAlert from '@/components/interview/HeadTrackingAlert';
import WarningModal from '@/components/interview/WarningModal';
import WaveAnimation from '@/components/interview/WaveAnimation';
import { authFetchInit, getSession } from '../lib/authClient';
import { getBackendOrigin } from '../utils/apiConfig';
import {
  applyInterviewCameraConstraints,
  getInterviewCameraConstraints,
  getMediaAccessErrorMessage,
  requestUserMedia,
} from '../utils/mediaDevices';
import { useOperation } from '../contexts/OperationContext';
import { isAuthErrorMessage, redirectToExpiredLogin } from '../utils/authInterceptor';
import { devLog } from '../utils/devLog';
import { useInterviewTimer } from '@/hooks/useInterviewTimer';

/** Matches backend STARTED_INTERVIEW_STATUSES (+ legacy in_progress). */
const RESUMABLE_INTERVIEW_STATUSES = new Set(['STARTED', 'ACTIVE', 'in_progress']);
const COMPLETED_INTERVIEW_STATUSES = new Set(['ENDED', 'completed']);

function InterviewPage() {
  const { setIsOperationInProgress } = useOperation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const interviewId = searchParams.get('interview_id');
  const [isValidated, setIsValidated] = useState(false);
  useInterviewTimer(interviewId, isValidated);
  const [isValidating, setIsValidating] = useState(true); // ✅ RENAMED: Validation loading
  const [validationError, setValidationError] = useState(null);
  
  // ✅ ADD: Separate loading state for ChatWindow
  const [isChatLoading, setIsChatLoading] = useState(false);
  
  // ✅ ADD: Audio state for wave animation
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  
  // ✅ ADD: ChatWindow states for head tracking toggle
  const [chatStates, setChatStates] = useState({
    isRecording: false,
    isResponseInProgress: false,
    canEndInterview: true,
    isSpeakCooldown: false,
  });

  // ✅ ADD: Callback to receive state changes from ChatWindow
  const handleChatStateChange = useCallback((newStates) => {
    setChatStates((prev) => ({ ...prev, ...newStates }));
  }, []);
  
  // ✅ ADD: Track if validation has been attempted
  const hasValidated = useRef(false);
  
  // ✅ ADD MISSING STATE VARIABLES
  const [conversation, setConversation] = useState([
    {
      id: 1,
      speaker: 'interviewer',
      message: 'Speak to start the interview.',
      timestamp: new Date().toLocaleTimeString()
    }
  ]);
  
  
  // Head tracking state
  const [headTrackingEnabled, setHeadTrackingEnabled] = useState(false); // Start disabled
  const [showHeadTrackingPopup, setShowHeadTrackingPopup] = useState(false);
  const [headTrackingStarted, setHeadTrackingStarted] = useState(false);
  const [showWarningModal, setShowWarningModal] = useState(false);
  const [warningType, setWarningType] = useState(null);
  
  // Mode tracking
  const [currentMode, setCurrentMode] = useState(null); // Track current mode
  
  // Track calibration state
  const [calibrationState, setCalibrationState] = useState('idle'); // 'idle', 'checking', 'ready', 'error', 'success'
  const [showCalibrationWarning, setShowCalibrationWarning] = useState(false);
  const [calibrationCheckTimer, setCalibrationCheckTimer] = useState(null);
  const [showCalibrationSuccess, setShowCalibrationSuccess] = useState(false);
  const readyForCalibrationRef = useRef(false);
  const calibrationInProgressRef = useRef(false);
  
  const streamRef = useRef(null);
  const headTrackingEnabledRef = useRef(headTrackingEnabled);
  headTrackingEnabledRef.current = headTrackingEnabled;
  const pausedForHiddenTabRef = useRef(false);
  const cameraSessionRef = useRef(0);
  /** Aligns with Speak button + Head tracking: lock UI during audio, recording, API work, response pipeline, or mic cooldown */
  const interviewInteractionLocked =
    isAudioPlaying ||
    isChatLoading ||
    chatStates.isResponseInProgress ||
    chatStates.isRecording ||
    !!chatStates.isSpeakCooldown;

  useEffect(() => {
    setIsOperationInProgress(interviewInteractionLocked);
    return () => setIsOperationInProgress(false);
  }, [interviewInteractionLocked, setIsOperationInProgress]);

  const [cameraError, setCameraError] = useState(null);
  const [isCameraLoading, setIsCameraLoading] = useState(true);
  const cameraRetryCountRef = useRef(0);
  const MAX_RETRIES = 3;

  // Handle calibration success
  const handleCalibrationSuccess = useCallback(() => {
    setCalibrationState('success');
    setShowCalibrationSuccess(true);
    
    // Clear any ongoing calibration check timer
    if (calibrationCheckTimer) {
      clearTimeout(calibrationCheckTimer);
      setCalibrationCheckTimer(null);
    }
    // Reset the calibration progress flag
    calibrationInProgressRef.current = false;
    devLog('🎉 Calibration completed successfully');
    
    // Auto-hide success message after 3 seconds
    setTimeout(() => {
      setShowCalibrationSuccess(false);
      setCalibrationState('idle');
    }, 3000);
  }, [calibrationCheckTimer]);

  // Initialize head tracking
  const {
    isCalibrated,
    isLooking,
    isConnected,
    error,
    readyForCalibration,
    calibrationMessage,
    videoRef,
    startCalibration,
    pauseFrameSending,
    resumeFrameSending,
    startMonitoring
  } = useHeadTracking(headTrackingEnabled, handleCalibrationSuccess);

  const stopCamera = useCallback(() => {
    cameraSessionRef.current += 1;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, [videoRef]);

  const startCamera = useCallback(async (retryCount = 0) => {
    if (!isValidated || isValidating) {
      return;
    }
    if (document.hidden && !headTrackingEnabledRef.current) {
      pausedForHiddenTabRef.current = true;
      return;
    }

    if (retryCount === 0) {
      cameraSessionRef.current += 1;
    }
    const session = cameraSessionRef.current;

    try {
      if (!videoRef.current) {
        devLog('⏳ Waiting for video element to mount...');
        setTimeout(() => {
          if (session !== cameraSessionRef.current) {
            return;
          }
          if (retryCount < MAX_RETRIES) {
            startCamera(retryCount + 1);
          } else {
            setCameraError('Video element not found. Please refresh the page.');
            setIsCameraLoading(false);
          }
        }, 500);
        return;
      }

      devLog('🎥 Requesting camera access...');
      setIsCameraLoading(true);
      setCameraError(null);

      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }

      const stream = await requestUserMedia(
        getInterviewCameraConstraints(headTrackingEnabledRef.current)
      );

      if (session !== cameraSessionRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      if (!videoRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        throw new Error('Video element was removed');
      }

      videoRef.current.srcObject = stream;
      streamRef.current = stream;

      await new Promise((resolve, reject) => {
        if (!videoRef.current) {
          reject(new Error('Video element not available'));
          return;
        }

        const video = videoRef.current;

        const handleLoadedMetadata = () => {
          video.removeEventListener('loadedmetadata', handleLoadedMetadata);
          video.removeEventListener('error', handleError);
          if (session !== cameraSessionRef.current) {
            resolve();
            return;
          }
          devLog('✅ Camera stream loaded successfully');
          setIsCameraLoading(false);
          setCameraError(null);
          cameraRetryCountRef.current = 0;
          resolve();
        };

        const handleError = () => {
          video.removeEventListener('loadedmetadata', handleLoadedMetadata);
          video.removeEventListener('error', handleError);
          reject(new Error('Video element failed to load stream'));
        };

        if (video.readyState >= 1) {
          handleLoadedMetadata();
        } else {
          video.addEventListener('loadedmetadata', handleLoadedMetadata);
          video.addEventListener('error', handleError);

          setTimeout(() => {
            video.removeEventListener('loadedmetadata', handleLoadedMetadata);
            video.removeEventListener('error', handleError);
            reject(new Error('Video load timeout'));
          }, 5000);
        }
      });
    } catch (error) {
      if (session !== cameraSessionRef.current) {
        return;
      }

      console.error('❌ Error accessing camera:', error);
      cameraRetryCountRef.current = retryCount + 1;

      let errorMessage = 'Failed to access camera. ';

      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        errorMessage += 'Please allow camera permissions and refresh the page.';
        setCameraError(errorMessage);
        setIsCameraLoading(false);
      } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        errorMessage += 'No camera found. Please connect a camera and refresh the page.';
        setCameraError(errorMessage);
        setIsCameraLoading(false);
      } else if (error.name === 'MediaDevicesUnsupported' || error.name === 'MediaDevicesUnavailable') {
        setCameraError(getMediaAccessErrorMessage('camera'));
        setIsCameraLoading(false);
      } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
        errorMessage += 'Camera is being used by another application. Please close other apps and refresh.';
        setCameraError(errorMessage);
        setIsCameraLoading(false);
      } else if (retryCount < MAX_RETRIES) {
        devLog(`🔄 Retrying camera access (attempt ${retryCount + 1}/${MAX_RETRIES})...`);
        setTimeout(() => {
          if (session === cameraSessionRef.current) {
            startCamera(retryCount + 1);
          }
        }, 1000 * (retryCount + 1));
      } else {
        errorMessage += 'Please refresh the page and try again.';
        setCameraError(errorMessage);
        setIsCameraLoading(false);
      }
    }
  }, [isValidated, isValidating, videoRef]);

  useEffect(() => {
    if (!isValidated || isValidating) {
      return undefined;
    }

    let cancelled = false;

    const syncCamera = async () => {
      if (document.hidden && !headTrackingEnabledRef.current) {
        stopCamera();
        pausedForHiddenTabRef.current = true;
        return;
      }

      pausedForHiddenTabRef.current = false;

      if (!streamRef.current) {
        await startCamera();
        return;
      }

      const applied = await applyInterviewCameraConstraints(
        streamRef.current,
        headTrackingEnabledRef.current
      );
      if (!cancelled && !applied) {
        await startCamera();
      }
    };

    syncCamera();
    return () => {
      cancelled = true;
    };
  }, [isValidated, isValidating, headTrackingEnabled, startCamera, stopCamera]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) {
        if (!headTrackingEnabledRef.current) {
          stopCamera();
          pausedForHiddenTabRef.current = true;
        }
        return;
      }

      if (pausedForHiddenTabRef.current || !streamRef.current) {
        pausedForHiddenTabRef.current = false;
        if (isValidated && !isValidating) {
          startCamera();
        }
      }
    };

    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [startCamera, stopCamera, isValidated, isValidating]);

  useEffect(() => () => stopCamera(), [stopCamera]);


  // Show head tracking popup when user enables the toggle
  useEffect(() => {
    if (headTrackingEnabled && !headTrackingStarted) {
      // Show popup when user enables head tracking
      setShowHeadTrackingPopup(true);
    }
  }, [headTrackingEnabled, headTrackingStarted]);

  // Handle warning modal display - show warnings immediately
  useEffect(() => {
    if (!headTrackingStarted || !headTrackingEnabled) return; // Only show warnings if head tracking is active

    // Skip warning checks if warning is already displayed
    if (showWarningModal) {
      return;
    }

    // Add a small delay after warning closes to allow backend to update isLooking state
    const timeoutId = setTimeout(() => {
      // Eye tracking warnings - show immediately when not looking
      const warningConditionMet = isCalibrated && !isLooking;
      devLog(`🔍 Warning condition check: isCalibrated=${isCalibrated}, !isLooking=${!isLooking}, conditionMet=${warningConditionMet}`);
      
      if (warningConditionMet) {
        devLog('🚨 Showing head tracking warning (eye contact)');
        setWarningType('eye_contact');
        setShowWarningModal(true);
        setCurrentMode('head_tracking');
        // Pause monitoring while warning is shown
        pauseFrameSending();
      } else if (isCalibrated && isLooking) {
        devLog('✅ User is looking at camera, no warning needed');
      } else if (!isCalibrated) {
        devLog('⚠️ Not calibrated yet, skipping warning check');
      }
    }, 500); // 500ms delay to allow backend to process new frames

    return () => clearTimeout(timeoutId);
  }, [headTrackingStarted, headTrackingEnabled, isCalibrated, isLooking, showWarningModal, pauseFrameSending]);

  // Update mode when switching
  useEffect(() => {
    if (headTrackingEnabled) {
      // Switching to head tracking mode
      if (currentMode !== 'head_tracking') {
        setCurrentMode('head_tracking');
        devLog('🔄 Switched to head tracking mode');
      }
    } else {
      // No monitoring when head tracking is disabled
      if (currentMode !== 'disabled') {
        setCurrentMode('disabled');
        devLog('🔄 Disabled monitoring');
      }
    }
  }, [headTrackingEnabled, currentMode]);

  // Initialize current mode on first render
  useEffect(() => {
    if (currentMode === null) {
      setCurrentMode('disabled'); // Start with no monitoring
      setHeadTrackingStarted(false); // Don't start monitoring initially
    }
  }, [currentMode]);

  // Start monitoring when video is ready and monitoring is confirmed
  useEffect(() => {
    devLog(`🔍 Monitoring check: videoRef=${!!videoRef.current}, isConnected=${isConnected}, headTrackingStarted=${headTrackingStarted}, showHeadTrackingPopup=${showHeadTrackingPopup}`);
    
    const video = videoRef.current;
    if (video && headTrackingStarted && !showHeadTrackingPopup) {
      const handleVideoReady = () => {
        devLog('🎥 Video ready, starting monitoring...');
        startMonitoring();
        
        // Don't start calibration immediately - wait for user to be ready
        // Calibration will start automatically when readyForCalibration becomes true
      };

      if (video.readyState >= 2) {
        handleVideoReady();
      } else {
        video.addEventListener('loadeddata', handleVideoReady);
        return () => {
          video.removeEventListener('loadeddata', handleVideoReady);
        };
      }
    }
  }, [videoRef, isConnected, headTrackingStarted, showHeadTrackingPopup, startMonitoring]);

  // Handle calibration check process
  const startCalibrationCheck = useCallback(() => {
    // Prevent multiple calibration checks from running simultaneously
    if (calibrationInProgressRef.current) {
      devLog('⚠️ Calibration check already in progress, skipping...');
      return;
    }
    
    devLog('🔍 Starting 5-second calibration check...');
    calibrationInProgressRef.current = true;
    setCalibrationState('checking');
    
    // Check for 5 seconds
    const timer = setTimeout(() => {
      devLog('⏰ 5-second check completed');
      // Get the current readyForCalibration value at the time of check
      const currentReadyForCalibration = readyForCalibrationRef.current;
      devLog(`🔍 Current readyForCalibration state: ${currentReadyForCalibration}`);
      
      if (currentReadyForCalibration && !isCalibrated) {
        devLog('✅ User is ready, starting calibration');
        setCalibrationState('ready');
        startCalibration();
      } else if (currentReadyForCalibration && isCalibrated) {
        devLog('✅ User is ready but already calibrated, skipping calibration');
        setCalibrationState('idle');
        calibrationInProgressRef.current = false;
      } else {
        devLog('❌ User not ready, showing warning modal');
        setCalibrationState('error');
        setShowCalibrationWarning(true);
        pauseFrameSending(); // Stop sending frames
      }
    }, 5000);
    
    setCalibrationCheckTimer(timer);
  }, [startCalibration, pauseFrameSending, isCalibrated]);

  // Handle calibration warning modal close
  const handleCalibrationWarningClose = useCallback(() => {
    devLog('🔄 User acknowledged warning, restarting check...');
    setShowCalibrationWarning(false);
    setCalibrationState('checking');
    resumeFrameSending(); // Resume sending frames
    
    // Start another 5-second check
    const timer = setTimeout(() => {
      devLog('⏰ Second 5-second check completed');
      // Get the current readyForCalibration value at the time of check
      const currentReadyForCalibration = readyForCalibrationRef.current;
      devLog(`🔍 Current readyForCalibration state: ${currentReadyForCalibration}`);
      
      if (currentReadyForCalibration && !isCalibrated) {
        devLog('✅ User is now ready, starting calibration');
        setCalibrationState('ready');
        startCalibration();
      } else if (currentReadyForCalibration && isCalibrated) {
        devLog('✅ User is ready but already calibrated, skipping calibration');
        setCalibrationState('idle');
        calibrationInProgressRef.current = false;
      } else {
        devLog('❌ User still not ready, showing warning again');
        setCalibrationState('error');
        setShowCalibrationWarning(true);
        pauseFrameSending(); // Stop sending frames again
      }
    }, 5000);
    
    setCalibrationCheckTimer(timer);
  }, [startCalibration, pauseFrameSending, resumeFrameSending, isCalibrated]);

  // Update ref when readyForCalibration changes
  useEffect(() => {
    readyForCalibrationRef.current = readyForCalibration;
  }, [readyForCalibration]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (calibrationCheckTimer) {
        clearTimeout(calibrationCheckTimer);
      }
      // Reset calibration progress flag
      calibrationInProgressRef.current = false;
    };
  }, [calibrationCheckTimer]);

  // Interview validation — cookie-aware auth; never dump failures to /upload
  useEffect(() => {
    const validateInterview = async () => {
      if (hasValidated.current) {
        return;
      }

      hasValidated.current = true;

      try {
        setIsValidating(true);
        setValidationError(null);

        const interviewIdFromUrl = searchParams.get('interview_id');

        if (!interviewIdFromUrl) {
          devLog('❌ No interview_id provided');
          setValidationError('No interview was specified. Open Resume from your dashboard.');
          return;
        }

        devLog('🔍 Validating interview:', interviewIdFromUrl);

        const session = await getSession();
        if (!session) {
          devLog('❌ No session found');
          navigate('/login', {
            replace: true,
            state: { from: `/interview?interview_id=${interviewIdFromUrl}` },
          });
          return;
        }

        const response = await fetch(
          `${getBackendOrigin()}/functions/v1/interviews/${interviewIdFromUrl}`,
          {
            method: 'GET',
            ...authFetchInit({ 'Content-Type': 'application/json' }),
          },
        );

        let result = {};
        try {
          result = await response.json();
        } catch {
          result = {};
        }

        devLog('📋 Interview validation result:', result);

        if (response.status === 401 || isAuthErrorMessage(result.error || result.message || '')) {
          redirectToExpiredLogin();
          return;
        }

        if (!response.ok || !result.success) {
          devLog('❌ Interview not found or access denied');
          setValidationError(
            result.message || 'This interview could not be found or you do not have access to it.',
          );
          return;
        }

        const interview = result.data;
        const status = interview?.status;

        if (status === 'PENDING') {
          devLog('⏳ Interview is pending payment confirmation');
          setValidationError(
            'This interview is still waiting for payment confirmation. Check your dashboard or payment status.',
          );
          return;
        }

        if (COMPLETED_INTERVIEW_STATUSES.has(status)) {
          devLog('✅ Interview already completed, redirecting to feedback page');
          navigate(`/interview-feedback?interview_id=${interviewIdFromUrl}`, { replace: true });
          return;
        }

        if (!RESUMABLE_INTERVIEW_STATUSES.has(status)) {
          devLog('❌ Interview status is not resumable:', status);
          setValidationError(
            `This interview cannot be resumed (status: ${status || 'unknown'}). Return to the dashboard to continue.`,
          );
          return;
        }

        devLog('✅ Interview validated successfully:', interview);
        setIsValidated(true);
      } catch (error) {
        console.error('❌ Interview validation error:', error);
        if (isAuthErrorMessage(error.message)) {
          redirectToExpiredLogin();
          return;
        }
        setValidationError(
          error.message || 'Could not validate this interview session. Please try again from the dashboard.',
        );
      } finally {
        setIsValidating(false);
      }
    };

    validateInterview();
  }, [navigate, searchParams]);

  // Handle head tracking confirmation
  const confirmHeadTracking = () => {
    setShowHeadTrackingPopup(false);
    setHeadTrackingStarted(true);
    devLog('🚀 Head tracking confirmed and started');
    
    // Start calibration check after a short delay to allow monitoring to start
    setTimeout(() => {
      devLog('⏰ Starting calibration check process...');
      startCalibrationCheck();
    }, 1000);
  };

  // Handle warning modal close
  const closeWarningModal = () => {
    setShowWarningModal(false);
    
    // Resume monitoring after user acknowledges warning
    setTimeout(() => {
      resumeFrameSending();
    }, 1000); // Small delay to ensure user has time to adjust
    
    devLog(`✅ Monitoring resumed for ${currentMode} mode`);
  };

  // Show loading while validating
  if (isValidating) { // ✅ FIXED: Use validation-specific loading state
    return (
      <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-primary)] mx-auto mb-4"></div>
          <p className="text-[var(--color-text-secondary)]">Validating interview session...</p>
        </div>
      </div>
    );
  }

  // Show error if not validated (auth redirects happen above; avoid silent /upload bounce)
  if (!isValidated) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center space-y-4">
          <p className="text-[var(--color-text-primary)] font-semibold text-lg">
            Unable to resume interview
          </p>
          <p className="text-[var(--color-text-secondary)] text-sm leading-relaxed">
            {validationError || 'This interview session could not be opened.'}
          </p>
          <button
            type="button"
            onClick={() => navigate('/dashboard', { replace: true })}
            className="inline-flex items-center justify-center px-4 py-2.5 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    );
  }

  // Original interview page content
  return (
    <>
      {/* Head Tracking Alert */}
      <HeadTrackingAlert 
        isCalibrated={isCalibrated}
        isConnected={isConnected}
        error={error}
        headTrackingEnabled={headTrackingEnabled}
        readyForCalibration={readyForCalibration}
        calibrationMessage={calibrationMessage}
        calibrationState={calibrationState}
        showCalibrationSuccess={showCalibrationSuccess}
      />

      {/* Head Tracking Confirmation Popup */}
      <AnimatePresence>
        {showHeadTrackingPopup && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-white dark:bg-gray-800 rounded-2xl p-6 max-w-md w-full shadow-2xl border border-gray-200 dark:border-gray-700"
            >
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </div>
                
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                  Head Tracking Ready
                </h3>
                
                <p className="text-gray-600 dark:text-gray-300 mb-6">
                  We're ready to start monitoring your head position and eye contact during the interview. This helps ensure professional conduct.
                </p>
                
                <button
                  onClick={confirmHeadTracking}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 shadow-lg hover:shadow-xl"
                >
                  Start Head Tracking
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Warning Modal */}
      <WarningModal
        isOpen={showWarningModal}
        onClose={closeWarningModal}
        warningType={warningType}
        headTrackingEnabled={headTrackingEnabled}
      />

      {/* Calibration Warning Modal */}
      <AnimatePresence>
        {showCalibrationWarning && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-white dark:bg-gray-800 rounded-2xl p-6 max-w-md w-full shadow-2xl border border-gray-200 dark:border-gray-700"
            >
              <div className="text-center">
                <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                  Camera Position Required
                </h3>
                
                <p className="text-gray-600 dark:text-gray-300 mb-6">
                  Please position yourself directly in front of the camera and look straight ahead. The system needs to detect your face and eye position for accurate head tracking calibration.
                </p>
                
                <button
                  onClick={handleCalibrationWarningClose}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 shadow-lg hover:shadow-xl"
                >
                  OK, I'm Ready
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      
      <div className="relative min-h-screen interview-page-photo-bg">
        {/* Session header — dark bar, head tracking */}
        <header
          className="sticky top-0 z-40 border-b border-white/10 bg-[#0a0b12] px-4 py-3 sm:px-6 sm:py-3.5 text-white shadow-[0_4px_24px_rgba(0,0,0,0.35)] backdrop-blur-md"
          aria-label="Interview session controls"
        >
          <div className="mx-auto flex max-w-[1600px] flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
            {/* Left: title */}
            <div className="flex min-w-0 flex-shrink-0 items-center gap-2.5">
              <Sparkles className="h-5 w-5 shrink-0 text-sky-400" aria-hidden />
              <h1 className="truncate text-base font-semibold tracking-tight sm:text-lg">
                AI Interview Session
              </h1>
            </div>

            {/* Right: premium + head tracking */}
            <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-3 sm:gap-4">

              <label
                className={`flex cursor-pointer items-center gap-2.5 ${interviewInteractionLocked ? 'cursor-not-allowed opacity-55' : ''}`}
              >
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={headTrackingEnabled}
                    onChange={(e) => setHeadTrackingEnabled(e.target.checked)}
                    disabled={interviewInteractionLocked}
                    className="peer sr-only"
                  />
                  <div
                    className={[
                      'flex h-7 w-11 items-center rounded-full px-0.5 transition-colors duration-200',
                      interviewInteractionLocked
                        ? 'bg-zinc-600'
                        : headTrackingEnabled
                          ? 'bg-[#2563eb]'
                          : 'bg-zinc-600',
                    ].join(' ')}
                  >
                    <span
                      className={[
                        'block h-5 w-5 rounded-full bg-white shadow-md transition-transform duration-200',
                        headTrackingEnabled ? 'translate-x-5' : 'translate-x-0.5',
                      ].join(' ')}
                    />
                  </div>
                </div>
                <span className="text-sm font-medium text-white/95">Head Tracking</span>
              </label>

              {headTrackingStarted && headTrackingEnabled && (
                <span className="hidden items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1 text-xs font-semibold text-emerald-300 lg:inline-flex">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                  Live
                </span>
              )}
            </div>
          </div>
        </header>

        <motion.div className="flex flex-col xl:flex-row min-h-0 h-[calc(100dvh-5rem)] max-h-[calc(100dvh-5rem)] overflow-hidden">
          {/* Left - Interviewer Video */}
          <div 
            className="w-full xl:w-1/3 border-b xl:border-b-0 xl:border-r p-3 sm:p-4 lg:p-6 flex-shrink-0"
            style={{ 
              backgroundColor: 'color-mix(in srgb, var(--color-card) 78%, transparent)', 
              borderColor: 'var(--color-border)' 
            }}
          >
            <div className="h-full flex flex-col">
              {/* Interviewer Video Container */}
              <div 
                className="h-40 sm:h-52 md:h-64 lg:h-72 xl:flex-1 relative rounded-xl sm:rounded-2xl overflow-hidden shadow-lg border flex items-center justify-center"
                style={{ 
                  borderColor: isAudioPlaying ? 'var(--color-primary)' : 'var(--color-border)', 
                  background: 'radial-gradient(circle at top, color-mix(in srgb, var(--color-primary) 14%, transparent), var(--color-bg) 55%)',
                  borderWidth: isAudioPlaying ? '3px' : '1px'
                }}
              >
                <div className="ambient-orb h-40 w-40 opacity-70" style={{ background: 'radial-gradient(circle, #5B8CFF44, transparent 70%)' }} />
                {/* Interviewer Image and Info Container */}
                <div className="flex flex-col items-center">
                  {/* Interviewer Image - Circular with Wave Animation */}
                  <div className="relative mb-2 sm:mb-4">
                    <motion.img
                      src="/assets/interview/interviewer_1.png"
                      loading="lazy"
                      decoding="async"
                      fetchPriority="low"
                      alt="Sadhan"
                      className="w-24 h-24 sm:w-28 sm:h-28 md:w-32 md:h-32 lg:w-36 lg:h-36 xl:w-40 xl:h-40 object-cover object-top rounded-full border-2 sm:border-4 shadow-xl relative z-10"
                      style={{
                        borderColor: isAudioPlaying ? 'var(--color-primary)' : 'white'
                      }}
                      animate={isAudioPlaying ? {
                        borderWidth: ['2px', '3px', '2px', '4px', '2px', '3px', '2px'], // Responsive border changes
                        scale: [1, 1.01, 1, 1.02, 1, 1.01, 1], // Very subtle breathing effect
                      } : {
                        borderWidth: '2px',
                        scale: 1
                      }}
                      transition={isAudioPlaying ? {
                        duration: 2.5, // Match the first wave timing
                        repeat: Infinity,
                        ease: "easeInOut",
                        times: [0, 0.2, 0.4, 0.6, 0.8, 0.9, 1], // Match the first wave timing
                      } : {
                        duration: 0.3
                      }}
                    />
                    
                    {/* Wave Animation Overlay */}
                    <WaveAnimation 
                      isActive={isAudioPlaying || isChatLoading} 
                      size={140} // Base wave size (will be scaled responsively)
                      imageSize={128} // Image size
                      listening={isChatLoading} // Use listening pattern when processing
                    />
                  </div>
                  
                </div>
                
                {/* Live Indicator */}
                <div className="absolute top-2 sm:top-4 left-2 sm:left-4">
                  <div className="flex items-center gap-1 sm:gap-2 bg-green-500/90 backdrop-blur-sm text-white px-2 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs font-semibold shadow-lg border border-green-400/30">
                    <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-white rounded-full animate-pulse"></div>
                    <span className="tracking-wide text-xs">LIVE</span>
                  </div>
                </div>

                {/* Interviewer Label */}
                <div className="absolute bottom-2 sm:bottom-4 left-2 sm:left-4">
                  <h3 
                    className="font-bold text-sm sm:text-base md:text-lg lg:text-xl mb-1 drop-shadow-lg"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    Sadhan
                  </h3>
                  <p className="text-xs sm:text-sm text-[var(--color-text-secondary)]">Balanced interviewer</p>
                </div>
              </div>
            </div>
          </div>

          {/* Middle - User Camera */}
          <div 
            className="w-full xl:w-1/3 border-b xl:border-b-0 xl:border-r p-3 sm:p-4 lg:p-6 flex-shrink-0" 
            style={{ 
              backgroundColor: 'var(--color-card)', 
              borderColor: 'var(--color-border)' 
            }}
          >
            <div className="h-full flex flex-col">
              {/* User Video Container */}
              <div 
                className="h-40 sm:h-52 md:h-64 lg:h-72 xl:flex-1 relative rounded-xl sm:rounded-2xl overflow-hidden shadow-lg border"
                style={{ borderColor: 'var(--color-border)' }}
              >
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted={true}
                  className="w-full h-full object-cover"
                />

                {/* Camera Loading Indicator */}
                {isCameraLoading && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
                      <p className="text-white text-sm">Loading camera...</p>
                    </div>
                  </div>
                )}

                {/* Camera Error Message */}
                {cameraError && !isCameraLoading && (
                  <div className="absolute inset-0 bg-black/80 flex items-center justify-center p-4">
                    <div className="text-center max-w-md">
                      <div className="text-red-400 mb-4">
                        <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                        </svg>
                      </div>
                      <p className="text-white text-sm mb-4">{cameraError}</p>
                      <button
                        onClick={() => {
                          setCameraError(null);
                          setIsCameraLoading(true);
                          cameraRetryCountRef.current = 0;
                          // Trigger camera restart
                          if (streamRef.current) {
                            streamRef.current.getTracks().forEach(track => track.stop());
                            streamRef.current = null;
                          }
                          // Force re-render to trigger useEffect
                          setTimeout(() => {
                            window.location.reload();
                          }, 100);
                        }}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
                      >
                        Retry Camera
                      </button>
                    </div>
                  </div>
                )}

                {/* User Camera Label */}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent p-3 sm:p-4 md:p-6">
                  <h3 
                    className="font-bold text-sm sm:text-base md:text-lg lg:text-xl mb-1 text-white drop-shadow-lg"
                  >
                    Your Camera
                  </h3>
                </div>

                {/* Connection Status */}
                {!cameraError && !isCameraLoading && (
                  <div className="absolute top-2 sm:top-4 left-2 sm:left-4">
                    <div 
                      className="flex items-center gap-1 sm:gap-2 text-white px-2 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs font-semibold shadow-lg border border-white/20 backdrop-blur-sm"
                      style={{ backgroundColor: 'var(--color-primary)' }}
                    >
                      <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-white rounded-full"></div>
                      <span className="tracking-wide text-xs">CONNECTED</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right - Chat Conversation */}
          <div 
            className="w-full xl:w-1/3 flex-1 min-h-0 flex flex-col"
            style={{ backgroundColor: 'var(--color-card)' }}
          >
            <ChatWindow
              conversation={conversation}
              setConversation={setConversation}
              isLoading={isChatLoading}
              setIsLoading={setIsChatLoading}
              isAudioPlaying={isAudioPlaying}
              setIsAudioPlaying={setIsAudioPlaying}
              onStateChange={handleChatStateChange}
            />
          </div>
        </motion.div>
      </div>
    </>
  );
}

export default InterviewPage;
