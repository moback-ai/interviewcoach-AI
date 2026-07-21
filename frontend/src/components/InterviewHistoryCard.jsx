import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { FiClock, FiCheckCircle, FiXCircle, FiPlay, FiRefreshCw, FiList } from 'react-icons/fi';
import NoticeModal from './common/NoticeModal';
import { fetchInterviewQuota, scheduleInterview } from '../utils/scheduleInterview';

const InterviewHistoryCard = ({ questionSet, pairing, isRegenerating, isAnyRegenerating = false }) => {
  const [loading, setLoading] = useState(false);
  const [retakeModalOpen, setRetakeModalOpen] = useState(false);
  const [noticeModal, setNoticeModal] = useState({ isOpen: false, title: '', message: '' });
  const [interviewQuota, setInterviewQuota] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const loadQuota = async () => {
      try {
        const quota = await fetchInterviewQuota();
        if (!cancelled) {
          setInterviewQuota(quota);
        }
      } catch (error) {
        console.warn('Could not load interview quota:', error);
      }
    };
    loadQuota();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!retakeModalOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [retakeModalOpen]);

  // Check if this specific tile or any tile is regenerating
  const isDisabled = isRegenerating || isAnyRegenerating;

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
      case 'ENDED':
        return <FiCheckCircle className="text-green-500" size={16} />;
      case 'in_progress':
        return <FiClock className="text-yellow-500" size={16} />;
      case 'scheduled':
        return <FiClock className="text-blue-500" size={16} />;
      case 'cancelled':
        return <FiXCircle className="text-red-500" size={16} />;
      case 'STARTED':
        return <FiPlay className="text-orange-500" size={16} />;
      default:
        return <FiClock className="text-gray-500" size={16} />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'completed':
      case 'ENDED':
        return 'Completed';
      case 'in_progress':
        return 'In Progress';
      case 'scheduled':
        return 'Scheduled';
      case 'cancelled':
        return 'Cancelled';
      case 'STARTED':
        return 'Started';
      default:
        return status;
    }
  };

  const handleRetakeClick = () => {
    setRetakeModalOpen(true);
  };

  const runScheduleInterview = async ({ retakeFrom } = {}) => {
    setLoading(true);
    try {
      await scheduleInterview({
        resumeId: pairing.resume_id,
        jdId: pairing.jd_id,
        questionSet: questionSet.questionSetNumber,
        retakeFrom,
      });
    } catch (error) {
      console.error('Error scheduling interview:', error);
      setNoticeModal({
        isOpen: true,
        title: retakeFrom ? 'Could not start retake' : 'Could not schedule interview',
        message: error.message,
      });
      setLoading(false);
    }
  };

  const handleScheduleClick = () => runScheduleInterview();

  const handleRetakeConfirm = async () => {
    setRetakeModalOpen(false);
    const originalInterviewId = questionSet.interviews[0]?.id;
    if (!originalInterviewId) {
      setNoticeModal({
        isOpen: true,
        title: 'Retake unavailable',
        message: 'No original interview found for retake',
      });
      return;
    }
    await runScheduleInterview({ retakeFrom: originalInterviewId });
  };

  const scheduleButtonLabel = loading
    ? 'Creating...'
    : interviewQuota?.free_remaining > 0
      ? 'Schedule Interview (Free)'
      : 'Schedule Interview';

  const hasCompletedInterviews = questionSet.interviews.some(interview => 
    interview.status === 'completed' || interview.status === 'ENDED'
  );

  const questionCount = Array.isArray(questionSet.questions)
    ? questionSet.questions.length
    : Number(questionSet.questionCount) || 0;

  return (
    <>
      <div className="bg-[var(--color-input-bg)] rounded-xl border border-[var(--color-border)] p-3 sm:p-4 md:p-6 shadow-md hover:shadow-lg transition-all duration-300">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-3 sm:mb-4 gap-3 sm:gap-0">
          <div className="flex items-center space-x-2 sm:space-x-3 min-w-0">
            <div className="bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] text-white rounded-xl w-8 h-8 sm:w-10 sm:h-10 md:w-12 md:h-12 flex items-center justify-center shadow-lg shrink-0">
              <span className="text-sm sm:text-base md:text-lg font-bold">{questionSet.questionSetNumber}</span>
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm sm:text-base font-semibold text-[var(--color-text-primary)]">
                  Question Set {questionSet.questionSetNumber}
                </h4>
                <span
                  className="inline-flex items-center gap-1 rounded-full border border-[color-mix(in_srgb,var(--color-primary)_28%,var(--color-border))] bg-[color-mix(in_srgb,var(--color-primary)_10%,var(--color-card))] px-2 py-0.5 text-[10px] sm:text-xs font-semibold text-[var(--color-primary)]"
                  title={`${questionCount} question${questionCount !== 1 ? 's' : ''} in this set`}
                >
                  <FiList size={11} className="opacity-80" />
                  {questionCount} question{questionCount !== 1 ? 's' : ''}
                </span>
              </div>
              <p className="text-xs sm:text-sm text-[var(--color-text-secondary)] mt-0.5">
                {questionSet.total_attempts} attempt{questionSet.total_attempts !== 1 ? 's' : ''}
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
            {/* Schedule Interview Button - Show when no interviews exist */}
            {questionSet.total_attempts === 0 && (
              <button
                onClick={handleScheduleClick}
                disabled={isDisabled || loading}
                className={`px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all duration-200 flex items-center justify-center shadow-md hover:shadow-lg transform hover:scale-105 ${
                  isDisabled
                    ? 'bg-gray-400 cursor-not-allowed opacity-50'
                    : 'bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/90 text-white cursor-pointer'
                }`}
              >
                <FiPlay className="mr-1 sm:mr-2" size={12} />
                <span className="hidden sm:inline">{scheduleButtonLabel}</span>
                <span className="sm:hidden">{loading ? 'Creating...' : 'Schedule'}</span>
              </button>
            )}
            
            {/* Retake Button - Show when completed interviews exist */}
            {hasCompletedInterviews && (
              <button
                onClick={handleRetakeClick}
                disabled={loading || isDisabled}
                className={`px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all duration-200 flex items-center justify-center shadow-md hover:shadow-lg transform hover:scale-105 ${
                  loading || isDisabled ? 'opacity-50 cursor-not-allowed bg-gray-400' : 'bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/90 text-white cursor-pointer'
                }`}
              >
                <FiRefreshCw className={`mr-1 sm:mr-2 ${loading ? 'animate-spin' : ''}`} size={12} />
                <span className="hidden sm:inline">
                  {loading ? 'Creating...' : 'Retake Interview'}
                </span>
                <span className="sm:hidden">
                  {loading ? 'Creating...' : 'Retake'}
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Interview History */}
        {questionSet.interviews.length > 0 ? (
          <div className="space-y-2 sm:space-y-3">
            <h5 className="text-xs sm:text-sm font-medium text-[var(--color-text-primary)] mb-2 sm:mb-3">
              Interview History
            </h5>
            {questionSet.interviews.map((interview) => (
              <div
                key={interview.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-2 sm:p-3 bg-[var(--color-card)] rounded-lg border border-[var(--color-border)] gap-2 sm:gap-0"
              >
                <div className="flex items-center space-x-2 sm:space-x-3">
                  {getStatusIcon(interview.status)}
                  <div>
                    <p className="text-xs sm:text-sm font-medium text-[var(--color-text-primary)]">
                      Attempt {interview.attempt_number}
                    </p>
                    <p className="text-xs text-[var(--color-text-secondary)]">
                      {formatDate(interview.scheduled_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-1 sm:space-x-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    interview.status === 'completed' || interview.status === 'ENDED' ? 'bg-green-100 text-green-800' :
                    interview.status === 'in_progress' ? 'bg-yellow-100 text-yellow-800' :
                    interview.status === 'scheduled' ? 'bg-blue-100 text-blue-800' :
                    interview.status === 'STARTED' ? 'bg-orange-100 text-orange-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {getStatusText(interview.status)}
                  </span>
                  {interview.retake_from && (
                    <span className="text-xs text-[var(--color-text-secondary)] bg-[var(--color-input-bg)] px-2 py-1 rounded">
                      Retake
                    </span>
                  )}
                  {/* Resume Interview Button - Only show for started interviews */}
                  {interview.status === 'STARTED' && (
                    <button
                      onClick={() => window.location.href = `/interview?interview_id=${interview.id}`}
                      disabled={isDisabled}
                      className={`px-2 py-1 rounded text-xs font-medium transition-all duration-200 flex items-center shadow-sm hover:shadow-md transform hover:scale-105 ${
                        isDisabled
                          ? 'bg-gray-400 cursor-not-allowed opacity-50'
                          : 'bg-orange-500 hover:bg-orange-600 text-white cursor-pointer'
                      }`}
                    >
                      <FiPlay className="mr-1" size={10} />
                      <span className="hidden sm:inline">Resume</span>
                      <span className="sm:hidden">Resume</span>
                    </button>
                  )}
                  
                  {/* View Summary Button - Only show for completed interviews */}
                  {(interview.status === 'completed' || interview.status === 'ENDED') && (
                    <button
                      onClick={() => window.location.href = `/interview-feedback?interview_id=${interview.id}`}
                      disabled={isDisabled}
                      className={`px-2 py-1 rounded text-xs font-medium transition-all duration-200 flex items-center shadow-sm hover:shadow-md transform hover:scale-105 ${
                        isDisabled
                          ? 'bg-gray-400 cursor-not-allowed opacity-50'
                          : 'bg-[var(--color-accent)] hover:bg-[var(--color-accent)]/90 text-white cursor-pointer'
                      }`}
                    >
                      <FiPlay className="mr-1" size={10} />
                      <span className="hidden sm:inline">Summary</span>
                      <span className="sm:hidden">View</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-3 sm:py-4">
            <p className="text-xs sm:text-sm text-[var(--color-text-secondary)]">
              No interviews taken yet. Click "Schedule Interview" to start your first attempt.
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3 mt-3 sm:mt-4">
          <button
            onClick={() => window.location.href = `/questions?resume_id=${pairing.resume_id}&jd_id=${pairing.jd_id}&question_set=${questionSet.questionSetNumber}`}
            disabled={isDisabled}
            className={`px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all duration-200 flex items-center justify-center shadow-md hover:shadow-lg transform hover:scale-105 ${
              isDisabled
                ? 'bg-gray-400 cursor-not-allowed opacity-50'
                : 'bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/90 text-white cursor-pointer'
            }`}
          >
            <FiPlay className="mr-1 sm:mr-2" size={12} />
            <span className="hidden sm:inline">View Questions</span>
            <span className="sm:hidden">Questions</span>
          </button>
        </div>
      </div>

      {/* Retake Confirmation Modal — portaled so fixed positioning is not trapped by App route motion wrapper */}
      {retakeModalOpen && typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] p-2 sm:p-4">
          <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg max-w-xs sm:max-w-md w-full max-h-[90vh] overflow-y-auto shadow-xl">
            <div className="p-3 sm:p-4 md:p-6">
              <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 sm:mb-4">
                Retake Interview
              </h3>
              <p className="text-xs sm:text-sm text-[var(--color-text-secondary)] mb-4 sm:mb-6">
                You're about to retake the interview with Question Set {questionSet.questionSetNumber}. 
                This will be attempt #{questionSet.total_attempts + 1} and will cost the same as your original interview.
              </p>
              
              <div className="bg-[var(--color-input-bg)] border border-[var(--color-border)] rounded-lg p-3 sm:p-4 mb-4 sm:mb-6">
                <h4 className="font-medium text-[var(--color-text-primary)] mb-2 text-sm sm:text-base">Previous Attempts:</h4>
                <div className="space-y-2">
                  {questionSet.interviews.map((interview) => (
                    <div key={interview.id} className="flex items-center justify-between text-xs sm:text-sm">
                      <span className="text-[var(--color-text-secondary)]">
                        Attempt {interview.attempt_number}
                      </span>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        interview.status === 'completed' || interview.status === 'ENDED' ? 'bg-green-100 text-green-800' :
                        interview.status === 'in_progress' ? 'bg-yellow-100 text-yellow-800' :
                        interview.status === 'STARTED' ? 'bg-orange-100 text-orange-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {getStatusText(interview.status)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3">
                <button
                  onClick={() => setRetakeModalOpen(false)}
                  className="flex-1 px-3 sm:px-4 py-2 border border-[var(--color-border)] text-[var(--color-text-primary)] rounded-lg hover:bg-[var(--color-input-bg)] transition-colors duration-200 text-sm cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRetakeConfirm}
                  disabled={loading}
                  className={`flex-1 px-3 sm:px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:bg-[var(--color-primary)]/90 transition-colors duration-200 text-sm ${
                    loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                  }`}
                >
                  {loading ? 'Creating...' : 'Confirm Retake'}
                </button>
              </div>
            </div>
          </div>
        </div>,
          document.body
        )}
      <NoticeModal
        isOpen={noticeModal.isOpen}
        onClose={() => setNoticeModal({ isOpen: false, title: '', message: '' })}
        title={noticeModal.title}
        message={noticeModal.message}
        variant="error"
      />
    </>
  );
};

export default InterviewHistoryCard;
