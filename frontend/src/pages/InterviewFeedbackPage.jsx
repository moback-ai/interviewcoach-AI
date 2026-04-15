import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  CheckCircle, 
  TrendingUp, 
  Clock, 
  Star,
  ArrowLeft,
  Download,
  Share2,
  BookOpen,
  Target,
  MessageSquare,
  AlertCircle,
  Headphones
} from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import Navbar from '@/components/Navbar';
import { supabase } from '@/supabaseClient';
import { trackEvents } from '../services/mixpanel';

// PDF generation functions
const generateInterviewPDF = (feedbackData, transcriptData, getOverallRating, getRatingLabel, getInterviewDuration, getQuestionsAnswered, formatKeyStrengths, formatImprovementAreas) => {
  // Import jsPDF dynamically to avoid SSR issues
  import('jspdf').then(({ default: jsPDF }) => {
    import('jspdf-autotable').then(({ default: autoTable }) => {
      const doc = new jsPDF();
      
      // Set document properties
      doc.setProperties({
        title: 'Interview Feedback Report',
        subject: 'Comprehensive Interview Analysis',
        author: 'Interview Coach Platform',
        creator: 'Interview Coach Platform'
      });

      // Page dimensions
      const pageWidth = doc.internal.pageSize.width;
      const margin = 20;
      let yPosition = 30;

      // Title
      doc.setFontSize(24);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(44, 62, 80);
      doc.text('Interview Feedback Report', pageWidth / 2, yPosition, { align: 'center' });
      yPosition += 20;

      // Interview Details
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(52, 73, 94);
      doc.text('Interview Details', margin, yPosition);
      yPosition += 15;

      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(44, 62, 80);
      
      const interviewDate = new Date(feedbackData.created_at).toLocaleDateString();
      const interviewTime = new Date(feedbackData.created_at).toLocaleTimeString();
      
      doc.text(`Date: ${interviewDate}`, margin, yPosition);
      yPosition += 8;
      doc.text(`Time: ${interviewTime}`, margin, yPosition);
      yPosition += 8;
      doc.text(`Interview ID: ${feedbackData.interview_id.slice(0, 8)}...`, margin, yPosition);
      yPosition += 15;

      // Overall Performance
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(52, 73, 94);
      doc.text('Overall Performance', margin, yPosition);
      yPosition += 15;

      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(44, 62, 80);
      
      doc.text(`Rating: ${getOverallRating()}/10 (${getRatingLabel()})`, margin, yPosition);
      yPosition += 8;
      doc.text(`Duration: ${getInterviewDuration()}`, margin, yPosition);
      yPosition += 8;
      doc.text(`Responses Given: ${getQuestionsAnswered()}`, margin, yPosition);
      yPosition += 15;

      // Executive Summary
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(52, 73, 94);
      doc.text('Executive Summary', margin, yPosition);
      yPosition += 15;

      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(44, 62, 80);
      
      const summary = feedbackData.summary || 'No summary available';
      const summaryLines = doc.splitTextToSize(summary, pageWidth - 2 * margin);
      summaryLines.forEach((line, index) => {
        if (yPosition > doc.internal.pageSize.height - 30) {
          doc.addPage();
          yPosition = 30;
        }
        doc.text(line, margin, yPosition);
        yPosition += 6;
      });
      yPosition += 10;

      // Key Strengths
      if (feedbackData.key_strengths) {
        doc.setFontSize(16);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(52, 73, 94);
        doc.text('Key Strengths', margin, yPosition);
        yPosition += 15;

        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(44, 62, 80);
        
        const strengths = formatKeyStrengths(feedbackData.key_strengths);
        strengths.forEach((strength, index) => {
          if (yPosition > doc.internal.pageSize.height - 30) {
            doc.addPage();
            yPosition = 30;
          }
          doc.text(`${index + 1}. ${strength}`, margin, yPosition);
          yPosition += 8;
        });
        yPosition += 10;
      }

      // Areas for Improvement
      if (feedbackData.improvement_areas) {
        doc.setFontSize(16);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(52, 73, 94);
        doc.text('Areas for Improvement', margin, yPosition);
        yPosition += 15;

        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(44, 62, 80);
        
        const improvements = formatImprovementAreas(feedbackData.improvement_areas);
        improvements.forEach((improvement, index) => {
          if (yPosition > doc.internal.pageSize.height - 30) {
            doc.addPage();
            yPosition = 30;
          }
          doc.text(`${index + 1}. ${improvement}`, margin, yPosition);
          yPosition += 8;
        });
        yPosition += 10;
      }

      // Full Transcript
      if (transcriptData) {
        doc.addPage();
        yPosition = 30;
        
        doc.setFontSize(16);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(52, 73, 94);
        doc.text('Full Interview Transcript', margin, yPosition);
        yPosition += 15;

        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(44, 62, 80);
        
        const transcript = JSON.parse(transcriptData.full_transcript);
        doc.text(`Total Messages: ${transcript.length}`, margin, yPosition);
        yPosition += 8;
        doc.text(`Interviewer Questions: ${transcript.filter(m => m.role === 'assistant').length}`, margin, yPosition);
        yPosition += 8;
        doc.text(`Candidate Responses: ${transcript.filter(m => m.role === 'user').length}`, margin, yPosition);
        yPosition += 15;

        // Transcript messages
        transcript.forEach((message, index) => {
          if (yPosition > doc.internal.pageSize.height - 30) {
            doc.addPage();
            yPosition = 30;
          }
          
          const role = message.role === 'assistant' ? 'Interviewer' : 'Candidate';
          const roleColor = message.role === 'assistant' ? [52, 152, 219] : [46, 204, 113];
          
          doc.setFontSize(9);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(...roleColor);
          doc.text(`[${index + 1}] ${role}:`, margin, yPosition);
          
          const messageX = margin + 40;
          doc.setFontSize(9);
          doc.setFont('helvetica', 'normal');
          doc.setTextColor(44, 62, 80);
          
          const messageLines = doc.splitTextToSize(message.content, pageWidth - messageX - margin);
          messageLines.forEach((line, lineIndex) => {
            if (yPosition > doc.internal.pageSize.height - 30) {
              doc.addPage();
              yPosition = 30;
            }
            doc.text(line, messageX, yPosition);
            yPosition += 5;
          });
          yPosition += 8;
        });
      }

      // Footer
      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(128, 128, 128);
        doc.text(`Page ${i} of ${totalPages}`, pageWidth / 2, doc.internal.pageSize.height - 10, { align: 'center' });
        doc.text('Interview Coach Platform', pageWidth / 2, doc.internal.pageSize.height - 5, { align: 'center' });
      }

      // Save the PDF
      const fileName = `interview-report-${feedbackData.interview_id.slice(0, 8)}-${new Date().toISOString().split('T')[0]}.pdf`;
      doc.save(fileName);
    });
  });
};

