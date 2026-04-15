import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';

const HeadTrackingAlert = ({ 
  isCalibrated, 
  isConnected, 
  error, 
  headTrackingEnabled = true,
  readyForCalibration = false,
  calibrationMessage = '',
  calibrationState = 'idle',
  showCalibrationSuccess = false
}) => {
  // Show error message if there's an error
  if (error) {
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="fixed top-3 sm:top-4 left-1/2 transform -translate-x-1/2 z-50 mx-3 sm:mx-4"
        >
          <div className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg shadow-lg border backdrop-blur-sm bg-red-500/90 text-white border-red-400/30 max-w-sm sm:max-w-md">
            <svg className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <div className="flex flex-col min-w-0">
              <span className="font-semibold text-xs sm:text-sm">Head Tracking Error</span>
              <span className="text-xs opacity-90 truncate">{error}</span>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>
    );
  }

  // Show calibration success message
  if (showCalibrationSuccess) {
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="fixed top-3 sm:top-4 left-1/2 transform -translate-x-1/2 z-50 mx-3 sm:mx-4"
        >
          <div className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg shadow-lg border backdrop-blur-sm bg-green-500/90 text-white border-green-400/30 max-w-sm sm:max-w-md">
            <svg className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <div className="flex flex-col min-w-0">
              <span className="font-semibold text-xs sm:text-sm">Calibration Successful!</span>
              <span className="text-xs opacity-90">Head tracking is now active and monitoring</span>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>
    );
  }

  // Don't show anything if not connected
  if (!isConnected) {
    return null;
  }

  // Show calibration status (only for head tracking)
  if (headTrackingEnabled && !isCalibrated) {
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="fixed top-3 sm:top-4 left-1/2 transform -translate-x-1/2 z-50 mx-3 sm:mx-4"
        >
          <div className={`flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg shadow-lg border backdrop-blur-sm max-w-sm sm:max-w-md ${
            calibrationState === 'checking' 
              ? 'bg-blue-500/90 text-white border-blue-400/30'
              : readyForCalibration 
                ? 'bg-green-500/90 text-white border-green-400/30' 
                : 'bg-yellow-500/90 text-white border-yellow-400/30'
          }`}>
            {calibrationState === 'checking' ? (
              <>
                <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin flex-shrink-0" />
                <div className="flex flex-col min-w-0">
                  <span className="font-semibold text-xs sm:text-sm">Checking camera position...</span>
                  <span className="text-xs opacity-90">Please look directly at the camera</span>
                </div>
              </>
            ) : readyForCalibration ? (
              <>
                <div className="w-4 h-4 sm:w-5 sm:h-5 bg-white rounded-full animate-pulse flex-shrink-0" />
                <span className="font-semibold text-xs sm:text-sm">Ready to calibrate - please look at camera</span>
              </>
            ) : (
              <>
                <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin flex-shrink-0" />
                <div className="flex flex-col min-w-0">
                  <span className="font-semibold text-xs sm:text-sm">Preparing head tracking...</span>
                  {calibrationMessage && (
                    <span className="text-xs opacity-90 truncate">{calibrationMessage}</span>
                  )}
                </div>
              </>
            )}
          </div>
        </motion.div>
      </AnimatePresence>
    );
  }

  // Don't show anything else - popup modal handles all critical warnings
  return null;
};

export default HeadTrackingAlert;
