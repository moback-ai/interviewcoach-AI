import React, { useState } from 'react';
import { FiClock, FiCheckCircle, FiXCircle, FiPlay, FiRefreshCw } from 'react-icons/fi';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../supabaseClient';
import { trackEvents } from '../services/mixpanel';

const InterviewHistoryCard = ({ questionSet, pairing, onRetakeRequest, isRegenerating, isAnyRegenerating = false }) => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [retakeModalOpen, setRetakeModalOpen] = useState(false);

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

  const handleRetakeConfirm = async () => {
    try {
      setLoading(true);
      
      // Close modal first
      setRetakeModalOpen(false);
      
      // Get the original interview ID for retake context
      const originalInterviewId = questionSet.interviews[0]?.id;
      if (!originalInterviewId) {
        throw new Error('No original interview found for retake');
      }
      
      // ✅ STEP 1: Create blank interview record first
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('No active session');
      }

      // Create blank interview with PENDING status
      const blankInterviewResponse = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/interviews`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: session.user.id,
          status: 'PENDING',
          scheduled_at: new Date().toISOString()
          // Don't store resume_id, jd_id, question_set, retake_from here yet
        })
      });

      if (!blankInterviewResponse.ok) {
        throw new Error('Failed to create interview record');
      }

      const blankInterviewResult = await blankInterviewResponse.json();
      const blankInterviewId = blankInterviewResult.data.id;

      console.log('✅ Blank interview created:', blankInterviewId);

      // ✅ STEP 2: Create payment with interview_id in metadata
      const response = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/create-payment`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          resume_id: pairing.resume_id,
          jd_id: pairing.jd_id,
          question_set: questionSet.questionSetNumber,
          retake_from: originalInterviewId,
          interview_id: blankInterviewId // ✅ NOW INCLUDED!
        })
      });
      
      if (!response.ok) {
        // ✅ If payment creation fails, delete the blank interview
        await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/interviews/${blankInterviewId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          }
        });
        throw new Error('Failed to create payment');
      }
      
      const result = await response.json();
      console.log('Payment created:', result);
      
      // ✅ STEP 3: Redirect to Dodo payment page
      window.location.href = result.payment_url;
      
    } catch (error) {
      console.error('Error initiating retake:', error);
      alert(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const hasCompletedInterviews = questionSet.interviews.some(interview => 
    interview.status === 'completed' || interview.status === 'ENDED'
  );
  


  return (
    <>
      <div className="bg-[var(--color-input-bg)] rounded-xl border border-[var(--color-border)] p-3 sm:p-4 md:p-6 shadow-md hover:shadow-lg transition-all duration-300">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-3 sm:mb-4 gap-3 sm:gap-0">
          <div className="flex items-center space-x-2 sm:space-x-3">
            <div className="bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] text-white rounded-xl w-8 h-8 sm:w-10 sm:h-10 md:w-12 md:h-12 flex items-center justify-center shadow-lg">
              <span className="text-sm sm:text-base md:text-lg font-bold">{questionSet.questionSetNumber}</span>
            </div>
            <div>
              <h4 className="text-sm sm:text-base font-semibold text-[var(--color-text-primary)]">
                Question Set {questionSet.questionSetNumber}
              </h4>
              <p className="text-xs sm:text-sm text-[var(--color-text-secondary)]">
                {questionSet.total_attempts} attempt{questionSet.total_attempts !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          
          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
            {/* Schedule Interview Button - Show when no interviews exist */}
            {questionSet.total_attempts === 0 && (
              <button
                onClick={async () => {
                  try {
                    // ✅ STEP 1: Create blank interview record first
                    const { data: { session } } = await supabase.auth.getSession();
                    if (!session?.access_token) {
                      throw new Error('No active session');
                    }

                    // Find existing interviews to determine attempt number
                    const existingInterviewsResponse = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/interviews?resume_id=${pairing.resume_id}&jd_id=${pairing.jd_id}&question_set=${questionSet.questionSetNumber}`, {
                      headers: {
                        'Authorization': `Bearer ${session.access_token}`
                      }
                    });

                    const existingInterviewsResult = await existingInterviewsResponse.json();
                    const existingInterviews = existingInterviewsResult.data || [];
                    
                    const nextAttemptNumber = existingInterviews.length > 0 
                      ? Math.max(...existingInterviews.map(i => i.attempt_number || 1)) + 1
                      : 1;

                    // Create blank interview with PENDING status
                    const blankInterviewResponse = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/interviews`, {
                      method: 'POST',
                      headers: {
                        'Authorization': `Bearer ${session.access_token}`,
                        'Content-Type': 'application/json'
                      },
                      body: JSON.stringify({
                        // ✅ Only store what we need to identify the interview
                        user_id: session.user.id, // For security/ownership
                        status: 'PENDING', // Status to track payment state
                        scheduled_at: new Date().toISOString() // Timestamp
                        // ❌ Don't store resume_id, jd_id, question_set, retake_from here
                      })
                    });

                    if (!blankInterviewResponse.ok) {
                      throw new Error('Failed to create interview record');
                    }

                    const blankInterviewResult = await blankInterviewResponse.json();
                    const blankInterviewId = blankInterviewResult.data.id;

                    console.log('✅ Blank interview created:', blankInterviewId);

                    // ✅ STEP 2: Create payment with interview_id in metadata
                    const response = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/create-payment`, {
                      method: 'POST',
                      headers: {
                        'Authorization': `Bearer ${session.access_token}`,
                        'Content-Type': 'application/json'
                      },
                      body: JSON.stringify({
                        resume_id: pairing.resume_id,
                        jd_id: pairing.jd_id,
                        question_set: questionSet.questionSetNumber,
                        interview_id: blankInterviewId // ✅ Pass the blank interview ID
                      })
                    });
                    
                    if (!response.ok) {
                      // ✅ If payment creation fails, delete the blank interview
                      await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/interviews/${blankInterviewId}`, {
                        method: 'DELETE',
                        headers: {
                          'Authorization': `Bearer ${session.access_token}`
                        }
                      });
                      throw new Error('Failed to create payment');
                    }
                    
                    const result = await response.json();
                    console.log('Payment created:', result);
                    
                    // ✅ STEP 3: Redirect to Dodo payment page
                    window.location.href = result.payment_url;
                    
                  } catch (error) {
                    console.error('Error creating payment:', error);
                    alert(`Error: ${error.message}`);
                  }
                }}
                disabled={isDisabled}
                className={`px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all duration-200 flex items-center justify-center shadow-md hover:shadow-lg transform hover:scale-105 ${
                  isDisabled
                    ? 'bg-gray-400 cursor-not-allowed opacity-50'
                    : 'bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/90 text-white cursor-pointer'
                }`}
              >
                <FiPlay className="mr-1 sm:mr-2" size={12} />
                <span className="hidden sm:inline">Schedule Interview</span>
                <span className="sm:hidden">Schedule</span>
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
            {questionSet.interviews.map((interview, index) => (
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

      {/* Retake Confirmation Modal */}
      {retakeModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 sm:p-4">
          <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg max-w-xs sm:max-w-md w-full shadow-xl">
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
        </div>
      )}
    </>
  );
};

export default InterviewHistoryCard;
