import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiClock, FiAlertCircle } from 'react-icons/fi';

/**
 * Modal component that warns user about imminent logout due to inactivity
 */
const IdleTimeoutModal = ({ isOpen, timeRemaining, onStayLoggedIn, onLogout }) => {
  useEffect(() => {
    // Prevent body scroll when modal is open
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[9999] p-4"
        onClick={onLogout} // Click outside to logout immediately
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
          onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside
        >
          {/* Decorative corner elements */}
          <div className="absolute top-4 right-4">
            <div className="w-2 h-2 bg-orange-400/50 rounded-full animate-pulse" style={{ animationDelay: '0ms' }}></div>
          </div>
          <div className="absolute bottom-4 left-4">
            <div className="w-2 h-2 bg-amber-400/50 rounded-full animate-pulse" style={{ animationDelay: '200ms' }}></div>
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
                  <FiClock className="w-10 h-10 text-orange-600 dark:text-orange-400" />
                </div>
              </div>
            </div>

            {/* Title */}
            <motion.h3
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="text-2xl sm:text-3xl font-bold mb-3 bg-gradient-to-r from-orange-600 via-amber-600 to-yellow-600 dark:from-orange-400 dark:via-amber-400 dark:to-yellow-400 bg-clip-text text-transparent"
            >
              Session Timeout Warning
            </motion.h3>

            {/* Countdown Timer */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 }}
              className="mb-4"
            >
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-orange-100 dark:bg-orange-900/30 border border-orange-300 dark:border-orange-700">
                <FiAlertCircle className="w-5 h-5 text-orange-600 dark:text-orange-400" />
                <span className="text-lg font-bold text-orange-700 dark:text-orange-300">
                  {timeRemaining} {timeRemaining === 1 ? 'second' : 'seconds'}
                </span>
              </div>
            </motion.div>

            {/* Message */}
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="mb-8 leading-relaxed text-sm sm:text-base px-2"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              You've been inactive for a while. You'll be automatically logged out in {timeRemaining} {timeRemaining === 1 ? 'second' : 'seconds'} for security reasons.
            </motion.p>
            
            {/* Action Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="flex gap-3"
            >
              <button
                onClick={onLogout}
                className="flex-1 py-3 px-4 rounded-xl border border-[var(--color-border)] hover:bg-[var(--color-hover)] transition-colors font-semibold"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Log Out Now
              </button>
              <button
                onClick={onStayLoggedIn}
                className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-orange-500 via-amber-500 to-yellow-500 hover:from-orange-600 hover:via-amber-600 hover:to-yellow-600 text-white font-semibold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-105 active:scale-95 relative overflow-hidden group"
              >
                {/* Shine effect on hover */}
                <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000"></span>
                <span className="relative">Stay Logged In</span>
              </button>
            </motion.div>

            {/* Info text */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="text-xs mt-4"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Click "Stay Logged In" to continue your session
            </motion.p>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default IdleTimeoutModal;

