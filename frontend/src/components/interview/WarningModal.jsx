import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { EyeOff, User, Users, AlertTriangle, X } from 'lucide-react';

const WarningModal = ({ 
  isOpen, 
  onClose, 
  warningType, 
  headTrackingEnabled 
}) => {
  if (!isOpen) return null;

  const getWarningContent = () => {
    if (headTrackingEnabled) {
      // Eye tracking warnings
      return {
        title: 'Eye Contact Warning',
        message: 'Please maintain eye contact with the camera for a professional interview experience.',
        icon: <EyeOff className="w-8 h-8" style={{ color: '#f59e0b' }} />,
        buttonColor: '#f59e0b',
        buttonHoverColor: '#d97706'
      };
    } else {
      // Person detection warnings
      switch (warningType) {
        case 'none':
          return {
            title: 'No Person Detected',
            message: 'Please move into view of the camera. No person is currently visible.',
            icon: <User className="w-8 h-8" style={{ color: 'var(--color-error)' }} />,
            buttonColor: 'var(--color-error)',
            buttonHoverColor: '#dc2626'
          };
        case 'multiple':
          return {
            title: 'Multiple People Detected',
            message: 'Only the candidate should be visible in the camera. Please ensure you are alone in the frame.',
            icon: <Users className="w-8 h-8" style={{ color: '#f59e0b' }} />,
            buttonColor: '#f59e0b',
            buttonHoverColor: '#d97706'
          };
        default:
          return {
            title: 'Camera Issue',
            message: 'There seems to be an issue with the camera detection. Please check your setup.',
            icon: <AlertTriangle className="w-8 h-8" style={{ color: 'var(--color-text-secondary)' }} />,
            buttonColor: 'var(--color-text-secondary)',
            buttonHoverColor: 'var(--color-text-primary)'
          };
      }
    }
  };

  const warning = getWarningContent();

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-3 sm:p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="rounded-xl sm:rounded-2xl p-4 sm:p-6 max-w-sm sm:max-w-md w-full shadow-2xl relative border"
          style={{ 
            backgroundColor: 'var(--color-card)',
            borderColor: 'var(--color-border)'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Close Button */}
          <button
            onClick={onClose}
            className="absolute top-3 sm:top-4 right-3 sm:right-4 p-1 rounded-full transition-colors"
            style={{ 
              color: 'var(--color-text-secondary)',
              backgroundColor: 'transparent'
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = 'var(--color-hover)';
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = 'transparent';
            }}
          >
            <X className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>

          <div className="text-center mt-6 sm:mt-8">
            {/* Warning Icon */}
            <div className="flex justify-center mb-3 sm:mb-4">
              <div className="w-12 h-12 sm:w-16 sm:h-16 flex items-center justify-center">
                {warning.icon}
              </div>
            </div>
            
            {/* Warning Title */}
            <h3 
              className="text-lg sm:text-xl font-bold mb-2 sm:mb-3"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {warning.title}
            </h3>
            
            {/* Warning Message */}
            <p 
              className="mb-4 sm:mb-6 leading-relaxed text-sm sm:text-base"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {warning.message}
            </p>
            
            {/* Action Button */}
            <button
              onClick={onClose}
              className="text-white font-semibold py-2.5 sm:py-3 px-4 sm:px-6 rounded-lg transition-colors duration-200 shadow-lg hover:shadow-xl w-full text-sm sm:text-base"
              style={{ 
                backgroundColor: warning.buttonColor,
                color: 'white'
              }}
              onMouseEnter={(e) => {
                e.target.style.backgroundColor = warning.buttonHoverColor;
              }}
              onMouseLeave={(e) => {
                e.target.style.backgroundColor = warning.buttonColor;
              }}
            >
              I Understand
            </button>
           
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default WarningModal;