function InterviewFeedbackPage() {
  const { isDark } = useTheme();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const interviewId = searchParams.get('interview_id');
  
  const [showLoading, setShowLoading] = useState(true);
  const [feedbackData, setFeedbackData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  
  // Prevent duplicate "Interview Feedback Accessed" tracking for this page visit
  const hasTrackedFeedbackAccessed = useRef(false);
  
  // Fetch feedback data from the database
  const fetchFeedbackData = async () => {
    if (!interviewId) {
      setError('Interview ID is required');
      setShowLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Get current user session
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
      
      // Fetch feedback data using the interview_id via Supabase Edge Function
      const response = await fetch(`${supabaseUrl}/functions/v1/interview-feedback?interview_id=${interviewId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Failed to fetch feedback: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.success && result.data && result.data.length > 0) {
        // Get the first feedback record for this interview
        setFeedbackData(result.data[0]);
        setShowLoading(false); // Hide loading when data is loaded
        
        // Note: Interview feedback generation is now tracked in InterviewPage.jsx and ChatWindow.jsx
        // when the interview actually ends and feedback is generated, not when feedback is accessed
        
        // Note: Interview completion is now tracked in InterviewPage.jsx and ChatWindow.jsx
        // when the interview actually ends, not when feedback is accessed
      } else {
        setError('No feedback data found for this interview');
        setShowLoading(false);
      }
    } catch (err) {
      console.error('Error fetching feedback data:', err);
      setError(err.message || 'Failed to load interview feedback');
      setShowLoading(false);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Track interview feedback accessed (once per page visit)
    if (!hasTrackedFeedbackAccessed.current) {
      hasTrackedFeedbackAccessed.current = true;
      trackEvents.interviewFeedbackAccessed({
        interview_id: interviewId,
        access_timestamp: new Date().toISOString()
      });
    }
    
    // Start fetching data immediately
    fetchFeedbackData();
  }, [interviewId]);

  const getOverallRating = () => {
    // Extract overall rating from the summary text if available
    if (feedbackData?.summary) {
      // Look for pattern like "Overall Rating: X.X/10" or "(Overall Rating: X.X/10)"
      const ratingMatch = feedbackData.summary.match(/\(?Overall Rating:\s*(\d+\.?\d*)\/10\)?/i);
      if (ratingMatch && ratingMatch[1]) {
        return parseFloat(ratingMatch[1]);
      }
      
      // Alternative pattern: look for "X.X/10" at the end of the summary
      const endRatingMatch = feedbackData.summary.match(/(\d+\.?\d*)\/10\s*\)?\s*$/i);
      if (endRatingMatch && endRatingMatch[1]) {
        return parseFloat(endRatingMatch[1]);
      }
    }
    
    // Fallback to default rating if no rating found in summary
    return 7.5; // Out of 10
  };

  const getRatingColor = (rating) => {
    if (rating >= 8) return 'text-green-500';
    if (rating >= 6) return 'text-yellow-500';
    return 'text-red-500';
  };

  const getRatingLabel = () => {
    // Extract the actual rating label from the summary text (between ** ** markers)
    if (feedbackData?.summary) {
      // Look for patterns like "**weak**", "**strong**", "**average**" in the summary
      const labelMatch = feedbackData.summary.match(/\b(weak|strong|average)\b/i);
      if (labelMatch && labelMatch[1]) {
        return labelMatch[1].charAt(0).toUpperCase() + labelMatch[1].slice(1).toLowerCase();
      }
    }
    
    // Fallback to rating-based labels if no label found in summary
    const rating = getOverallRating();
    if (rating >= 8) return 'Excellent';
    if (rating >= 6) return 'Good';
    if (rating >= 4) return 'Average';
    return 'Needs Improvement';
  };

  const getRatingIconColor = () => {
    // Get the rating label and return appropriate color for the tick mark
    const label = getRatingLabel().toLowerCase();
    
    if (label === 'strong') return 'text-green-500';
    if (label === 'average') return 'text-yellow-500';
    if (label === 'weak') return 'text-red-500';
    
    // Fallback to rating-based colors
    const rating = getOverallRating();
    if (rating >= 8) return 'text-green-500';
    if (rating >= 6) return 'text-yellow-500';
    return 'text-red-500';
  };

  const formatKeyStrengths = (strengthsText) => {
    if (!strengthsText) return [];
    
    // Split by numbered points (1., 2., 3., etc.)
    const points = strengthsText.split(/\d+\.\s*/).filter(point => point.trim());
    
    // Clean up each point and return as array
    return points.map(point => point.trim());
  };

  const formatImprovementAreas = (improvementsText) => {
    if (!improvementsText) return [];
    
    // Split by numbered points (1., 2., 3., etc.)
    const points = improvementsText.split(/\d+\.\s*/).filter(point => point.trim());
    
    // Clean up each point and return as array
    return points.map(point => point.trim());
  };

  const formatSummary = (summaryText) => {
    if (!summaryText) return '';
    
    // Remove the overall rating part since it's displayed elsewhere
    let cleanedSummary = summaryText.replace(/\(?Overall Rating:\s*\d+\.?\d*\/10\)?/gi, '');
    
    // Clean up any extra spaces or punctuation that might be left
    cleanedSummary = cleanedSummary.replace(/\s+/g, ' ').trim();
    
    // Remove trailing punctuation if it ends with a period after cleaning
    cleanedSummary = cleanedSummary.replace(/\.$/, '');
    
    // Replace **word** with <strong>word</strong> for weak, strong, average
    cleanedSummary = cleanedSummary.replace(/\*\*(weak|strong|average)\*\*/gi, '<strong>$1</strong>');
    
    return cleanedSummary;
  };

  const getInterviewDuration = () => {
    if (feedbackData?.interview_duration_minutes) {
      const minutes = feedbackData.interview_duration_minutes;
      if (minutes < 60) {
        return `${minutes} min`;
      } else {
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;
        return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
      }
    }
    return '25 min'; // Fallback
  };

  const getQuestionsAnswered = () => {
    if (feedbackData?.responses_count !== undefined) {
      return feedbackData.responses_count;
    }
    return 12; // Fallback
  };

  const downloadInterviewReport = async () => {
    try {
      setIsLoading(true);
      
      // Fetch transcript data if not already available
      let transcriptData = null;
      if (feedbackData?.interview_id) {
        const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
        const { data: { session } } = await supabase.auth.getSession();
        
        const transcriptResponse = await fetch(`${supabaseUrl}/functions/v1/transcripts?interview_id=${feedbackData.interview_id}`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          }
        });

        if (transcriptResponse.ok) {
          const transcriptResult = await transcriptResponse.json();
          if (transcriptResult.success && transcriptResult.data && transcriptResult.data.length > 0) {
            transcriptData = transcriptResult.data[0];
          }
        }
      }

      // Generate and download PDF
      generateInterviewPDF(
        feedbackData, 
        transcriptData, 
        getOverallRating, 
        getRatingLabel, 
        getInterviewDuration, 
        getQuestionsAnswered, 
        formatKeyStrengths, 
        formatImprovementAreas
      );
      
    } catch (error) {
      console.error('Error downloading interview report:', error);
      alert('Failed to download interview report. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadAudioTranscript = async (audioUrl) => {
    try {
      console.log('🎵 Downloading audio transcript from:', audioUrl);
      
      // Fetch the audio file
      const response = await fetch(audioUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch audio: ${response.status}`);
      }
      
      // Get the audio blob
      const audioBlob = await response.blob();
      
      // Create download link
      const url = window.URL.createObjectURL(audioBlob);
      const link = document.createElement('a');
      link.href = url;
      
      // Set filename with timestamp
      const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
      link.download = `interview_audio_transcript_${timestamp}.wav`;
      
      // Trigger download
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      console.log('✅ Audio transcript downloaded successfully');
      
    } catch (error) {
      console.error('❌ Failed to download audio transcript:', error);
      alert('Failed to download audio transcript. Please try again.');
    }
  };

  // Show loading screen
  if (showLoading) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)] flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-primary)] border-t-transparent mx-auto mb-4"></div>
            <p className="text-[var(--color-text-secondary)] text-lg">Loading your interview feedback...</p>
            <p className="text-[var(--color-text-secondary)] text-sm mt-2 opacity-75">This should only take a moment</p>
          </div>
        </div>
      </>
    );
  }

  // Show error state
  if (error) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)] px-3 sm:px-4 py-6 sm:py-8 md:py-12 lg:py-16">
          <div className="w-full max-w-6xl mx-auto">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center mx-auto mb-4">
                <AlertCircle size={32} className="text-red-500" />
              </div>
              <h1 className="text-2xl font-bold mb-2">Error Loading Feedback</h1>
              <p className="text-[var(--color-text-secondary)] mb-6">{error}</p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <button
                  onClick={() => window.location.reload()}
                  className="px-6 py-3 rounded-lg font-medium transition-all duration-300 shadow-md hover:shadow-lg hover:scale-105 active:scale-95"
                  style={{ 
                    backgroundColor: 'var(--color-primary)',
                    color: 'white'
                  }}
                >
                  Try Again
                </button>
                <button
                  onClick={() => navigate('/dashboard')}
                  className="px-6 py-3 rounded-lg font-medium transition-all duration-300 border hover:scale-105 active:scale-95"
                  style={{ 
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-primary)',
                    backgroundColor: 'var(--color-card)'
                  }}
                >
                  Back to Dashboard
                </button>
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  // Show loading state while fetching data
  if (isLoading || !feedbackData) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)] px-3 sm:px-4 py-6 sm:py-8 md:py-12 lg:py-16">
          <div className="w-full max-w-6xl mx-auto">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-4 border-[var(--color-primary)] border-t-transparent rounded-full mx-auto mb-4"></div>
              <p className="text-[var(--color-text-secondary)]">Loading interview feedback...</p>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      
      <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)] px-3 sm:px-4 py-6 sm:py-8 md:py-12 lg:py-16">
        <div className="w-full max-w-6xl mx-auto">
          {/* Centered Header Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="text-center mb-8 sm:mb-10"
          >
            <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tight text-[var(--color-primary)] mb-3 sm:mb-4">
              Interview Feedback
            </h1>
            <p className="text-sm sm:text-base md:text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto leading-relaxed px-2 mb-6">
              Your comprehensive performance analysis and personalized recommendations
            </p>
            
            {/* Back Button */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.2 }}
              className="flex items-center justify-center gap-4"
            >
              
              {/* Download Section - Seamlessly Integrated */}
              <div className="flex flex-col sm:flex-row gap-3">
                {/* Download Overview Button */}
                <button
                  onClick={downloadInterviewReport}
                  disabled={isLoading}
                  className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-all duration-300 shadow-md hover:shadow-lg hover:scale-105 active:scale-95 flex items-center justify-center gap-2"
                >
                  <Download size={20} />
                  Download Overview
                </button>
                
                {/* Download Audio Transcript Button */}
                {feedbackData?.audio_url && (
                  <button
                    onClick={() => handleDownloadAudioTranscript(feedbackData.audio_url)}
                    className="px-6 py-3 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition-all duration-300 shadow-md hover:shadow-lg hover:scale-105 active:scale-95 flex items-center justify-center gap-2"
                  >
                    <Headphones size={20} />
                    Download Audio Transcript
                  </button>
                )}
              </div>
              
              
            </motion.div>
          </motion.div>

          {/* Content Container */}
          <div className="space-y-8">
            {/* Overall Score Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <div 
                className="rounded-2xl p-6 shadow-lg border"
                style={{ 
                  backgroundColor: 'var(--color-card)',
                  borderColor: 'var(--color-border)' 
                }}
              >
                <div className="flex items-center justify-between mb-6">
                  <h2 
                    className="text-xl font-bold"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    Overall Performance
                  </h2>
                  <div className="flex items-center gap-2">
                    <Star size={20} className="text-yellow-500" />
                    <span 
                      className={`text-2xl font-bold ${getRatingColor(getOverallRating())}`}
                    >
                      {getOverallRating()}/10
                    </span>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="text-center">
                    <div className={`w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center mx-auto mb-3`}>
                      <CheckCircle size={24} className={getRatingIconColor()} />
                    </div>
                    <h3 
                      className="font-semibold mb-1"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {getRatingLabel()}
                    </h3>
                    <p 
                      className="text-sm"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Overall Rating
                    </p>
                  </div>
                  
                  <div className="text-center">
                    <div className="w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center mx-auto mb-3">
                      <Clock size={24} className="text-blue-500" />
                    </div>
                    <h3 
                      className="font-semibold mb-1"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {getInterviewDuration()}
                    </h3>
                    <p 
                      className="text-sm"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Interview Duration
                    </p>
                  </div>
                  
                  <div className="text-center">
                    <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/20 flex items-center justify-center mx-auto mb-3">
                      <MessageSquare size={24} className="text-purple-500" />
                    </div>
                    <h3 
                      className="font-semibold mb-1"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {getQuestionsAnswered()}
                    </h3>
                    <p 
                      className="text-sm"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Responses Given
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Key Strengths */}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.1 }}
              >
                <div 
                  className="rounded-2xl p-6 shadow-lg border h-full"
                  style={{ 
                    backgroundColor: 'var(--color-card)',
                    borderColor: 'var(--color-border)' 
                  }}
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center">
                      <TrendingUp size={20} className="text-green-500" />
                    </div>
                    <h3 
                      className="text-lg font-bold"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      Key Strengths
                    </h3>
                  </div>
                  
                  <div className="space-y-3">
                    {feedbackData.key_strengths ? (
                      formatKeyStrengths(feedbackData.key_strengths).map((strength, index) => (
                        <div key={index} className="flex items-start gap-3">
                          <div className="w-6 h-6 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-xs font-semibold text-green-600 dark:text-green-400">
                              {index + 1}
                            </span>
                          </div>
                          <p 
                            className="text-sm leading-relaxed"
                            style={{ color: 'var(--color-text-primary)' }}
                          >
                            {strength}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p style={{ color: 'var(--color-text-primary)' }}>
                        No key strengths data available.
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>

              {/* Areas for Improvement */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
              >
                <div 
                  className="rounded-2xl p-6 shadow-lg border h-full"
                  style={{ 
                    backgroundColor: 'var(--color-card)',
                    borderColor: 'var(--color-border)' 
                  }}
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-full bg-orange-100 dark:bg-orange-900/20 flex items-center justify-center">
                      <Target size={20} className="text-orange-500" />
                    </div>
                    <h3 
                      className="text-lg font-bold"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      Areas for Improvement
                    </h3>
                  </div>
                  
                  <div className="space-y-3">
                    {feedbackData.improvement_areas ? (
                      formatImprovementAreas(feedbackData.improvement_areas).map((improvement, index) => (
                        <div key={index} className="flex items-start gap-3">
                          <div className="w-6 h-6 rounded-full bg-orange-100 dark:bg-orange-900/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <span className="text-xs font-semibold text-orange-600 dark:text-orange-400">
                              {index + 1}
                            </span>
                          </div>
                          <p 
                            className="text-sm leading-relaxed"
                            style={{ color: 'var(--color-text-primary)' }}
                          >
                            {improvement}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p style={{ color: 'var(--color-text-primary)' }}>
                        No improvement areas data available.
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            </div>

            {/* Summary */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
            >
              <div 
                className="rounded-2xl p-6 shadow-lg border"
                style={{ 
                  backgroundColor: 'var(--color-card)',
                  borderColor: 'var(--color-border)' 
                }}
              >
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center">
                    <BookOpen size={20} className="text-blue-500" />
                  </div>
                  <h3 
                    className="text-lg font-bold"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    Overall Summary
                  </h3>
                </div>
                
                <div className="prose max-w-none">
                  {feedbackData.summary ? (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.5 }}
                      className="p-4 rounded-xl transition-all duration-300 hover:scale-[1.01]"
                      style={{ 
                        backgroundColor: 'var(--color-bg)',
                        border: '1px solid var(--color-border)'
                      }}
                    >
                      <p 
                        className="text-base leading-relaxed text-justify"
                        style={{ color: 'var(--color-text-primary)' }}
                        dangerouslySetInnerHTML={{ __html: formatSummary(feedbackData.summary) }}
                      />
                    </motion.div>
                  ) : (
                    <p style={{ color: 'var(--color-text-primary)' }}>
                      No summary data available.
                    </p>
                  )}
                </div>
                
                {/* Summary footer with quick stats */}
                {feedbackData.summary && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.6 }}
                    className="mt-6 pt-6 border-t"
                    style={{ borderColor: 'var(--color-border)' }}
                  >
                    <div className="flex items-center justify-end">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-green-500"></div>
                        <span 
                          className="text-sm font-medium"
                          style={{ color: 'var(--color-text-secondary)' }}
                        >
                          Comprehensive evaluation
                        </span>
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>
            </motion.div>

            {/* Action Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.4 }}
              className="flex flex-col sm:flex-row gap-4 justify-center"
            >
              <button
                onClick={() => navigate('/interview')}
                className="px-6 py-3 rounded-lg font-medium transition-all duration-300 shadow-md hover:shadow-lg hover:scale-105 active:scale-95"
                style={{ 
                  backgroundColor: 'var(--color-primary)',
                  color: 'white'
                }}
              >
                Practice Another Interview
              </button>
              
              <button
                onClick={() => navigate('/dashboard')}
                className="px-6 py-3 rounded-lg font-medium transition-all duration-300 border hover:scale-105 active:scale-95"
                style={{ 
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)',
                  backgroundColor: 'var(--color-card)'
                }}
              >
                View All Interviews
              </button>
            </motion.div>
          </div>
        </div>
      </div>
    </>
  );
}

export default InterviewFeedbackPage;
