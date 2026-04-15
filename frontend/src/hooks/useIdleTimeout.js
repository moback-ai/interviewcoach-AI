import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useOperation } from '../contexts/OperationContext';
import { supabase } from '../supabaseClient';

/**
 * Custom hook to handle idle timeout and automatic logout
 * @param {number} idleTimeoutMinutes - Minutes of inactivity before logout (default: 30)
 * @param {number} warningTimeSeconds - Seconds before logout to show warning (default: 30)
 * @returns {object} { showWarning, timeRemaining, resetTimer }
 */
export const useIdleTimeout = (idleTimeoutMinutes = 30, warningTimeSeconds = 30) => {
  const { isAuthenticated } = useAuth();
  const { isOperationInProgress } = useOperation();
  const [showWarning, setShowWarning] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(warningTimeSeconds);
  const idleTimerRef = useRef(null);
  const warningTimerRef = useRef(null);
  const logoutTimerRef = useRef(null);
  const countdownIntervalRef = useRef(null);
  const lastActivityRef = useRef(Date.now());
  const isWarningShownRef = useRef(false);

  // Convert minutes to milliseconds
  const idleTimeoutMs = idleTimeoutMinutes * 60 * 1000;
  const warningTimeMs = warningTimeSeconds * 1000;

  // ✅ ADD: Check if timeout is disabled (null means disabled)
  const isDisabled = idleTimeoutMinutes === null || idleTimeoutMinutes === undefined;

  // Handle logout
  const handleLogout = useCallback(async () => {
    console.log('[Idle Timeout] Logging out due to inactivity');
    await supabase.auth.signOut();
    window.location.href = '/login';
  }, []);

  // Reset the idle timer
  const resetTimer = useCallback(() => {
    // ✅ ADD: Early return if disabled
    if (isDisabled) {
      return;
    }

    // Clear existing timers
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
    }
    if (warningTimerRef.current) {
      clearTimeout(warningTimerRef.current);
    }
    if (logoutTimerRef.current) {
      clearTimeout(logoutTimerRef.current);
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
    }

    // Hide warning if it was shown
    if (isWarningShownRef.current) {
      setShowWarning(false);
      setTimeRemaining(warningTimeSeconds);
      isWarningShownRef.current = false;
    }

    // Update last activity time
    lastActivityRef.current = Date.now();

    // Only set up timers if user is authenticated AND no critical operation is in progress
    if (!isAuthenticated || isOperationInProgress) {
      return;
    }

    // Set timer for warning (idleTimeout - warningTime)
    warningTimerRef.current = setTimeout(() => {
      setShowWarning(true);
      isWarningShownRef.current = true;
      
      // Start countdown
      let remaining = warningTimeSeconds;
      setTimeRemaining(remaining);
      
      countdownIntervalRef.current = setInterval(() => {
        remaining -= 1;
        setTimeRemaining(remaining);
        
        if (remaining <= 0) {
          if (countdownIntervalRef.current) {
            clearInterval(countdownIntervalRef.current);
            countdownIntervalRef.current = null;
          }
        }
      }, 1000);

      // Set timer for actual logout
      logoutTimerRef.current = setTimeout(() => {
        if (countdownIntervalRef.current) {
          clearInterval(countdownIntervalRef.current);
          countdownIntervalRef.current = null;
        }
        handleLogout();
      }, warningTimeMs);
    }, idleTimeoutMs - warningTimeMs);

    // Set timer for full idle timeout (as backup)
    idleTimerRef.current = setTimeout(() => {
      if (!isWarningShownRef.current) {
        handleLogout();
      }
    }, idleTimeoutMs);
  }, [isAuthenticated, idleTimeoutMs, warningTimeMs, warningTimeSeconds, handleLogout, isDisabled]);

  // Track user activity
  useEffect(() => {
    // ✅ ADD: Early return if disabled
    if (isDisabled) {
      return;
    }

    if (!isAuthenticated || isOperationInProgress) {
      // Clear timers if user is not authenticated OR if a critical operation is in progress
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
      setShowWarning(false);
      isWarningShownRef.current = false;
      return;
    }

    // Events that indicate user activity
    const activityEvents = [
      'mousedown',
      'mousemove',
      'keypress',
      'scroll',
      'touchstart',
      'click',
      'keydown'
    ];

    // Add event listeners
    const handleActivity = () => {
      // Only reset if enough time has passed since last activity (debounce)
      const timeSinceLastActivity = Date.now() - lastActivityRef.current;
      if (timeSinceLastActivity > 1000) { // Debounce: reset only if > 1 second since last activity
        resetTimer();
      }
    };

    activityEvents.forEach(event => {
      document.addEventListener(event, handleActivity, true);
    });

    // Initialize timer on mount
    resetTimer();

    // Cleanup
    return () => {
      activityEvents.forEach(event => {
        document.removeEventListener(event, handleActivity, true);
      });
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    };
  }, [isAuthenticated, isOperationInProgress, resetTimer, isDisabled]);

  // Handle user staying active (clicking "Stay Logged In")
  const handleStayLoggedIn = useCallback(() => {
    resetTimer();
  }, [resetTimer]);

  return {
    showWarning,
    timeRemaining,
    resetTimer: handleStayLoggedIn
  };
};

export default useIdleTimeout;

