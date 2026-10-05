import { useEffect, useRef, useState, useCallback } from 'react';
import { io } from 'socket.io-client';
import { getAccessToken } from '../lib/authClient';
import { getBackendOrigin } from '../utils/apiConfig';

const FRAME_INTERVAL_MS = 333;
const MAX_FRAME_WIDTH = 640;
const JPEG_QUALITY = 0.8;

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
  const canvasRef = useRef(null);

  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    if (!video?.videoWidth || !video?.videoHeight) {
      return null;
    }

    const scale = Math.min(1, MAX_FRAME_WIDTH / video.videoWidth);
    const width = Math.max(1, Math.round(video.videoWidth * scale));
    const height = Math.max(1, Math.round(video.videoHeight * scale));

    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas');
    }
    const canvas = canvasRef.current;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, width, height);
    return canvas.toDataURL('image/jpeg', JPEG_QUALITY);
  }, []);

  const stopFrameSending = useCallback(() => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
  }, []);

  const startFrameSending = useCallback(() => {
    if (!enabled || !socketRef.current || !sendingFramesRef.current) {
      return;
    }

    stopFrameSending();
    frameIntervalRef.current = setInterval(() => {
      if (!sendingFramesRef.current || !socketRef.current || document.hidden) {
        return;
      }

      const img = captureFrame();
      if (!img) {
        return;
      }

      try {
        socketRef.current.emit('frame', {
          image: img,
          calibrate: calibrateModeRef.current,
        });
      } catch (sendError) {
        console.warn('Frame sending error:', sendError);
        stopFrameSending();
      }
    }, FRAME_INTERVAL_MS);
  }, [enabled, captureFrame, stopFrameSending]);

  const startCalibration = useCallback(() => {
    if (!enabled || !socketRef.current || calibrateModeRef.current) {
      return;
    }

    calibrateModeRef.current = true;
    setIsCalibrated(false);
    setReadyForCalibration(false);
    setCalibrationMessage('');

    setTimeout(() => {
      calibrateModeRef.current = false;
    }, 5000);
  }, [enabled]);

  const checkReadyForCalibration = useCallback(() => {
    if (!enabled || !socketRef.current) return false;
    return readyForCalibration;
  }, [enabled, readyForCalibration]);

  const pauseFrameSending = useCallback(() => {
    sendingFramesRef.current = false;
  }, []);

  const resumeFrameSending = useCallback(() => {
    sendingFramesRef.current = true;
    if (enabled && socketRef.current && isConnected) {
      startFrameSending();
    }
  }, [enabled, isConnected, startFrameSending]);

  const startMonitoring = useCallback(() => {
    if (enabled) {
      startFrameSending();
    }
  }, [enabled, startFrameSending]);

  const stopMonitoring = useCallback(() => {
    stopFrameSending();
  }, [stopFrameSending]);

  useEffect(() => {
    if (!enabled) {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
        setIsConnected(false);
        setIsCalibrated(false);
        setIsLooking(true);
        setError(null);
      }
      return;
    }

    const token = getAccessToken();
    const socket = io(getBackendOrigin() || window.location.origin, {
      transports: ['websocket', 'polling'],
      path: '/socket.io',
      timeout: 20000,
      forceNew: true,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      withCredentials: true,
      auth: token ? { token } : {},
    });

    socket.on('connect', () => {
      setIsConnected(true);
      setError(null);
      if (!hasInitializedRef.current) {
        socket.emit('reset_calibration');
        hasInitializedRef.current = true;
      }
      if (enabled && !sendingFramesRef.current) {
        sendingFramesRef.current = true;
        startFrameSending();
      }
    });

    socket.on('disconnect', () => {
      setIsConnected(false);
      stopFrameSending();
    });

    socket.on('connect_error', () => {
      setError('Connection failed - Backend may not be running');
      setIsConnected(false);
    });

    socket.on('response', (data) => {
      if (data.error) {
        setError(data.error);
        stopFrameSending();
        return;
      }

      if (error) {
        setError(null);
      }

      if (data.calibrated !== undefined) {
        if (data.calibrated) {
          setIsCalibrated(true);
          setReadyForCalibration(false);
          setCalibrationMessage('');
          onCalibrationSuccess?.();
        } else {
          setIsCalibrated(false);
        }
      }

      if (data.calibration_reset) {
        setIsCalibrated(false);
        setReadyForCalibration(false);
        setCalibrationMessage('');
      }

      if (data.ready_for_calibration !== undefined) {
        setReadyForCalibration(data.ready_for_calibration);
      }

      if (data.message) {
        setCalibrationMessage(data.message);
      }

      if (data.looking !== undefined) {
        setIsLooking(data.looking);
      }
    });

    socketRef.current = socket;

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [enabled, stopFrameSending, startFrameSending, onCalibrationSuccess, error]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) {
        stopFrameSending();
      } else if (enabled && socketRef.current?.connected && sendingFramesRef.current) {
        startFrameSending();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [enabled, startFrameSending, stopFrameSending]);

  useEffect(() => () => {
    stopFrameSending();
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
  }, [stopFrameSending]);

  return {
    isCalibrated,
    isLooking,
    isConnected,
    error,
    readyForCalibration,
    calibrationMessage,
    videoRef,
    startFrameSending,
    stopFrameSending,
    startCalibration,
    checkReadyForCalibration,
    pauseFrameSending,
    resumeFrameSending,
    captureFrame,
    startMonitoring,
    stopMonitoring,
  };
};
