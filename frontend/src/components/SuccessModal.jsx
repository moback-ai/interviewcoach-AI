import React from 'react';
import { FiCheckCircle, FiX } from 'react-icons/fi';

const SuccessModal = ({ isOpen, onClose, title, message, details, customAction }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-xl w-full max-w-xs sm:max-w-sm md:max-w-md lg:max-w-lg shadow-2xl transform transition-all duration-200 mx-2">
        {/* Header */}
        <div className="flex items-center justify-between p-3 sm:p-4 md:p-6 border-b border-[var(--color-border)]">
          <div className="flex items-center space-x-2 sm:space-x-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center">
              <FiCheckCircle className="w-4 h-4 sm:w-5 sm:h-5 text-green-600 dark:text-green-400" />
            </div>
            <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)]">
              {title || 'Success!'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors duration-200 p-1 rounded-lg hover:bg-[var(--color-input-bg)]"
          >
            <FiX size={18} className="sm:w-5 sm:h-5" />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-3 sm:p-4 md:p-6">
          <p className="text-sm sm:text-base text-[var(--color-text-secondary)] leading-relaxed mb-3 sm:mb-4">
            {message}
          </p>
          
          {details && (
            <div className="bg-[var(--color-input-bg)] border border-[var(--color-border)] rounded-lg p-3 sm:p-4 mb-3 sm:mb-4">
              <h4 className="font-medium text-[var(--color-text-primary)] mb-2 sm:mb-3 text-sm">
                Details:
              </h4>
              <div className="space-y-1.5 sm:space-y-2">
                {details.map((detail, index) => (
                  <div key={index} className="text-xs sm:text-sm text-[var(--color-text-secondary)]">
                    {detail}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3">
            {customAction && (
              <button
                onClick={customAction.onClick}
                className="w-full sm:w-auto px-4 sm:px-6 py-2.5 sm:py-3 bg-[var(--color-accent)] text-white rounded-lg hover:bg-[var(--color-accent)]/90 transition-colors duration-200 font-medium shadow-sm hover:shadow-md text-sm sm:text-base"
              >
                {customAction.label}
              </button>
            )}
            <button
              onClick={onClose}
              className="w-full sm:w-auto px-4 sm:px-6 py-2.5 sm:py-3 bg-[var(--color-primary)] text-white rounded-lg hover:bg-[var(--color-primary)]/90 transition-colors duration-200 font-medium shadow-sm hover:shadow-md text-sm sm:text-base"
            >
              {customAction ? 'Close' : 'Continue'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SuccessModal;
