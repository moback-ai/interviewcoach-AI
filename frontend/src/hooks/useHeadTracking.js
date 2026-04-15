import { useEffect, useRef, useState, useCallback } from 'react';
import { io } from 'socket.io-client';

export const useHeadTracking = (enabled = true, onCalibrationSuccess = null) => {
  const [isCalibrated, setIsCalibrated] = useState(false);
  const [isLooking, setIsLooking] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const [readyForCalibration, setReadyForCalibration] = useState(false);
  const [calibrationMessage, setCalibrationMessage] = useState('');
  
  const socketRef = useRef(null);
  const videoRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const calibrateModeRef = useRef(false);
  const sendingFramesRef = useRef(true);
  const hasInitializedRef = useRef(false);

  // Frame capture function
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !videoRef.current.videoWidth || !videoRef.current.videoHeight) {
      return null;
    }

    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.8);
  }, []);





  // Stop frame sending (define this BEFORE startFrameSending)
  const stopFrameSending = useCallback(() => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
      console.log('📡 Frame sending stopped');
    }
  }, []);

  // Start frame sending
  const startFrameSending = useCallback(() => {
    if (!enabled || !socketRef.current) return;
    
    // Don't start if frame sending is paused
    if (!sendingFramesRef.current) {
      console.log('⏸️ Frame sending is paused, not starting');
      return;
    }

    // Clear any existing interval before starting new one
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }

    console.log('📡 Starting frame sending...');
    frameIntervalRef.current = setInterval(() => {
      if (!sendingFramesRef.current || !socketRef.current) return;

      const img = captureFrame();
      if (!img) {
        console.log('⚠️ No frame captured, skipping send');
        return;
      }

      try {
        socketRef.current.emit('frame', { 
          image: img, 
          calibrate: calibrateModeRef.current 
        });
      } catch (error) {
        console.warn('Frame sending error:', error);
        // Stop frame sending if socket is broken
        stopFrameSending();
      }
    }, 200); // Send frame every 200ms
  }, [enabled, captureFrame, stopFrameSending]);

  // Start calibration
  const startCalibration = useCallback(() => {
    if (!enabled || !socketRef.current) return;
    
    // Prevent multiple simultaneous calibrations
    if (calibrateModeRef.current) {
      console.log('⚠️ Calibration already in progress, skipping...');
      return;
    }

    console.log('🎯 Starting head tracking calibration...');
    calibrateModeRef.current = true;
    setIsCalibrated(false);
    setReadyForCalibration(false);
    setCalibrationMessage('');

    // Stop calibration after 5 seconds (increased to give more time for user to look at camera)
    setTimeout(() => {
      calibrateModeRef.current = false;
      console.log('✅ Calibration attempt finished');
    }, 5000);
  }, [enabled]);

  // Check if ready for calibration (without starting it)
  const checkReadyForCalibration = useCallback(() => {
    if (!enabled || !socketRef.current) return false;
    return readyForCalibration;
  }, [enabled, readyForCalibration]);

  // Pause/resume frame sending
  const pauseFrameSending = useCallback(() => {
    sendingFramesRef.current = false;
    console.log('⏸️ Frame sending paused');
  }, []);

  const resumeFrameSending = useCallback(() => {
    sendingFramesRef.current = true;
    console.log('▶️ Frame sending resumed');
    
    // Restart frame sending if head tracking is enabled and socket is connected
    if (enabled && socketRef.current && isConnected) {
      startFrameSending();
    }
  }, [enabled, isConnected, startFrameSending]);

  // Start monitoring based on enabled state
  const startMonitoring = useCallback(() => {
    console.log(`🎬 Starting monitoring (head tracking: ${enabled ? 'enabled' : 'disabled'})`);
    
    if (enabled) {
      startFrameSending();
    } else {
      console.log('🛑 Head tracking disabled - no monitoring');
    }
  }, [enabled, startFrameSending]);

  // Stop monitoring
  const stopMonitoring = useCallback(() => {
    console.log('🛑 Stopping all monitoring');
    stopFrameSending();
  }, [stopFrameSending]);

  // Initialize socket connection
  useEffect(() => {
    if (!enabled) {
      // Clean up socket connection when head tracking is disabled
      if (socketRef.current) {
        console.log('🔌 Closing socket connection (head tracking disabled)');
        socketRef.current.disconnect();
        socketRef.current = null;
        setIsConnected(false);
        setIsCalibrated(false);
        setIsLooking(true);
        setError(null);
      }
      return;
    }

    console.log('🔗 Initializing socket connection for head tracking');
    const socket = io(import.meta.env.VITE_API_BASE_URL, {
      transports: ['websocket', 'polling'],
      timeout: 20000,
      forceNew: true,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000
    });

    socket.on('connect', () => {
      console.log('🔗 Socket connected for head tracking');
      setIsConnected(true);
      setError(null);
      
      // Only reset calibration for truly new sessions, not when re-enabling
      if (!hasInitializedRef.current) {
        console.log('🔄 New session detected, resetting calibration state');
        socket.emit('reset_calibration');
        hasInitializedRef.current = true;
      } else {
        console.log('🔄 Re-enabling head tracking, preserving calibration state');
      }
      
      // Resume frame sending if it was paused and head tracking is enabled
      if (enabled && !sendingFramesRef.current) {
        console.log('🔄 Resuming frame sending after socket reconnection');
        sendingFramesRef.current = true;
        startFrameSending();
      }
    });

    socket.on('disconnect', () => {
      console.log('🔌 Socket disconnected');
      setIsConnected(false);
      // Stop frame sending when socket disconnects
      stopFrameSending();
    });

    socket.on('connect_error', (error) => {
      console.error('🔌 Socket connection error:', error);
      setError('Connection failed - Backend may not be running');
      setIsConnected(false);
      // Don't show error if it's just a connection issue - user can still use person detection
      console.log('⚠️ Head tracking backend not available, falling back to person detection mode');
    });

    socket.on('response', (data) => {
      if (data.error) {
        console.error('Head tracking error:', data.error);
        setError(data.error);
        // Stop sending frames when there's an error to prevent continuous errors
        stopFrameSending();
        return;
      }
      
      // Clear any previous errors if we get a successful response
      if (error) {
        setError(null);
      }

      if (data.calibrated !== undefined) {
        if (data.calibrated) {
          setIsCalibrated(true);
          setReadyForCalibration(false);
          setCalibrationMessage('');
          console.log('✅ Head tracking calibrated');
          
          // Notify parent component of successful calibration
          if (onCalibrationSuccess) {
            onCalibrationSuccess();
          }
        } else {
          setIsCalibrated(false);
          console.log('🔄 Calibration reset');
        }
      }

      if (data.calibration_reset) {
        setIsCalibrated(false);
        setReadyForCalibration(false);
        setCalibrationMessage('');
        console.log('🔄 Calibration state reset for new session');
      }

      if (data.ready_for_calibration !== undefined) {
        const wasReady = readyForCalibration;
        setReadyForCalibration(data.ready_for_calibration);
        if (!wasReady && data.ready_for_calibration) {
          console.log('🎯 User is now ready for calibration');
        } else if (wasReady && !data.ready_for_calibration) {
          console.log('⚠️ User is no longer ready for calibration');
        }
      } else {
        // If ready_for_calibration is not sent, assume false (not ready for calibration)
        // This prevents the frontend from thinking user is ready when backend doesn't send this
        if (readyForCalibration) {
          console.log('🔄 ready_for_calibration not sent by backend, setting to false');
          setReadyForCalibration(false);
        }
      }

      if (data.message) {
        setCalibrationMessage(data.message);
        console.log('📝 Calibration message:', data.message);
      }

      if (data.looking !== undefined) {
        setIsLooking(data.looking);
      }
    });

    socketRef.current = socket;

    return () => {
      if (socketRef.current) {
        console.log('🔌 Cleaning up socket connection');
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [enabled, stopFrameSending]); // Re-run when enabled state changes



  // Cleanup on unmount
  useEffect(() => {
    return () => {
      console.log('🧹 Cleaning up head tracking resources');
      stopFrameSending();
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [stopFrameSending]);

  // Additional cleanup for React Strict Mode
  useEffect(() => {
    const cleanup = () => {
      if (frameIntervalRef.current) {
        clearInterval(frameIntervalRef.current);
        frameIntervalRef.current = null;
      }
    };

    return cleanup;
  }, []);

  return {
    // State
    isCalibrated,
    isLooking,
    isConnected,
    error,
    readyForCalibration, // Ready for calibration status
    calibrationMessage, // Calibration message
    
    // Refs
    videoRef,
    
    // Functions
    startFrameSending,
    stopFrameSending,
    startCalibration,
    checkReadyForCalibration, // Check if ready for calibration
    pauseFrameSending,
    resumeFrameSending,
    captureFrame,
    startMonitoring, // Unified monitoring start
    stopMonitoring   // Unified monitoring stop
  };
};
