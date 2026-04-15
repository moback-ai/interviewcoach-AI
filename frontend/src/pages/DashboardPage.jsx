import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiFileText, FiBriefcase, FiPlay, FiEye, FiRefreshCw, FiCalendar, FiBarChart2, FiSettings } from 'react-icons/fi';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../hooks/useTheme';
import { useOperation } from '../contexts/OperationContext';
import Navbar from '../components/Navbar';
import InterviewHistoryCard from '../components/InterviewHistoryCard';
import SuccessModal from '../components/SuccessModal';
import { supabase } from '../supabaseClient';
import { apiPost } from '../api';
import { trackEvents } from '../services/mixpanel';
import PerformanceGraph from '../components/PerformanceGraph';
import { motion, AnimatePresence } from 'framer-motion';

function DashboardPage() {
  const { theme } = useTheme();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { setIsOperationInProgress } = useOperation();
  const [loading, setLoading] = useState(true);
  const [selectedPairings, setSelectedPairings] = useState(new Set());
  const [expandedDescriptions, setExpandedDescriptions] = useState(new Set());
  const [resumeJobPairings, setResumeJobPairings] = useState([]);
  const [error, setError] = useState(null);
  const [modalContent, setModalContent] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [regeneratingQuestions, setRegeneratingQuestions] = useState(new Set());
  const [successModal, setSuccessModal] = useState({ isOpen: false, title: '', message: '', details: null });
  const [downloadingResume, setDownloadingResume] = useState(new Set());
  const [downloadSuccess, setDownloadSuccess] = useState(null);
  // ✅ ADD: State for question generation modal
  const [showQuestionModal, setShowQuestionModal] = useState(false);
  const [selectedPairingForRegen, setSelectedPairingForRegen] = useState(null);
  const [easyQuestions, setEasyQuestions] = useState(1);
  const [mediumQuestions, setMediumQuestions] = useState(1);
  const [hardQuestions, setHardQuestions] = useState(1);
  const [codingQuestions, setCodingQuestions] = useState(0);
  const [splitMode, setSplitMode] = useState(false);
  const [blendMode, setBlendMode] = useState(false);
  // ✅ ADD: Split and Blend mode percentage sliders
  const [splitResumePercentage, setSplitResumePercentage] = useState(50);
  const [blendResumePercentage, setBlendResumePercentage] = useState(50);
  const [questionValidationError, setQuestionValidationError] = useState('');
  // Add state for loading overall performance


  useEffect(() => {
    fetchDashboardData();
  }, []);

    // Check if any questions are being regenerated
  const isGeneratingQuestions = regeneratingQuestions.size > 0;

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
      const response = await fetch(`${supabaseUrl}/functions/v1/dashboard`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Failed to fetch dashboard data: ${response.status}`);
      }

      const result = await response.json();
      console.log('Dashboard data:', result);
      setResumeJobPairings(result.data || []);

    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPairing = (pairingId) => {
    console.log('Toggling pairing:', pairingId);
    setSelectedPairings(prev => {
      const newSet = new Set(prev);
      if (newSet.has(pairingId)) {
        newSet.delete(pairingId);
        console.log('Removed pairing:', pairingId, 'New set:', Array.from(newSet));
      } else {
        newSet.add(pairingId);
        console.log('Added pairing:', pairingId, 'New set:', Array.from(newSet));
      }
      return newSet;
    });
  };

  const handleToggleDescription = (pairingId) => {
    setExpandedDescriptions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(pairingId)) {
        newSet.delete(pairingId);
      } else {
        newSet.add(pairingId);
      }
      return newSet;
    });
  };

  const openJobDescriptionModal = (jobTitle, jobDescription) => {
    setModalContent({ title: jobTitle, description: jobDescription });
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setModalContent(null);
  };

  const handleViewQuestions = (questionSetId, pairing) => {
    console.log('View questions for question set:', questionSetId);
    // Navigate to questions page with resume_id and jd_id
    const url = `/questions?resume_id=${pairing.resume_id}&jd_id=${pairing.jd_id}&question_set=${questionSetId.split('-').pop()}`;
    window.location.href = url;
  };

  const handleViewSummary = (questionSetId, pairing) => {
    console.log('View summary for question set:', questionSetId);
    // TODO: Navigate to interview summary page
    alert('Interview summary feature coming soon!');
  };

  const handleRegenerateQuestions = async (pairing) => {
    // ✅ NEW: Open modal with question settings instead of directly generating
    setSelectedPairingForRegen(pairing);
    // Reset question counts and modes
    setEasyQuestions(1);
    setMediumQuestions(1);
    setHardQuestions(1);
    setCodingQuestions(0);
    setSplitMode(false);
    setBlendMode(false);
    setSplitResumePercentage(50);
    setBlendResumePercentage(50);
    setQuestionValidationError('');
    setShowQuestionModal(true);
  };

  // ✅ NEW: Function to actually generate questions after user confirms settings
  const handleConfirmRegenerate = async () => {
    if (!selectedPairingForRegen) return;

    const pairing = selectedPairingForRegen;
    
    // Validate question counts based on mode
    // ✅ CHANGE: Only count easy, medium, hard (exclude coding questions) when both modes are enabled
    const totalQuestions = splitMode && blendMode 
      ? easyQuestions + mediumQuestions + hardQuestions 
      : easyQuestions + mediumQuestions + hardQuestions + codingQuestions;

    // Only validate when both split AND blend modes are enabled
    if (splitMode && blendMode) {
      // Both modes on - need at least 6 total questions (excluding coding)
      if (totalQuestions < 6) {
        // ✅ CHANGE: Use conditional message based on coding slider visibility
        const errorMessage = pairing.technical === true
          ? 'When both Split and Blend modes are enabled, you need at least 6 total questions, excluding coding questions.'
          : 'When both Split and Blend modes are enabled, you need at least 6 total questions.';
        setQuestionValidationError(errorMessage);
        return;
      }
    }

    // Clear any previous validation errors
    setQuestionValidationError('');
    
    // Prevent multiple clicks
    if (regeneratingQuestions.has(pairing.id)) {
      return;
    }

    try {
      // Close modal
      setShowQuestionModal(false);
      
      // Set loading state for this specific pairing
      setRegeneratingQuestions(prev => new Set(prev).add(pairing.id));
      setIsOperationInProgress(true); // ✅ Pause idle timeout during question generation
      
      // Step 3: Generate questions using backend API with question settings
      const questionsResult = await generateQuestionsFromBackend(pairing, {
        easy: easyQuestions,
        medium: mediumQuestions,
        hard: hardQuestions,
        coding: codingQuestions,
        splitMode,
        blendMode,
        splitResumePercentage,
        blendResumePercentage
      });
      
      // ... rest of the existing logic
      if (!questionsResult.success) {
        throw new Error(`Failed to generate questions: ${questionsResult.message}`);
      }

      // Step 4: Save questions to database via edge function
      const questionsSaveResult = await saveQuestionsToDatabase(
        pairing.resume_id, 
        pairing.jd_id, 
        questionsResult.data.questions
      );

      if (!questionsSaveResult.success) {
        throw new Error(`Failed to save questions: ${questionsSaveResult.message}`);
      }

      // Step 5: Track questions regenerated event
      const savedQuestionSet = questionsSaveResult.data[0]?.question_set || 'unknown';
      trackEvents.questionsRegenerated({
        resume_id: pairing.resume_id,
        jd_id: pairing.jd_id,
        question_set: savedQuestionSet,
        regeneration_timestamp: new Date().toISOString(),
        questions_count: questionsResult.data.questions.length
      });

      // Step 6: Show success message and refresh data
      const uniqueQuestions = questionsSaveResult.data.reduce((acc, item) => {
        if (!acc.has(item.question_text)) {
          acc.add(item.question_text);
        }
        return acc;
      }, new Set());
      
      setSuccessModal({
        isOpen: true,
        title: 'Questions Generated Successfully!',
        message: `Question Set ${savedQuestionSet} has been created with ${uniqueQuestions.size} questions.`,
        details: [
          `Question Set: ${savedQuestionSet}`,
          `Total Questions: ${uniqueQuestions.size}`,
          `Resume: ${pairing.resumeName}`,
          `Job Title: ${pairing.jobTitle}`
        ]
      });
      
      // Refresh the dashboard data to show the new question set
      await fetchDashboardData();

    } catch (error) {
      console.error('Error in regenerate questions workflow:', error);
      alert(`Error: ${error.message}`);
    } finally {
      // Clear loading state for this specific pairing
      setRegeneratingQuestions(prev => {
        const newSet = new Set(prev);
        newSet.delete(pairing.id);
        return newSet;
      });
      setIsOperationInProgress(false); // ✅ Resume idle timeout after generation
      setSelectedPairingForRegen(null);
    }
  };

  const handleScheduleInterview = (pairingId) => {
    console.log('Schedule interview for pairing:', pairingId);
    // TODO: Navigate to interview scheduling page
    alert('Interview scheduling feature coming soon!');
  };

  const handleDownloadResume = async (pairing, e) => {
    e.stopPropagation(); // Prevent triggering the pairing selection
    
    // Prevent multiple clicks
    if (downloadingResume.has(pairing.id)) {
      return;
    }
    
    try {
      // Set loading state for this specific pairing
      setDownloadingResume(prev => new Set(prev).add(pairing.id));
      setDownloadSuccess(null);
      
      // Extract file path from the full URL
      // pairing.resumeUrl is like: http://127.0.0.1:54321/storage/v1/object/public/resumes/user_files/filename.pdf
      // We need: user_files/filename.pdf
      const url = new URL(pairing.resumeUrl);
      const pathParts = url.pathname.split('/');
      const bucketIndex = pathParts.findIndex(part => part === 'resumes');
      if (bucketIndex === -1) {
        throw new Error('Invalid resume URL format');
      }
      const filePath = pathParts.slice(bucketIndex + 1).join('/');
      
      console.log('Downloading resume from path:', filePath);
      
      // Direct download from Supabase storage
      const { data, error } = await supabase.storage
        .from('resumes')
        .download(filePath)
      
      if (error) throw error
      
      // Create download link
      const downloadUrl = URL.createObjectURL(data)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = pairing.resumeName || 'resume.pdf'
      document.body.appendChild(a)
      a.click()
      
      // Cleanup
      URL.revokeObjectURL(downloadUrl)
      document.body.removeChild(a)
      
      // Show success feedback
      setDownloadSuccess(pairing.id);
      setTimeout(() => setDownloadSuccess(null), 3000); // Clear after 3 seconds

    } catch (error) {
      console.error('Error downloading resume:', error)
      alert('Failed to download resume. Please try again.')
    } finally {
      // Clear loading state for this specific pairing
      setDownloadingResume(prev => {
        const newSet = new Set(prev);
        newSet.delete(pairing.id);
        return newSet;
      });
    }
  };

  // Retake requests are now handled directly in InterviewHistoryCard
  // This function is kept for future use if needed
  const handleRetakeRequest = (retakeInterview) => {
    console.log('Retake interview created:', retakeInterview);
    // Refresh the dashboard to show the new interview
    fetchDashboardData();
  };

  // Helper function to format file size
  const formatFileSize = (bytes) => {
    if (!bytes) return 'Unknown size';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Helper function to get file extension
  const getFileExtension = (filename) => {
    if (!filename) return 'Unknown';
    return filename.split('.').pop()?.toUpperCase() || 'Unknown';
  };

  // Helper function to call backend API for question generation
  const generateQuestionsFromBackend = async (pairing, questionSettings = {}) => {
    try {
      const response = await apiPost('/api/generate-questions', {
        resume_url: pairing.resumeUrl,
        job_title: pairing.jobTitle,
        job_description: pairing.jobDescription,
        // ✅ FIX: Send question_counts in the correct format that backend expects
        question_counts: {
          beginner: questionSettings.easy || 1,  // ✅ FIX: Use 'beginner' key (not 'easy')
          medium: questionSettings.medium || 1,
          hard: questionSettings.hard || 1,
          coding: questionSettings.coding || 0
        },
        split: questionSettings.splitMode || false,  // ✅ FIX: Use 'split' (not 'split_mode')
        resume_pct: questionSettings.splitResumePercentage || 50,  // ✅ ADD: Missing parameter
        jd_pct: 100 - (questionSettings.splitResumePercentage || 50),  // ✅ ADD: Missing parameter
        blend: questionSettings.blendMode || false,  // ✅ FIX: Use 'blend' (not 'blend_mode')
        blend_pct_resume: questionSettings.blendResumePercentage || 50,  // ✅ ADD: Missing parameter
        blend_pct_jd: 100 - (questionSettings.blendResumePercentage || 50)  // ✅ ADD: Missing parameter
      });

      return response;
    } catch (error) {
      console.error('Error calling backend API:', error);
      throw error;
    }
  };

  // Helper function to save questions to database via edge function
  const saveQuestionsToDatabase = async (resumeId, jdId, questions) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'http://127.0.0.1:54321';
      
      // First, get the current highest question set number for this specific resume_id + jd_id combination
      const getCurrentQuestionSetsResponse = await fetch(`${supabaseUrl}/functions/v1/questions?resume_id=${resumeId}&jd_id=${jdId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!getCurrentQuestionSetsResponse.ok) {
        const errorData = await getCurrentQuestionSetsResponse.json();
        throw new Error(errorData.message || `Failed to get current question sets: ${getCurrentQuestionSetsResponse.status}`);
      }

      const currentQuestionSetsResult = await getCurrentQuestionSetsResponse.json();
      const questionsForThisCombination = currentQuestionSetsResult.data || [];
      
      // Find the highest question set number for this specific resume_id + jd_id combination
      const existingQuestionSets = questionsForThisCombination.map(q => q.question_set).filter(set => set !== null && set !== undefined);
      
      if (existingQuestionSets.length === 0) {
        console.log('[DEBUG] No existing question sets found for this resume_id + jd_id combination, starting with set 1');
        var nextQuestionSet = 1;
      } else {
        const maxSet = Math.max(...existingQuestionSets);
        nextQuestionSet = maxSet + 1;
        console.log('[DEBUG] Found existing sets for this combination, max is', maxSet, 'next will be', nextQuestionSet);
      }
      
      console.log('[DEBUG] Current question sets for resume_id', resumeId, 'and jd_id', jdId, ':', existingQuestionSets);
      console.log('[DEBUG] Next question set will be:', nextQuestionSet);
      console.log('[DEBUG] Total questions found for this combination:', questionsForThisCombination.length);
      console.log('[DEBUG] Questions by set for this combination:', existingQuestionSets.reduce((acc, set) => {
        acc[set] = (acc[set] || 0) + 1;
        return acc;
      }, {}));
      
      // Now save the new questions with the incremented question set number
      const response = await fetch(`${supabaseUrl}/functions/v1/questions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          resume_id: resumeId,
          jd_id: jdId,
          questions: questions,
          question_set: nextQuestionSet
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Failed to save questions: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error saving questions:', error);
      throw error;
    }
  };

  // ✅ ADD: Validation function for question generation
  const canGenerateQuestions = () => {
    // Only validate when both split AND blend modes are enabled
    if (splitMode && blendMode) {
      // ✅ CHANGE: Only count easy, medium, hard (exclude coding questions)
      const totalQuestions = easyQuestions + mediumQuestions + hardQuestions;
      // Both modes on - need at least 6 total questions (excluding coding)
      return totalQuestions >= 6;
    }
    
    // In all other cases, button is enabled
    return true;
  };

  // ✅ ADD: Helper function to get the reason why button is disabled
  const getDisabledReason = () => {
    if (!selectedPairingForRegen) {
      return null;
    }
    
    if (regeneratingQuestions.has(selectedPairingForRegen.id)) {
      return null; // Don't show message during generation
    }
    
    if (splitMode && blendMode) {
      // ✅ CHANGE: Only count easy, medium, hard (exclude coding questions)
      const totalQuestions = easyQuestions + mediumQuestions + hardQuestions;
      if (totalQuestions < 6) {
        // ✅ CHANGE: Show different message based on whether coding slider is visible
        if (selectedPairingForRegen.technical === true) {
          return 'When both Split and Blend modes are enabled, you need at least 6 total questions, excluding coding questions.';
        } else {
          return 'When both Split and Blend modes are enabled, you need at least 6 total questions.';
        }
      }
    }
    
    return null;
  };

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen bg-[var(--color-bg)] pt-20 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-primary)] mx-auto"></div>
            <p className="mt-4 text-[var(--color-text-secondary)]">Loading dashboard...</p>
          </div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen bg-[var(--color-bg)] pt-20 flex items-center justify-center">
          <div className="text-center max-w-md mx-auto px-4">
            <div className="bg-[var(--color-error)]/10 border border-[var(--color-error)] rounded-lg p-6">
              <h3 className="text-lg font-semibold text-[var(--color-error)] mb-2">Error Loading Dashboard</h3>
              <p className="text-[var(--color-text-secondary)] mb-4">{error}</p>
              <button
                onClick={fetchDashboardData}
                className="bg-[var(--color-primary)] text-white px-4 py-2 rounded-lg hover:opacity-90 transition-opacity cursor-pointer"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

    return (
    <>
      <Navbar disableNavigation={isGeneratingQuestions} />
      <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)] px-3 sm:px-4 lg:px-6 py-4 sm:py-6 md:py-8 lg:py-12 flex justify-center">
        <div className="w-full max-w-7xl">
          {/* Header */}
          <div className="text-center mb-6 sm:mb-8 md:mb-10">
            <h1 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl xl:text-5xl font-extrabold tracking-tight text-[var(--color-primary)] mb-2 sm:mb-3 md:mb-4">
              Interview Dashboard
            </h1>
            <p className="text-xs sm:text-sm md:text-base lg:text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto leading-relaxed px-2 mb-3 sm:mb-4">
              Manage your resume and job description pairings
            </p>
          </div>

          {/* Performance Graph - Only shows when user has 2+ completed interviews */}
          {resumeJobPairings.length > 0 && (
            <div className="mb-6 sm:mb-8">
              <PerformanceGraph resumeJobPairings={resumeJobPairings} />
            </div>
          )}

          {/* Upload Button Section - Only show for users with existing data */}
          {resumeJobPairings.length > 0 && (
            <div className="text-center mb-6 sm:mb-8">
                              <button
                  onClick={() => {
                    if (!isGeneratingQuestions) {
                      window.location.href = '/upload';
                    }
                  }}
                  disabled={isGeneratingQuestions}
                  className={`px-4 sm:px-6 md:px-8 py-2 sm:py-3 rounded-lg text-sm sm:text-base font-semibold transition-all duration-200 inline-flex items-center shadow-md hover:shadow-lg transform hover:scale-105 ${
                    isGeneratingQuestions
                      ? 'bg-gray-400 cursor-not-allowed opacity-50'
                      : 'bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/90 text-white cursor-pointer'
                  }`}
                >
                <FiFileText className="mr-2" />
                <span className="hidden sm:inline">Upload Resume & Job Description</span>
                <span className="sm:hidden">Upload</span>
              </button>
            </div>
          )}

          {/* Main Content */}
          <div className="space-y-4 sm:space-y-6 md:space-y-8">
            {resumeJobPairings.length === 0 ? (
              <div className="text-center py-8 sm:py-12">
                <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] p-4 sm:p-6 md:p-8 max-w-sm sm:max-w-md mx-auto">
                  <FiFileText className="mx-auto mb-3 sm:mb-4 text-[var(--color-text-secondary)]" size={32} />
                  <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-2">No Resume-Job Description Pairings Found</h3>
                  <p className="text-xs sm:text-sm text-[var(--color-text-secondary)] mb-4 sm:mb-6">
                    You need to upload a resume and job description, then generate questions to see them here.
                  </p>
                  <button
                    onClick={() => {
                      if (!isGeneratingQuestions) {
                        window.location.href = '/upload';
                      }
                    }}
                    disabled={isGeneratingQuestions}
                    className={`px-4 sm:px-6 py-2 sm:py-3 rounded-lg text-sm sm:text-base font-semibold transition-all duration-200 inline-flex items-center ${
                      isGeneratingQuestions
                        ? 'bg-gray-400 cursor-not-allowed opacity-50'
                        : 'bg-[var(--color-primary)] hover:bg-[var(--color-primary)]/90 text-white cursor-pointer'
                    }`}
                  >
                    <FiFileText className="mr-2" />
                    <span className="hidden sm:inline">Upload Resume & Job Description</span>
                    <span className="sm:hidden">Upload</span>
                  </button>
                </div>
              </div>
            ) : (
              resumeJobPairings.map((pairing) => (
              <div key={pairing.id} className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] shadow-lg hover:shadow-xl transition-all duration-300 overflow-hidden">
                {/* Resume-Job Description Pairing Header - Clickable */}
                <div 
                  className="p-3 sm:p-4 md:p-6 border-b border-[var(--color-border)] cursor-pointer hover:shadow-inner transition-all duration-200"
                  onClick={() => handleSelectPairing(pairing.id)}
                >
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 md:gap-6 items-stretch">
                    {/* Resume */}
                    <div 
                      className={`bg-[var(--color-input-bg)] border border-[var(--color-border)] rounded-lg p-3 sm:p-4 md:p-6 text-center flex flex-col justify-center min-h-[80px] sm:min-h-[100px] md:min-h-[120px] transition-all duration-200 cursor-pointer hover:bg-[var(--color-primary)] hover:text-white group relative ${
                        downloadingResume.has(pairing.id) ? 'opacity-75 cursor-not-allowed' : ''
                      } ${downloadSuccess === pairing.id ? 'ring-2 ring-green-500 ring-opacity-50' : ''}`}
                      onClick={(e) => handleDownloadResume(pairing, e)}
                      onKeyDown={(e) => e.key === 'Enter' && handleDownloadResume(pairing, e)}
                      title="Click to download resume"
                      role="button"
                      tabIndex={0}
                      aria-label={`Download resume file: ${pairing.resumeName}`}
                    >
                      {/* Loading State */}
                      {downloadingResume.has(pairing.id) && (
                        <div className="absolute inset-0 bg-[var(--color-primary)]/20 rounded-lg flex items-center justify-center">
                          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--color-primary)]"></div>
                        </div>
                      )}
                      
                      {/* Success State */}
                      {downloadSuccess === pairing.id && (
                        <div className="absolute top-2 right-2 bg-green-500 text-white rounded-full p-1">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      )}
                      
                      <FiFileText className="mx-auto mb-2 sm:mb-3 text-[var(--color-primary)] group-hover:text-white transition-all duration-200" size={24} />
                      <p className="text-xs sm:text-sm md:text-base font-semibold text-[var(--color-text-primary)] group-hover:text-white transition-all duration-200">
                        {pairing.resumeName}
                      </p>
                      
                      {/* Simple Status Text */}
                      <p className="text-xs text-[var(--color-text-secondary)] group-hover:text-white/80 transition-all duration-200 mt-1">
                        {downloadingResume.has(pairing.id) 
                          ? 'Downloading...' 
                          : downloadSuccess === pairing.id 
                            ? 'Downloaded!' 
                            : 'Click to download'
                        }
                      </p>
                    </div>
                    
                    {/* Job Title and Description Combined */}
                    <div className="bg-[var(--color-input-bg)] border border-[var(--color-border)] rounded-lg p-3 sm:p-4 md:p-6 text-center flex flex-col justify-center min-h-[80px] sm:min-h-[100px] md:min-h-[120px] transition-all duration-300 ease-in-out">
                      <FiBriefcase className="mx-auto mb-2 sm:mb-3 text-[var(--color-primary)] transition-colors duration-200" size={24} />
                      <p className="text-xs sm:text-sm md:text-base font-semibold text-[var(--color-text-primary)] transition-colors duration-200">
                        {pairing.jobTitle}
                      </p>
                      <div className="mt-1 sm:mt-2 text-left">
                        <div className="relative">
                          <p className="text-xs sm:text-sm text-[var(--color-text-secondary)] leading-relaxed line-clamp-2">
                            {pairing.jobDescription}
                          </p>
                          {pairing.jobDescription.length > 120 && (
                            <div className="mt-1 sm:mt-2 flex justify-end">
                              <button 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openJobDescriptionModal(pairing.jobTitle, pairing.jobDescription);
                                }}
                                className="inline-flex items-center gap-1 text-xs font-medium text-[var(--color-primary)] hover:text-[var(--color-primary)]/80 transition-colors duration-200 group"
                              >
                                <span className="hidden sm:inline">View details</span>
                                <span className="sm:hidden">Details</span>
                                <svg 
                                  className="w-3 h-3" 
                                  fill="none" 
                                  stroke="currentColor" 
                                  viewBox="0 0 24 24"
                                >
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* Status Indicator */}
                    <div className="flex items-center justify-center sm:col-span-2 lg:col-span-1">
                      <div className={`flex items-center space-x-1 sm:space-x-2 px-2 sm:px-3 md:px-4 py-1 sm:py-2 rounded-lg transition-all duration-200 ${
                        selectedPairings.has(pairing.id)
                          ? 'bg-[var(--color-primary)] text-white'
                          : 'bg-[var(--color-accent)] text-white'
                      }`}>
                        <div className={`w-1.5 sm:w-2 h-1.5 sm:h-2 rounded-full transition-colors duration-200 ${
                          selectedPairings.has(pairing.id) ? 'bg-white' : 'bg-white'
                        }`}></div>
                        <span className="text-xs sm:text-sm font-medium transition-colors duration-200">
                          {selectedPairings.has(pairing.id) ? 'Selected' : 'Click to select'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                                               {/* Question Sets and Action Buttons - Only show when selected */}
                <div className={`overflow-hidden transition-all duration-500 ease-in-out ${
                  selectedPairings.has(pairing.id) ? 'max-h-[3000px] opacity-100' : 'max-h-0 opacity-0'
                }`}>
                  <div className="p-4 sm:p-6 md:p-8 bg-gradient-to-br from-[var(--color-input-bg)] to-[var(--color-card)]">
                   {/* Question Sets Container */}
                   <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] p-3 sm:p-4 md:p-6 shadow-lg mb-4 sm:mb-6 transition-colors duration-200">
                     <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 sm:mb-6 gap-2 sm:gap-0">
                       <h3 className="text-base sm:text-lg font-bold text-[var(--color-text-primary)] flex items-center">
                         <div className="bg-[var(--color-primary)] text-white rounded-lg p-1.5 sm:p-2 mr-2 sm:mr-3">
                           <FiPlay size={16} />
                         </div>
                         Question Sets
                       </h3>
                       <span className="text-xs sm:text-sm text-[var(--color-text-secondary)] bg-[var(--color-input-bg)] px-2 sm:px-3 py-1 rounded-full border border-[var(--color-border)] self-start sm:self-auto">
                         {pairing.questionSets.length} set{pairing.questionSets.length !== 1 ? 's' : ''}
                       </span>
                     </div>
                     <div className="grid gap-3 sm:gap-4">
                       {pairing.questionSets.map((questionSet) => (
                         <InterviewHistoryCard
                           key={questionSet.id}
                           questionSet={questionSet}
                           pairing={pairing}
                           onRetakeRequest={handleRetakeRequest}
                           isRegenerating={regeneratingQuestions.has(pairing.id)}
                           isAnyRegenerating={isGeneratingQuestions}
                         />
                       ))}
                     </div>
                   </div>

                   {/* Global Action Buttons */}
                   <div className="flex justify-center">
                     <button
                       onClick={() => handleRegenerateQuestions(pairing)}
                       disabled={regeneratingQuestions.has(pairing.id) || isGeneratingQuestions}
                       className={`bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-primary)]/90 hover:from-[var(--color-primary)]/90 hover:to-[var(--color-primary)] text-white py-2 sm:py-3 md:py-4 px-4 sm:px-6 md:px-8 rounded-lg sm:rounded-xl font-semibold transition-all duration-200 shadow-lg hover:shadow-xl transform hover:scale-[1.02] flex items-center justify-center text-sm sm:text-base ${
                         (regeneratingQuestions.has(pairing.id) || isGeneratingQuestions) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                       }`}
                     >
                       <FiRefreshCw className={`mr-2 sm:mr-3 ${regeneratingQuestions.has(pairing.id) ? 'animate-spin' : ''}`} size={18} />
                       <span className="hidden sm:inline">
                         {regeneratingQuestions.has(pairing.id) ? 'Regenerating...' : isGeneratingQuestions ? 'Generation in Progress...' : 'Regenerate Questions'}
                       </span>
                       <span className="sm:hidden">
                         {regeneratingQuestions.has(pairing.id) ? 'Regenerating...' : isGeneratingQuestions ? 'In Progress...' : 'Regenerate'}
                       </span>
                     </button>
                   </div>
                  </div>
                </div>
              </div>
            ))
            )}
          </div>
        </div>
      </div>

      {/* Job Description Modal */}
      {isModalOpen && modalContent && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 sm:p-4">
          <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg max-w-xs sm:max-w-md md:max-w-2xl w-full max-h-[90vh] sm:max-h-[80vh] overflow-hidden shadow-xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-3 sm:p-4 md:p-6 border-b border-[var(--color-border)]">
              <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)]">
                {modalContent.title}
              </h3>
              <button
                onClick={closeModal}
                className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors duration-200 p-1 cursor-pointer"
              >
                <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {/* Modal Content */}
            <div className="p-3 sm:p-4 md:p-6 overflow-y-auto max-h-[calc(90vh-120px)] sm:max-h-[calc(80vh-120px)]">
              <div className="prose prose-sm max-w-none">
                <p className="text-xs sm:text-sm text-[var(--color-text-secondary)] leading-relaxed whitespace-pre-wrap">
                  {modalContent.description}
                </p>
              </div>
            </div>
            
            {/* Modal Footer */}
            <div className="flex justify-end p-3 sm:p-4 md:p-6 border-t border-[var(--color-border)]">
              <button
                onClick={closeModal}
                className="px-3 sm:px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:opacity-90 transition-opacity duration-200 text-sm sm:text-base cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ✅ NEW: Question Generation Settings Modal */}
      {showQuestionModal && selectedPairingForRegen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-[var(--color-card)] rounded-2xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-[var(--color-border)] shadow-2xl"
          >
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <FiSettings className="w-5 h-5" style={{ color: 'var(--color-primary)' }} />
                <h2 className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  Question Generation Settings
                </h2>
              </div>
              <button
                onClick={() => {
                  setShowQuestionModal(false);
                  setSelectedPairingForRegen(null);
                }}
                className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors p-1 rounded-lg hover:bg-[var(--color-hover)]"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-6">
              {/* Question Difficulty Distribution */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Question Difficulty Distribution
                  </h3>
                  <span className="text-sm font-medium px-3 py-1 rounded-full bg-[var(--color-primary)]/10 text-[var(--color-primary)]">
                    Total: {easyQuestions + mediumQuestions + hardQuestions + codingQuestions} questions
                  </span>
                </div>

                {/* ✅ CHANGE: Use grid layout instead of space-y-4 for horizontal display */}
                <div className={`grid ${selectedPairingForRegen.technical === true ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4' : 'grid-cols-1 md:grid-cols-3'} gap-4`}>
                  {/* Easy Questions */}
                  <div className="bg-green-50/50 dark:bg-green-900/10 border border-green-200/50 dark:border-green-800/30 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium text-green-700 dark:text-green-300">
                        Easy Questions
                      </label>
                      <span className="text-xs text-green-600 dark:text-green-400 bg-green-100/70 dark:bg-green-800/30 px-2 py-1 rounded-full">
                        {easyQuestions}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={easyQuestions}
                      onChange={(e) => setEasyQuestions(parseInt(e.target.value))}
                      className="w-full h-2 bg-green-200/50 dark:bg-green-700/30 rounded-lg appearance-none cursor-pointer slider-green"
                    />
                    <div className="flex justify-between text-xs text-green-600/70 dark:text-green-400/70 mt-1">
                      <span>1</span>
                      <span>5</span>
                    </div>
                  </div>

                  {/* Medium Questions */}
                  <div className="bg-yellow-50/50 dark:bg-yellow-900/10 border border-yellow-200/50 dark:border-yellow-800/30 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium text-yellow-700 dark:text-yellow-300">
                        Medium Questions
                      </label>
                      <span className="text-xs text-yellow-600 dark:text-yellow-400 bg-yellow-100/70 dark:bg-yellow-800/30 px-2 py-1 rounded-full">
                        {mediumQuestions}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={mediumQuestions}
                      onChange={(e) => setMediumQuestions(parseInt(e.target.value))}
                      className="w-full h-2 bg-yellow-200/50 dark:bg-yellow-700/30 rounded-lg appearance-none cursor-pointer slider-yellow"
                    />
                    <div className="flex justify-between text-xs text-yellow-600/70 dark:text-yellow-400/70 mt-1">
                      <span>1</span>
                      <span>5</span>
                    </div>
                  </div>

                  {/* Hard Questions */}
                  <div className="bg-red-50/50 dark:bg-red-900/10 border border-red-200/50 dark:border-red-800/30 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium text-red-700 dark:text-red-300">
                        Hard Questions
                      </label>
                      <span className="text-xs text-red-600 dark:text-red-400 bg-red-100/70 dark:bg-red-800/30 px-2 py-1 rounded-full">
                        {hardQuestions}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={hardQuestions}
                      onChange={(e) => setHardQuestions(parseInt(e.target.value))}
                      className="w-full h-2 bg-red-200/50 dark:bg-red-700/30 rounded-lg appearance-none cursor-pointer slider-red"
                    />
                    <div className="flex justify-between text-xs text-red-600/70 dark:text-red-400/70 mt-1">
                      <span>1</span>
                      <span>5</span>
                    </div>
                  </div>

                  {/* Coding Questions Slider - Only show if technical === true */}
                  {selectedPairingForRegen.technical === true && (
                    <div className="bg-blue-50/50 dark:bg-blue-900/10 border border-blue-200/50 dark:border-blue-800/30 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm font-medium text-blue-700 dark:text-blue-300">
                          Coding Questions
                        </label>
                        <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-100/70 dark:bg-blue-800/30 px-2 py-1 rounded-full">
                          {codingQuestions}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="5"
                        value={codingQuestions}
                        onChange={(e) => setCodingQuestions(parseInt(e.target.value))}
                        className="w-full h-2 bg-blue-200/50 dark:bg-blue-700/30 rounded-lg appearance-none cursor-pointer slider-blue"
                      />
                      <div className="flex justify-between text-xs text-blue-600/70 dark:text-blue-400/70 mt-1">
                        <span>0</span>
                        <span>5</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Validation Error Message */}
                {!canGenerateQuestions() && splitMode && blendMode && (
                  <div className="mt-4 p-3 bg-red-50/50 dark:bg-red-900/10 border border-red-200/50 dark:border-red-800/30 rounded-lg">
                    <p className="text-sm text-red-700 dark:text-red-300">
                      {/* ✅ CHANGE: Conditional message based on coding slider visibility */}
                      {selectedPairingForRegen.technical === true
                        ? 'When both Split and Blend modes are enabled, you need at least 6 total questions, excluding coding questions.'
                        : 'When both Split and Blend modes are enabled, you need at least 6 total questions.'}
                    </p>
                  </div>
                )}

                {/* Mode-specific validation hints */}
                {splitMode && blendMode && (
                  <div className="mt-4 p-3 bg-blue-50/50 dark:bg-blue-900/10 border border-blue-200/50 dark:border-blue-800/30 rounded-lg">
                    <p className="text-sm text-blue-700 dark:text-blue-300">
                      💡 <strong>Hybrid Mode:</strong> With both modes enabled, you need at least 6 total questions to ensure a good mix of split and blended questions.
                    </p>
                  </div>
                )}
              </div>

              {/* Mode Toggles */}
              <div className="space-y-4">
                {/* Split Mode Toggle with Slider */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <label className="text-sm font-medium text-[var(--color-text-primary)]">
                        Split Mode
                      </label>
                      <p className="text-xs text-[var(--color-text-secondary)]">
                        Generate separate questions from resume vs job description
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSplitMode(!splitMode)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        splitMode ? 'bg-[var(--color-primary)]' : 'bg-gray-200 dark:bg-gray-700'
                      } cursor-pointer`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          splitMode ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* Split Mode Slider - Directly below Split Mode toggle */}
                  <AnimatePresence>
                    {splitMode && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.3 }}
                        className="mt-3"
                      >
                        <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                          <h4 className="text-sm font-medium text-yellow-800 dark:text-yellow-200 mb-3">
                            Split Mode Settings
                          </h4>
                          <div className="space-y-3">
                            <div className="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
                              <span>Resume</span>
                              <span>Job Description</span>
                            </div>
                            <input
                              type="range"
                              min="0"
                              max="100"
                              value={splitResumePercentage}
                              onChange={(e) => setSplitResumePercentage(parseInt(e.target.value))}
                              className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer slider"
                            />
                            <div className="flex justify-between text-sm font-medium text-[var(--color-text-primary)]">
                              <span>{splitResumePercentage}%</span>
                              <span>{100 - splitResumePercentage}%</span>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Blend Mode Toggle with Slider */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <label className="text-sm font-medium text-[var(--color-text-primary)]">
                        Blend Mode
                      </label>
                      <p className="text-xs text-[var(--color-text-secondary)]">
                        Generate questions that blend resume and job description content
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setBlendMode(!blendMode)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        blendMode ? 'bg-[var(--color-primary)]' : 'bg-gray-200 dark:bg-gray-700'
                      } cursor-pointer`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          blendMode ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* Blend Mode Slider - Directly below Blend Mode toggle */}
                  <AnimatePresence>
                    {blendMode && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.3 }}
                        className="mt-3"
                      >
                        <div className="p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                          <h4 className="text-sm font-medium text-purple-800 dark:text-purple-200 mb-3">
                            Blend Mode Settings
                          </h4>
                          <div className="space-y-3">
                            <div className="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
                              <span>Resume Weight</span>
                              <span>Job Description Weight</span>
                            </div>
                            <input
                              type="range"
                              min="0"
                              max="100"
                              value={blendResumePercentage}
                              onChange={(e) => setBlendResumePercentage(parseInt(e.target.value))}
                              className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer slider"
                            />
                            <div className="flex justify-between text-sm font-medium text-[var(--color-text-primary)]">
                              <span>{blendResumePercentage}%</span>
                              <span>{100 - blendResumePercentage}%</span>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowQuestionModal(false);
                  setSelectedPairingForRegen(null);
                }}
                className="flex-1 py-3 px-4 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-hover)] transition-colors font-semibold"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmRegenerate}
                disabled={!canGenerateQuestions() || regeneratingQuestions.has(selectedPairingForRegen.id)}
                title={!canGenerateQuestions() && !regeneratingQuestions.has(selectedPairingForRegen.id) ? getDisabledReason() : ''}  // ✅ ADD: Show tooltip when disabled
                className="flex-1 py-3 px-4 rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-semibold"
              >
                {regeneratingQuestions.has(selectedPairingForRegen.id) ? 'Generating...' : 'Generate Questions'}
              </button>
            </div>
          </motion.div>
        </div>
      )}


      {/* Success Modal */}
      <SuccessModal
        isOpen={successModal.isOpen}
        onClose={() => setSuccessModal({ isOpen: false, title: '', message: '', details: null })}
        title={successModal.title}
        message={successModal.message}
        details={successModal.details}
      />
    </>
  );
}

export default DashboardPage;
