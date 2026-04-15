import React, { useRef } from 'react';
import { FiUploadCloud, FiFileText, FiX, FiLoader } from 'react-icons/fi';
import { motion, AnimatePresence } from 'framer-motion';

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
};

const UploadBox = ({
  label,
  accept,
  file,
  setFile,
  error,
  setError,
  dragging,
  setDragging,
  type,
  otherFileExists,
  multiple = false, // default: false
  parsing = false, // new prop for parsing state
  disabled = false, // new prop for disabled state
}) => {
  const inputRef = useRef(null);

  const validTypes = {
    resume: [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ],
    job: ['application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
  };

  const handleDragEvents = (e, isEntering) => {
    if (disabled || parsing) return; // Disable drag events when disabled
    e.preventDefault();
    setDragging(isEntering);
  };

  const handleFileSelect = (e) => {
    if (disabled || parsing) return; // Disable file selection when disabled
    const selectedFiles = Array.from(e.target.files);
    validateFiles(selectedFiles);
  };

  const validateFiles = (files) => {
    if (disabled || parsing) return; // Disable validation when disabled
    if (!files || files.length === 0) return;

    if (!multiple && files.length > 1) {
      setError(`Only one file can be uploaded for ${label.toLowerCase()}.`);
      return;
    }

    if (!multiple && file) {
      setError(`${label} already uploaded. Remove it before uploading another.`);
      return;
    }

    const invalidFile = files.find((f) => !validTypes[type].includes(f.type));
    if (invalidFile) {
      setError(`Only ${accept} files are allowed for ${label.toLowerCase()}.`);
      return;
    }

    // If setFile is a function that expects a file (for job description parsing)
    if (typeof setFile === 'function' && files.length === 1) {
      setFile(files[0]);
    } else {
      setFile(multiple ? files : files[0]);
    }
    setError('');
  };

  const removeFile = (index = 0) => {
    if (disabled || parsing) return; // Disable file removal when disabled
    if (!multiple) {
      setFile(null);
      setError('');
      inputRef.current.value = null;
    } else {
      const newFiles = [...file];
      newFiles.splice(index, 1);
      setFile(newFiles.length ? newFiles : null);
    }
  };

  return (
    <motion.div
      className={`border-2 border-dashed rounded-xl p-6 text-center transition ${
        disabled || parsing
          ? 'cursor-not-allowed opacity-60'
          : dragging
          ? 'cursor-pointer border-[var(--color-primary)] scale-105 bg-[var(--color-bg-secondary)]'
          : parsing
          ? 'border-[var(--color-primary)] bg-[var(--color-bg-secondary)]'
          : 'cursor-pointer border-[var(--color-border)]'
      }`}
      onClick={() => {
        if (disabled || parsing) {
          return; // Disable clicking when disabled
        }
        if (!multiple && file) {
          setError(`${label} already uploaded. Remove it before uploading another.`);
        } else {
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => handleDragEvents(e, true)}
      onDragLeave={(e) => handleDragEvents(e, false)}
      onDrop={(e) => {
        if (disabled || parsing) return; // Disable drop when disabled
        handleDragEvents(e, false);
        const droppedFiles = Array.from(e.dataTransfer.files);
        validateFiles(droppedFiles);
      }}
    >
      {parsing ? (
        <div className="flex flex-col items-center">
          <FiLoader className="mx-auto w-10 h-10 text-[var(--color-primary)] mb-3 animate-spin" />
          <p className="text-sm text-[var(--color-primary)] font-medium mb-2">
            Parsing {label}...
          </p>
          <p className="text-xs text-[var(--color-text-secondary)]">
            Please wait while we extract job information
          </p>
        </div>
      ) : disabled ? (
        <div className="flex flex-col items-center">
          <FiUploadCloud className="mx-auto w-10 h-10 text-[var(--color-text-secondary)] mb-3" />
          <p className="text-sm text-[var(--color-text-secondary)] font-medium mb-2">
            {label} Upload Disabled
          </p>
          <p className="text-xs text-[var(--color-text-secondary)]">
            Please wait for question generation to complete
          </p>
        </div>
      ) : (
        <>
          <FiUploadCloud className="mx-auto w-10 h-10 text-[var(--color-primary)] mb-3" />
          <p className="text-sm text-[var(--color-text-secondary)] mb-2">
            <span className="block sm:hidden">
                Tap to upload your <strong>{label}</strong> ({accept})
            </span>
            <span className="hidden sm:block">
                Click or drag your <strong>{label}</strong> ({accept})
            </span>
          </p>
        </>
      )}
      
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleFileSelect}
        className="hidden"
        disabled={disabled || parsing}
      />

      <AnimatePresence>
        {file && !parsing && (multiple ? file : [file]).map((f, idx) => (
          <motion.div
            key={f.name + idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mt-4 p-4 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-sm shadow-sm backdrop-blur-sm"
          >
            <div className="flex-1 flex items-center gap-3 text-green-500 truncate text-left">
              <FiFileText className="w-5 h-5" />
              <span title={f.name} className="truncate">
                {f.name} ({formatSize(f.size)})
              </span>
            </div>
        <button
        type="button"
        onClick={(e) => {
            e.stopPropagation();
            e.currentTarget.blur(); 
            if (disabled || parsing) return; // Disable removal when disabled
            if (window.innerWidth <= 480) {
            const confirmDelete = window.confirm('Remove this file?');
            if (!confirmDelete) return;
            }
            removeFile(idx);
        }}
        disabled={disabled || parsing}
        className={`shrink-0 rounded-full p-2 sm:p-2.5 flex items-center justify-center transition-all duration-200 ease-in-out focus:outline-none focus:ring-2 ${
          disabled || parsing
            ? 'text-[var(--color-text-secondary)] opacity-50 cursor-not-allowed'
            : 'text-[var(--color-text-secondary)] hover:text-[var(--color-error)] hover:bg-[var(--color-error-bg)] active:scale-95 focus:ring-[var(--color-error)]'
        }`}
        aria-label="Remove file"
        >
        <FiX className="w-5 h-5" />
        </button>
          </motion.div>
        ))}
      </AnimatePresence>

      {error && <p className="text-sm text-[var(--color-error)] mt-2">{error}</p>}
    </motion.div>
  );
};

export default UploadBox;