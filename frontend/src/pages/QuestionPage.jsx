import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { FiSearch, FiFilter, FiCode, FiFileText, FiCopy, FiCreditCard, FiLoader, FiRefreshCw, FiEye, FiSettings, FiPlay, FiDownload, FiMessageSquare, FiAlertCircle } from 'react-icons/fi';
import { Sparkles } from 'lucide-react';
import Navbar from '../components/Navbar';
import PageWavesShell from '../components/common/PageWavesShell';
import LazySyntaxHighlightedCode from '../components/common/LazySyntaxHighlightedCode';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import { trackEvents } from '../services/mixpanel';
import { getSession } from '../lib/authClient';
import { isAuthErrorMessage, redirectToExpiredLogin } from '../utils/authInterceptor';
import { getBackendOrigin } from '../utils/apiConfig';
import NoticeModal from '../components/common/NoticeModal';
import { fetchInterviewQuota, scheduleInterview } from '../utils/scheduleInterview';
import { unlockBodyScroll } from '../utils/unlockBodyScroll';
import generateQuestionsPDF from '../utils/generateQuestionsPDF';


const getLevelColor = (level) => {
  switch (level) {
    case 'easy':
      return 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800';
    case 'medium':
      return 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800';
    case 'hard':
      return 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200 dark:bg-gray-900/20 dark:text-gray-400 dark:border-gray-800';
  }
};

const normalizeLevel = (level) => {
  const normalized = String(level || '').trim().toLowerCase();
  if (['beginner', 'easy', 'basic', 'junior', 'novice', 'simple'].includes(normalized)) return 'easy';
  if (['intermediate', 'medium', 'mid', 'moderate', 'coding'].includes(normalized)) return 'medium';
  if (['expert', 'hard', 'advanced', 'senior', 'difficult', 'complex'].includes(normalized)) return 'hard';
  return normalized || 'medium';
};

const DIFFICULTY_ORDER = { easy: 1, medium: 2, hard: 3 };
const GENERATE_ANSWERS_TIMEOUT_MS = 300000;
const formatLabel = (value) => String(value || '').charAt(0).toUpperCase() + String(value || '').slice(1);

const hasSampleAnswer = (answer) => {
  const text = String(answer || '').trim();
  return Boolean(text) && text !== 'No answer provided';
};

const questionCardVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: (index) => ({
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.22,
      delay: Math.min(index * 0.03, 0.18),
      ease: [0.16, 1, 0.3, 1],
    },
  }),
};

const answerCardVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: (index) => ({
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.18,
      delay: Math.min(index * 0.04, 0.2),
      ease: [0.16, 1, 0.3, 1],
    },
  }),
};



// ... existing mock data and helper functions ...

// Helper function to detect if a line looks like code
const isCodeLine = (line) => {
  const trimmed = line.trim();
  if (!trimmed) return false;
  
  // Common code patterns
  const codePatterns = [
    /^(def|class|import|from|if|elif|else|for|while|try|except|with|async|await|return|yield|break|continue|pass|raise|assert|del|global|nonlocal)\s/, // Python keywords
    /^(function|const|let|var|class|import|export|if|else|for|while|try|catch|async|await|return|yield|break|continue|throw|switch|case|default)\s/, // JavaScript/TypeScript
    /^(public|private|protected|static|final|abstract|class|interface|extends|implements|import|package|if|else|for|while|try|catch|return|throw|switch|case|default)\s/, // Java
    /^[a-zA-Z_][a-zA-Z0-9_]*\s*[=:]\s*/, // Variable assignment
    /^\s*[{}[\]();]/, // Code brackets/punctuation at start
    /^\s*\/\/|\/\*|\*\/|#/, // Comments
    /^\s*\d+\s*[=:]/, // Number followed by assignment
  ];
  
  return codePatterns.some(pattern => pattern.test(trimmed));
};

// Helper function to detect language from code content
const detectLanguage = (code) => {
  const codeLower = code.toLowerCase();
  
  if (codeLower.includes('def ') || codeLower.includes('import ') || codeLower.includes('from ') || codeLower.includes('print(')) {
    return 'python';
  }
  if (codeLower.includes('function ') || codeLower.includes('const ') || codeLower.includes('let ') || codeLower.includes('=>')) {
    return 'javascript';
  }
  if (codeLower.includes('public class') || codeLower.includes('System.out') || codeLower.includes('@Override')) {
    return 'java';
  }
  if (codeLower.includes('SELECT ') || codeLower.includes('FROM ') || codeLower.includes('WHERE ')) {
    return 'sql';
  }
  if (codeLower.includes('#include') || codeLower.includes('std::')) {
    return 'cpp';
  }
  
  return 'python'; // Default to Python
};

/** Render light markdown inline: **bold**, *italic*, `code` — no extra dependency. */
const renderInlineMarkdown = (text) => {
  if (text == null || text === '') return null;
  const nodes = [];
  // Order: code fences first, then bold, then italic
  const tokenRe = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = tokenRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('`') && token.endsWith('`')) {
      nodes.push(
        <code
          key={`md-${key++}`}
          className="px-1 py-0.5 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[0.9em] font-mono"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('**') && token.endsWith('**')) {
      nodes.push(
        <strong key={`md-${key++}`} className="font-semibold text-[var(--color-text-primary)]">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      nodes.push(
        <em key={`md-${key++}`} className="italic">
          {token.slice(1, -1)}
        </em>
      );
    } else {
      nodes.push(token);
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length ? nodes : text;
};

const AnswerContent = ({ answer }) => {
  if (!answer) return null;
  
  // First, try to split by markdown code blocks (```lang optional)
  const markdownParts = answer.split(/(```[\w]*\r?\n[\s\S]*?```)/);
  
  // If we found markdown blocks, use them
  if (markdownParts.length > 1) {
    return (
      <div className="space-y-4">
        {markdownParts.map((part, index) => {
          if (part.startsWith('```')) {
            // Extract the language and code from the markdown code block
            const codeMatch = part.match(/```(\w*)\r?\n([\s\S]*?)```/);
            if (codeMatch) {
              const language = codeMatch[1] || 'text';
              const code = codeMatch[2].trim();
              return <LazySyntaxHighlightedCode key={index} code={code} language={language} />;
            }
            return null;
          } else {
            // Process text parts - check if they contain code patterns
            return processTextWithCode(part, index);
          }
        })}
      </div>
    );
  }
  
  // No markdown blocks found - try to detect code in plain text
  return processTextWithCode(answer, 0);
};

// Function to process text and detect code blocks
const processTextWithCode = (text, baseIndex) => {
  if (!text.trim()) return null;
  
  const lines = text.split('\n');
  const result = [];
  let currentText = [];
  let currentCode = [];
  let inCodeBlock = false;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    const isCode = isCodeLine(line);
    const isIndented = line.match(/^\s{2,}/); // At least 2 spaces of indentation
    const isEmpty = trimmed === '';
    
    // Check if we're starting a code block
    if (!inCodeBlock && isCode) {
      // Save any accumulated text
      if (currentText.length > 0) {
        result.push({
          type: 'text',
          content: currentText.join('\n')
        });
        currentText = [];
      }
      inCodeBlock = true;
      currentCode = [line];
    } 
    // Continue code block
    else if (inCodeBlock) {
      // Continue code block if:
      // 1. Line looks like code
      // 2. Line is empty (blank lines are common in code)
      // 3. Line is indented (indentation suggests continuation of code)
      // 4. Line has code-like characters (brackets, operators, etc.)
      const hasCodeChars = /[{}[\]();=<>!&|+\-*/%]/.test(trimmed);
      
      if (isCode || isEmpty || isIndented || (hasCodeChars && currentCode.length > 0)) {
        currentCode.push(line);
      } else {
        // Check if next few lines are also non-code to confirm end of code block
        let nonCodeCount = 0;
        for (let j = i; j < Math.min(i + 3, lines.length); j++) {
          if (!isCodeLine(lines[j]) && lines[j].trim() && !lines[j].match(/^\s{2,}/)) {
            nonCodeCount++;
          }
        }
        
        // If we have clear non-code text ahead, end the code block
        if (nonCodeCount >= 1) {
          // End of code block - save it
          if (currentCode.length > 0) {
            const codeContent = currentCode.join('\n').trim();
            if (codeContent.length > 0) {
              result.push({
                type: 'code',
                content: codeContent
              });
            }
            currentCode = [];
          }
          inCodeBlock = false;
          currentText.push(line);
        } else {
          // Still might be code, continue
          currentCode.push(line);
        }
      }
    } 
    // Regular text
    else {
      currentText.push(line);
    }
  }
  
  // Handle remaining content
  if (inCodeBlock && currentCode.length > 0) {
    const codeContent = currentCode.join('\n').trim();
    if (codeContent.length > 0) {
      result.push({
        type: 'code',
        content: codeContent
      });
    }
  }
  
  if (currentText.length > 0) {
    result.push({
      type: 'text',
      content: currentText.join('\n')
    });
  }
  
  // If no code blocks detected, return as plain text
  if (result.length === 0 || (result.length === 1 && result[0].type === 'text')) {
    return (
      <div className="space-y-4">
        {result.length > 0 ? (
          <div className="text-[var(--color-text-primary)] leading-relaxed">
            {result[0].content.split('\n').map((line, lineIndex) => (
              <p key={lineIndex} className="mb-2 text-sm sm:text-base">
                {line ? renderInlineMarkdown(line) : '\u00A0'}
              </p>
            ))}
          </div>
        ) : (
          <div className="text-[var(--color-text-primary)] leading-relaxed">
            {text.split('\n').map((line, lineIndex) => (
              <p key={lineIndex} className="mb-2 text-sm sm:text-base">
                {line ? renderInlineMarkdown(line) : '\u00A0'}
              </p>
            ))}
          </div>
        )}
      </div>
    );
  }
  
  // Render mixed content
  return (
    <div className="space-y-4">
      {result.map((item, index) => {
        if (item.type === 'code') {
          const language = detectLanguage(item.content);
          return <LazySyntaxHighlightedCode key={`code-${baseIndex}-${index}`} code={item.content} language={language} />;
        } else {
          return (
            <div key={`text-${baseIndex}-${index}`} className="text-[var(--color-text-primary)] leading-relaxed">
              {item.content.split('\n').map((line, lineIndex) => (
                <p key={lineIndex} className="mb-2 text-sm sm:text-base">
                  {line ? renderInlineMarkdown(line) : '\u00A0'}
                </p>
              ))}
            </div>
          );
        }
      })}
    </div>
  );
};

export default function QuestionsPage() {
  const [searchParams] = useSearchParams(); // ✅ Add this
  const [expandedQuestions, setExpandedQuestions] = useState(new Set());
  const [filterLevel, setFilterLevel] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [isPaymentLoading, setIsPaymentLoading] = useState(false);
  // Database state
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentQuestionSet, setCurrentQuestionSet] = useState(null);
  const [availableQuestionSets, setAvailableQuestionSets] = useState([]);
  const [currentResumeId, setCurrentResumeId] = useState(null);
  const [currentJdId, setCurrentJdId] = useState(null);
  const [interviewHistory, setInterviewHistory] = useState([]);
  const [hasExistingInterviews, setHasExistingInterviews] = useState(false);
  const [interviewQuota, setInterviewQuota] = useState(null);
  const [noticeModal, setNoticeModal] = useState({ isOpen: false, title: '', message: '', variant: 'error' });
  const [isGeneratingAnswers, setIsGeneratingAnswers] = useState(false);
  const [pairingContext, setPairingContext] = useState(null);
  const [showQuestionModal, setShowQuestionModal] = useState(false);
  const [easyQuestions, setEasyQuestions] = useState(1);
  const [mediumQuestions, setMediumQuestions] = useState(1);
  const [hardQuestions, setHardQuestions] = useState(1);
  const [codingQuestions, setCodingQuestions] = useState(0);
  const [splitMode, setSplitMode] = useState(false);
  const [blendMode, setBlendMode] = useState(false);
  const [splitResumePercentage, setSplitResumePercentage] = useState(50);
  const [blendResumePercentage, setBlendResumePercentage] = useState(50);
  const [questionValidationError, setQuestionValidationError] = useState('');
  const [isRegeneratingQuestions, setIsRegeneratingQuestions] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  
  // Prevent duplicate event tracking
  const hasTrackedQuestionsAccessed = useRef(false);

  useEffect(() => {
    unlockBodyScroll();
  }, []);

  // ✅ Updated useEffect - now filters by resume_id + jd_id combination
  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        setLoading(true);
        setError(null);

        // ✅ Get resume_id and jd_id from URL params
        const resumeIdFromUrl = searchParams.get('resume_id');
        const jdIdFromUrl = searchParams.get('jd_id');
        const questionSetFromUrl = searchParams.get('question_set'); // ✅ Get question_set from URL

        if (resumeIdFromUrl && jdIdFromUrl) {
          console.log('✅ Got resume_id and jd_id from URL:', { resumeIdFromUrl, jdIdFromUrl, questionSetFromUrl });
          setCurrentResumeId(resumeIdFromUrl);
          setCurrentJdId(jdIdFromUrl);
        } else {
          console.log('⚠️ No resume_id/jd_id in URL - this might be a direct visit to questions page');
          setError('Please upload a resume and job description first');
          return;
        }

        const session = await getSession();
        if (!session) {
          throw new Error('No active session');
        }

        const backendOrigin = getBackendOrigin();
        
        // First, get all available question sets for this specific resume_id + jd_id combination
        const questionSetsResponse = await fetch(`${backendOrigin}/functions/v1/questions?resume_id=${resumeIdFromUrl}&jd_id=${jdIdFromUrl}`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!questionSetsResponse.ok) {
          const errorData = await questionSetsResponse.json();
          throw new Error(errorData.message || `Failed to fetch question sets: ${questionSetsResponse.status}`);
        }

        const questionSetsResult = await questionSetsResponse.json();
        const questionsForThisCombination = questionSetsResult.data || [];
        
        // Extract unique question sets for this combination and sort them
        const questionSets = [...new Set(questionsForThisCombination.map(q => q.question_set))].sort((a, b) => b - a);
        setAvailableQuestionSets(questionSets);
        
        console.log('[DEBUG] Available question sets for this combination:', questionSets);
        
        // ✅ Use the question_set from URL if available, otherwise fall back to most recent
        let targetQuestionSet = null;
        if (questionSetFromUrl) {
          targetQuestionSet = parseInt(questionSetFromUrl);
          console.log('[DEBUG] Using question_set from URL:', targetQuestionSet);
        } else {
          targetQuestionSet = questionSets.length > 0 ? questionSets[0] : null;
          console.log('[DEBUG] No question_set in URL, using most recent:', targetQuestionSet);
        }
        
        setCurrentQuestionSet(targetQuestionSet);
        
        if (targetQuestionSet) {
          // Fetch questions from the specific question set for this combination
          const questionsResponse = await fetch(`${backendOrigin}/functions/v1/questions?resume_id=${resumeIdFromUrl}&jd_id=${jdIdFromUrl}&question_set=${targetQuestionSet}`, {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${session.access_token}`,
              'Content-Type': 'application/json'
            }
          });

          if (!questionsResponse.ok) {
            const errorData = await questionsResponse.json();
            throw new Error(errorData.message || `Failed to fetch questions: ${questionsResponse.status}`);
          }

          const result = await questionsResponse.json();
          console.log('[DEBUG] Fetched questions from set', targetQuestionSet, 'for combination:', result);
          setQuestions(result.data || []);
          
          // Track questions accessed (only once)
          if (!hasTrackedQuestionsAccessed.current) {
            hasTrackedQuestionsAccessed.current = true;
            trackEvents.questionsAccessed({
              resume_id: resumeIdFromUrl,
              jd_id: jdIdFromUrl,
              question_set: targetQuestionSet,
              total_questions: result.data?.length || 0,
              access_timestamp: new Date().toISOString()
            });
          }
        } else {
          setQuestions([]);
        }

        // ✅ Fetch interview history for this question set
        if (targetQuestionSet) {
          await fetchInterviewHistory(resumeIdFromUrl, jdIdFromUrl, targetQuestionSet, session.access_token);
        }

      } catch (error) {
        console.error('Error fetching questions:', error);
        if (isAuthErrorMessage(error.message)) {
          redirectToExpiredLogin();
          return;
        }
        setError(error.message);
      } finally {
        setLoading(false);
      }
    };

    fetchQuestions();
  }, [searchParams]); // ✅ Add searchParams as dependency

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

  // ✅ New function to fetch interview history for the current question set
  const fetchInterviewHistory = async (resumeId, jdId, questionSet, accessToken) => {
    try {
      const backendOrigin = getBackendOrigin();
      
      // Fetch interview history for this specific question set
      const response = await fetch(`${backendOrigin}/functions/v1/dashboard`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        console.warn('Failed to fetch interview history, continuing without it');
        return;
      }

      const result = await response.json();
      const pairings = result.data || [];
      
      // Find the current resume + jd pairing
      const currentPairing = pairings.find(p => 
        p.resume_id === resumeId && p.jd_id === jdId
      );

      if (currentPairing) {
        setPairingContext({
          resume_id: currentPairing.resume_id,
          jd_id: currentPairing.jd_id,
          resumeName: currentPairing.resumeName,
          jobTitle: currentPairing.jobTitle,
          jobDescription: currentPairing.jobDescription,
          technical: currentPairing.technical === true,
        });
        // Find the current question set
        const currentQuestionSetData = currentPairing.questionSets.find(qs => 
          qs.questionSetNumber === questionSet
        );

        if (currentQuestionSetData) {
          setInterviewHistory(currentQuestionSetData.interviews || []);
          setHasExistingInterviews(currentQuestionSetData.total_attempts > 0);
          console.log('[DEBUG] Interview history for question set', questionSet, ':', currentQuestionSetData);
        } else {
          setInterviewHistory([]);
          setHasExistingInterviews(false);
        }
      } else {
        setPairingContext(null);
        setInterviewHistory([]);
        setHasExistingInterviews(false);
      }
    } catch (error) {
      console.warn('Error fetching interview history:', error);
      // Don't fail the entire page load if this fails
    }
  };

  const deriveQuestionSettingsFromCurrentSet = () => {
    const counts = questions.reduce((acc, item) => {
      const rawLevel = String(item.difficulty_category || item.difficulty_level || '').trim().toLowerCase();
      if (rawLevel === 'coding') {
        acc.coding += 1;
        return acc;
      }
      const normalized = normalizeLevel(rawLevel);
      if (normalized === 'easy') acc.easy += 1;
      else if (normalized === 'hard') acc.hard += 1;
      else acc.medium += 1;
      return acc;
    }, { easy: 0, medium: 0, hard: 0, coding: 0 });

    setEasyQuestions(Math.max(1, counts.easy || 1));
    setMediumQuestions(Math.max(1, counts.medium || 1));
    setHardQuestions(Math.max(1, counts.hard || 1));
    setCodingQuestions(pairingContext?.technical === true ? counts.coding : 0);
    setSplitMode(false);
    setBlendMode(false);
    setSplitResumePercentage(50);
    setBlendResumePercentage(50);
    setQuestionValidationError('');
  };

  const canRegenerateQuestions = () => {
    if (splitMode && blendMode) {
      const totalQuestions = easyQuestions + mediumQuestions + hardQuestions;
      return totalQuestions >= 6;
    }
    return true;
  };

  const getRegenerateDisabledReason = () => {
    if (splitMode && blendMode) {
      const totalQuestions = easyQuestions + mediumQuestions + hardQuestions;
      if (totalQuestions < 6) {
        return pairingContext?.technical === true
          ? 'When both Split and Blend modes are enabled, you need at least 6 total questions, excluding coding questions.'
          : 'When both Split and Blend modes are enabled, you need at least 6 total questions.';
      }
    }
    return '';
  };

  const handleOpenRegenerateModal = () => {
    deriveQuestionSettingsFromCurrentSet();
    setShowQuestionModal(true);
  };

  const generateQuestionsFromBackend = async (questionSettings = {}) => {
    if (!pairingContext || !currentResumeId || !currentJdId) {
      throw new Error('Resume, job description, and question set are required to regenerate questions.');
    }

    const session = await getSession();
    if (!session) {
      throw new Error('No active session');
    }

    const excludeQuestionTexts = questions
      .map((item) => (item.question_text || item.question || '').trim())
      .filter(Boolean);

    const backendOrigin = getBackendOrigin();
    const response = await fetch(`${backendOrigin}/api/generate-questions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        resume_id: currentResumeId,
        jd_id: currentJdId,
        job_title: pairingContext.jobTitle,
        job_description: pairingContext.jobDescription,
        exclude_question_texts: excludeQuestionTexts,
        question_counts: {
          beginner: questionSettings.easy || 1,
          medium: questionSettings.medium || 1,
          hard: questionSettings.hard || 1,
          coding: pairingContext.technical === true ? (questionSettings.coding || 0) : 0,
        },
        split: questionSettings.splitMode || false,
        resume_pct: questionSettings.splitResumePercentage || 50,
        jd_pct: 100 - (questionSettings.splitResumePercentage || 50),
        blend: questionSettings.blendMode || false,
        blend_pct_resume: questionSettings.blendResumePercentage || 50,
        blend_pct_jd: 100 - (questionSettings.blendResumePercentage || 50),
      }),
    });

    const result = await response.json();
    if (!response.ok || !result.success) {
      const err = new Error(result.message || 'Failed to generate questions');
      if (result.code) err.code = result.code;
      throw err;
    }
    return result;
  };

  const replaceQuestionsInDatabase = async (generatedQuestions) => {
    const session = await getSession();
    if (!session) {
      throw new Error('No active session');
    }

    const backendOrigin = getBackendOrigin();
    const response = await fetch(`${backendOrigin}/functions/v1/questions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        resume_id: currentResumeId,
        jd_id: currentJdId,
        question_set: currentQuestionSet,
        replace: true,
        questions: generatedQuestions,
      }),
    });

    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(result.message || 'Failed to save regenerated questions');
    }
    return result;
  };

  const handleConfirmRegenerateQuestions = async () => {
    if (!canRegenerateQuestions()) {
      setQuestionValidationError(getRegenerateDisabledReason());
      return;
    }

    setQuestionValidationError('');
    setShowQuestionModal(false);
    setIsRegeneratingQuestions(true);

    try {
      const questionsResult = await generateQuestionsFromBackend({
        easy: easyQuestions,
        medium: mediumQuestions,
        hard: hardQuestions,
        coding: codingQuestions,
        splitMode,
        blendMode,
        splitResumePercentage,
        blendResumePercentage,
      });

      const questionsSaveResult = await replaceQuestionsInDatabase(questionsResult.data?.questions || []);
      const savedQuestions = questionsSaveResult.data || [];
      const uniqueQuestions = savedQuestions.reduce((acc, item) => {
        const questionText = item.question_text || item.question;
        if (questionText) {
          acc.add(questionText);
        }
        return acc;
      }, new Set());

      setQuestions(savedQuestions);
      setExpandedQuestions(new Set());
      setSearchTerm('');
      setFilterLevel('all');
      setNoticeModal({
        isOpen: true,
        title: 'Questions regenerated',
        message: `Set ${currentQuestionSet} was updated with ${uniqueQuestions.size || savedQuestions.length} refreshed question${(uniqueQuestions.size || savedQuestions.length) === 1 ? '' : 's'}.`,
        variant: 'info',
        primaryLabel: 'OK',
      });

      trackEvents.questionsRegenerated({
        resume_id: currentResumeId,
        jd_id: currentJdId,
        question_set: currentQuestionSet,
        regeneration_timestamp: new Date().toISOString(),
        questions_count: savedQuestions.length,
      });
    } catch (error) {
      console.error('Error regenerating questions:', error);
      if (isAuthErrorMessage(error.message)) {
        redirectToExpiredLogin();
        return;
      }
      const isDossierMissing = error?.code === 'DOSSIER_MISSING';
      setNoticeModal({
        isOpen: true,
        title: isDossierMissing ? 'Interview profile missing' : 'Could not regenerate questions',
        message: isDossierMissing
          ? 'No saved interview dossier was found for this pair. Create questions again from Upload.'
          : (error.message || 'Could not regenerate questions.'),
        variant: 'error',
        primaryLabel: 'OK',
      });
    } finally {
      setIsRegeneratingQuestions(false);
    }
  };

  // One row per question with a single sample answer.
  const displayQuestions = Object.values(
    questions.reduce((acc, item) => {
      const normalizedLevel = normalizeLevel(item.difficulty_category || item.difficulty_level);
      const questionText = item.question_text || item.question || '';
      const questionKey = `${normalizedLevel}::${questionText.trim().toLowerCase()}`;
      const answer = item.expected_answer || item.answer || '';
      const missing = !hasSampleAnswer(answer);

      if (!acc[questionKey]) {
        acc[questionKey] = {
          question_id: item.id || questionKey,
          question: questionText,
          level: normalizedLevel,
          originalIndex: Object.keys(acc).length,
          answer,
          missing,
        };
      } else if (!acc[questionKey].missing && missing) {
        // Keep existing filled answer
      } else if (acc[questionKey].missing && !missing) {
        acc[questionKey].answer = answer;
        acc[questionKey].missing = false;
        if (item.id) acc[questionKey].question_id = item.id;
      }

      return acc;
    }, {})
  );

  const sortQuestionsByDifficulty = (list) => {
    return [...list].sort((a, b) => {
      const aOrder = DIFFICULTY_ORDER[a.level] || 999;
      const bOrder = DIFFICULTY_ORDER[b.level] || 999;
      return aOrder - bOrder || a.originalIndex - b.originalIndex;
    });
  };

  const filteredQuestions = sortQuestionsByDifficulty(
    displayQuestions.filter((q) => {
      const matchesLevel = filterLevel === 'all' || normalizeLevel(q.level) === normalizeLevel(filterLevel);
      const matchesSearch = q.question.toLowerCase().includes(searchTerm.toLowerCase());
      return matchesLevel && matchesSearch;
    })
  );

  const sampleAnswersMissing = displayQuestions.some((q) => q.missing);

  const handleDownloadQuestionsPdf = async () => {
    if (!displayQuestions.length || !currentQuestionSet || isDownloadingPdf) return;

    try {
      setIsDownloadingPdf(true);
      await generateQuestionsPDF({
        questionsList: sortQuestionsByDifficulty(displayQuestions),
        questionSet: currentQuestionSet,
        jobTitle: pairingContext?.jobTitle || '',
      });
    } catch (error) {
      console.error('Error downloading questions PDF:', error);
      setNoticeModal({
        isOpen: true,
        title: 'Download failed',
        message: 'Could not download the questions PDF. Please try again.',
        variant: 'error',
      });
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  const closeNoticeModal = () => {
    setNoticeModal({
      isOpen: false,
      title: '',
      message: '',
      variant: 'error',
      actionButton: null,
      primaryLabel: undefined,
      onPrimary: undefined,
      secondaryLabel: undefined,
      onSecondary: undefined,
    });
  };

  const sampleAnswersErrorCopy = (rawMessage = '') => {
    const msg = String(rawMessage || '').trim();
    const lower = msg.toLowerCase();

    if (
      lower.includes('timeout') ||
      lower.includes('timed out') ||
      lower.includes('aborted')
    ) {
      return {
        title: 'Generation took too long',
        message:
          'Sample answer generation timed out before finishing. Retry generates only questions that still need an answer.',
        retryable: true,
      };
    }

    if (
      lower.includes('complete sample answer') ||
      lower.includes('did not return') ||
      lower.includes('incomplete')
    ) {
      const countMatch = msg.match(/(\d+)\s*question/i);
      const countLabel = countMatch ? `${countMatch[1]} question(s)` : 'one or more questions';
      return {
        title: 'Sample answers incomplete',
        message: `We couldn't finish sample answers for ${countLabel}. Retry generates only the remaining questions — answers that already succeeded are kept.`,
        retryable: true,
      };
    }

    if (lower.includes('dossier') || lower.includes('missing')) {
      return {
        title: 'Could not generate sample answers',
        message: msg || 'Sample answers could not be generated for this question set.',
        retryable: false,
      };
    }

    return {
      title: 'Could not generate sample answers',
      message:
        msg ||
        'Something went wrong while generating sample answers. You can retry, or dismiss and try again later.',
      retryable: true,
    };
  };

  const handleGenerateSampleAnswers = async () => {
    if (!currentResumeId || !currentJdId || !currentQuestionSet) {
      setNoticeModal({
        isOpen: true,
        title: 'Missing data',
        message: 'Resume, job description, and question set are required to generate sample answers.',
        variant: 'info',
        primaryLabel: 'OK',
      });
      return;
    }

    setIsGeneratingAnswers(true);
    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const backendOrigin = getBackendOrigin();
      const response = await fetch(`${backendOrigin}/api/generate-answers`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        signal: typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
          ? AbortSignal.timeout(GENERATE_ANSWERS_TIMEOUT_MS)
          : undefined,
        body: JSON.stringify({
          resume_id: currentResumeId,
          jd_id: currentJdId,
          question_set: currentQuestionSet,
        }),
      });

      if (!response.ok) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('text/html') && response.status === 504) {
          throw new Error('Sample answer generation timed out on the server. Please try again.');
        }
        let errorData = {};
        try {
          errorData = await response.json();
        } catch {
          errorData = {};
        }
        if (Array.isArray(errorData.data?.questions) && errorData.data.questions.length) {
          setQuestions(errorData.data.questions);
        }
        const savedCount = Number(errorData.data?.generated_count || 0);
        const missingCount = Number(errorData.data?.missing_count || 0);
        if (savedCount > 0 && missingCount > 0) {
          throw new Error(
            `LLM did not return complete sample answers for ${missingCount} question(s). Please try again.`
          );
        }
        throw new Error(errorData.message || `Failed to generate sample answers: ${response.status}`);
      }

      const result = await response.json();
      if (!result.success) {
        throw new Error(result.message || 'Sample answer generation failed');
      }

      const savedQuestions = result.data?.questions || [];
      const missingCount = Number(result.data?.missing_count || 0);
      const generatedCount = Number(result.data?.generated_count ?? 0);

      if (savedQuestions.length) {
        setQuestions(savedQuestions);
        setExpandedQuestions(new Set());
      }

      if (result.partial || missingCount > 0) {
        const remainingLabel = `${missingCount} question${missingCount === 1 ? '' : 's'}`;
        setNoticeModal({
          isOpen: true,
          title: 'Sample answers incomplete',
          message: generatedCount > 0
            ? `Saved sample answers for ${generatedCount} question${generatedCount === 1 ? '' : 's'}. Retry will generate only the remaining ${remainingLabel}.`
            : `We couldn't finish sample answers for ${remainingLabel}. Retry generates only those that are still missing.`,
          variant: 'warning',
          primaryLabel: 'Retry',
          onPrimary: () => {
            closeNoticeModal();
            handleGenerateSampleAnswers();
          },
          secondaryLabel: 'Dismiss',
          onSecondary: closeNoticeModal,
        });
        return;
      }

      const uniqueQuestionCount = savedQuestions.length;
      let readyMessage;
      if (result.data?.already_complete) {
        readyMessage = 'All questions already have sample answers.';
      } else if (generatedCount > 0 && generatedCount < uniqueQuestionCount) {
        readyMessage = `Filled in sample answers for the remaining ${generatedCount} question${generatedCount === 1 ? '' : 's'}.`;
      } else {
        readyMessage = `Generated sample answers for ${uniqueQuestionCount || 'your'} question${uniqueQuestionCount === 1 ? '' : 's'}.`;
      }
      setNoticeModal({
        isOpen: true,
        title: 'Sample answers ready',
        message: readyMessage,
        variant: 'info',
        primaryLabel: 'OK',
      });
    } catch (error) {
      console.error('Error generating sample answers:', error);
      if (isAuthErrorMessage(error.message)) {
        redirectToExpiredLogin();
        return;
      }
      const rawMessage =
        error?.name === 'TimeoutError' || error?.name === 'AbortError'
          ? 'Sample answer generation timed out. Please try again.'
          : error.message;
      const copy = sampleAnswersErrorCopy(rawMessage);
      setNoticeModal({
        isOpen: true,
        title: copy.title,
        message: copy.message,
        variant: copy.retryable ? 'warning' : 'error',
        primaryLabel: copy.retryable ? 'Retry' : 'OK',
        onPrimary: copy.retryable
          ? () => {
              closeNoticeModal();
              handleGenerateSampleAnswers();
            }
          : undefined,
        secondaryLabel: copy.retryable ? 'Dismiss' : undefined,
        onSecondary: copy.retryable ? closeNoticeModal : undefined,
      });
    } finally {
      setIsGeneratingAnswers(false);
    }
  };

  const toggleQuestion = (questionId) => {
    const newExpanded = new Set(expandedQuestions);
    if (newExpanded.has(questionId)) {
      newExpanded.delete(questionId);
    } else {
      newExpanded.add(questionId);
    }
    setExpandedQuestions(newExpanded);
  };
  const runScheduleInterview = async ({ retakeFrom } = {}) => {
    if (!currentResumeId || !currentJdId || !currentQuestionSet) {
      setNoticeModal({
        isOpen: true,
        title: 'Missing data',
        message: 'Please ensure resume, job description, and question set are available.',
        variant: 'info',
      });
      return;
    }

    setIsPaymentLoading(true);
    try {
      await scheduleInterview({
        resumeId: currentResumeId,
        jdId: currentJdId,
        questionSet: currentQuestionSet,
        retakeFrom,
      });
    } catch (error) {
      console.error('Error scheduling interview:', error);
      const isAlreadyActive =
        error.message?.toLowerCase().includes('active interview') ||
        error.message?.toLowerCase().includes('in progress') ||
        error.message?.toLowerCase().includes('resume');

      const activeInterview = interviewHistory.find(
        (interview) =>
          interview.status === 'STARTED' ||
          interview.status === 'ACTIVE' ||
          interview.status === 'in_progress'
      );

      setNoticeModal({
        isOpen: true,
        title: isAlreadyActive ? 'Active Interview In Progress' : (retakeFrom ? 'Retake Failed' : 'Payment Failed'),
        message: error.message || 'An unexpected error occurred.',
        variant: isAlreadyActive ? 'info' : 'error',
        actionButton: (isAlreadyActive && activeInterview) ? (
          <button
            type="button"
            onClick={() => {
              setNoticeModal({ isOpen: false, title: '', message: '', variant: 'error', actionButton: null });
              window.location.href = `/interview?interview_id=${activeInterview.id}`;
            }}
            className="w-full py-2.5 px-4 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <FiPlay size={14} /> Resume Interview
          </button>
        ) : null,
      });
      setIsPaymentLoading(false);
    }
  };

  const handlePayment = async () => {
    if (!currentResumeId || !currentJdId) {
      setNoticeModal({
        isOpen: true,
        title: 'Upload required',
        message: 'Please ensure resume and job description are uploaded first.',
        variant: 'info',
      });
      return;
    }
    await runScheduleInterview();
  };

  const handleRetakeInterview = async () => {
    const activeInterview = interviewHistory.find(
      (interview) =>
        interview.status === 'STARTED' ||
        interview.status === 'ACTIVE' ||
        interview.status === 'in_progress'
    );

    if (activeInterview) {
      setNoticeModal({
        isOpen: true,
        title: 'Active Interview In Progress',
        message: 'You already have an active interview in progress for this question set. Please resume your current interview before starting a new retake.',
        variant: 'info',
        actionButton: (
          <button
            type="button"
            onClick={() => {
              setNoticeModal({ isOpen: false, title: '', message: '', variant: 'error', actionButton: null });
              window.location.href = `/interview?interview_id=${activeInterview.id}`;
            }}
            className="w-full py-2.5 px-4 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <FiPlay size={14} /> Resume Interview
          </button>
        ),
      });
      return;
    }

    const originalInterview = interviewHistory.find(
      (interview) => interview.status === 'completed' || interview.status === 'ENDED'
    );

    if (!originalInterview) {
      setNoticeModal({
        isOpen: true,
        title: 'Retake Unavailable',
        message: 'No completed interview found to retake from.',
        variant: 'info',
      });
      return;
    }

    await runScheduleInterview({ retakeFrom: originalInterview.id });
  };

  const scheduleButtonLabel = (() => {
    if (isPaymentLoading) return 'Processing...';
    if (interviewQuota?.free_remaining > 0) {
      return `Schedule Interview (Free)`;
    }
    return 'Schedule Interview';
  })();

  const activeInterview = interviewHistory.find(
    (interview) =>
      interview.status === 'STARTED' ||
      interview.status === 'ACTIVE' ||
      interview.status === 'in_progress'
  );

  const hasCompletedInterview = interviewHistory.some(
    (interview) => interview.status === 'completed' || interview.status === 'ENDED'
  );

  const handleResumeInterview = () => {
    if (!activeInterview?.id) return;
    window.location.href = `/interview?interview_id=${activeInterview.id}`;
  };
  
  return (
    <>
      <Navbar />
      <PageWavesShell contentClassName="text-[var(--color-text-primary)] px-3 sm:px-4 py-6 sm:py-8 md:py-12 lg:py-16 flex justify-center">
        <div className="w-full max-w-6xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="text-center mb-8 sm:mb-10"
          >
            <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tight text-[var(--color-text-primary)] mb-3 sm:mb-4">
              Interview Questions & Answers
            </h1>
            <p className="text-sm sm:text-base md:text-lg text-[var(--color-text-primary)]/80 max-w-2xl mx-auto leading-relaxed px-2 mb-4">
              Review generated questions for your interview preparation. Sample answers can be generated on demand.
            </p>

            {/* Question set toolbar */}
            {currentQuestionSet && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.3 }}
                className="flex flex-col items-center mt-4 max-w-3xl mx-auto w-full"
              >
                {/* Info row */}
                <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm sm:text-base text-[var(--color-text-secondary)]">
                  <span className="inline-flex items-center gap-2">
                    <FiFileText className="w-4 h-4 text-[var(--color-text-primary)] shrink-0" aria-hidden />
                    <span className="font-medium text-[var(--color-text-primary)]">
                      Question Set {currentQuestionSet}
                    </span>
                  </span>
                  <span className="hidden sm:block h-4 w-px bg-[var(--color-text-primary)]/40" aria-hidden />
                  <span className="inline-flex items-center gap-2">
                    <FiMessageSquare className="w-4 h-4 text-[var(--color-text-primary)] shrink-0" aria-hidden />
                    <span className="font-medium text-[var(--color-text-primary)]">
                      {displayQuestions.length} Question{displayQuestions.length !== 1 ? 's' : ''}
                    </span>
                  </span>
                </div>

                {!loading && !error && (
                  <>
                    <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 w-full mt-4">
                      {displayQuestions.length > 0 && (
                        <button
                          type="button"
                          onClick={handleDownloadQuestionsPdf}
                          disabled={isDownloadingPdf}
                          className="inline-flex items-center gap-2 text-sm font-medium px-4 sm:px-5 py-2.5 rounded-lg border border-[var(--color-border)] text-[var(--color-text-primary)] bg-[var(--color-input-bg)] hover:bg-[var(--color-card)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                        >
                          {isDownloadingPdf ? (
                            <>
                              <FiLoader className="w-4 h-4 animate-spin" />
                              Preparing PDF...
                            </>
                          ) : (
                            <>
                              <FiDownload className="w-4 h-4" />
                              Download PDF
                            </>
                          )}
                        </button>
                      )}
                      {!hasExistingInterviews && pairingContext && (
                        <button
                          type="button"
                          onClick={handleOpenRegenerateModal}
                          disabled={isRegeneratingQuestions}
                          className="inline-flex items-center gap-2 text-sm font-medium px-4 sm:px-5 py-2.5 rounded-lg border border-[var(--color-border)] text-[var(--color-text-primary)] bg-[var(--color-input-bg)] hover:bg-[var(--color-card)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                        >
                          <FiRefreshCw className={`w-4 h-4 ${isRegeneratingQuestions ? 'animate-spin' : ''}`} />
                          {isRegeneratingQuestions ? 'Regenerating...' : 'Regenerate Questions'}
                        </button>
                      )}
                      {sampleAnswersMissing && (
                        <button
                          type="button"
                          onClick={handleGenerateSampleAnswers}
                          disabled={isGeneratingAnswers}
                          className="inline-flex items-center gap-2 text-sm font-medium px-4 sm:px-5 py-2.5 rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity shadow-sm"
                        >
                          {isGeneratingAnswers ? (
                            <>
                              <FiLoader className="w-4 h-4 animate-spin" />
                              Generating answers...
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-4 h-4" aria-hidden />
                              Generate Sample Answers
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </>
                )}
              </motion.div>
            )}
          </motion.div>

          {/* Filters */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="bg-[var(--color-card)] rounded-xl sm:rounded-2xl lg:rounded-3xl shadow-lg sm:shadow-xl lg:shadow-2xl border border-[var(--color-border)] p-4 sm:p-6 lg:p-8 mb-6 sm:mb-8"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="sm:col-span-1">
                <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2 flex items-center">
                  <FiSearch className="mr-2" size={16} />
                  Search Questions
                </label>
                <input
                  type="text"
                  placeholder="Search questions..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full px-3 sm:px-4 py-2 sm:py-3 border border-[var(--color-border)] rounded-lg sm:rounded-xl bg-[var(--color-input-bg)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition-colors text-sm sm:text-base"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2 flex items-center">
                  <FiFilter className="mr-2" size={16} />
                  Question Difficulty
                </label>
                 <div className="relative">
                <select
                  value={filterLevel}
                  onChange={(e) => setFilterLevel(e.target.value)}
                     className="appearance-none w-full px-3 sm:px-4 py-2 sm:py-3 pr-10 border border-[var(--color-border)] rounded-lg sm:rounded-xl bg-[var(--color-input-bg)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition-all duration-200 text-sm sm:text-base hover:border-[var(--color-primary)] cursor-pointer"
                >
                  <option value="all">All Levels</option>
                     <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
                   <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                     <svg className="w-4 h-4 text-[var(--color-text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                       <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                     </svg>
                   </div>
                 </div>
              </div>
            </div>
          </motion.div>

          {/* Questions List */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.2 }}
            className="space-y-4 sm:space-y-6"
          >
            {loading ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="text-center py-12 sm:py-16"
              >
                <FiLoader className="w-12 h-12 sm:w-16 sm:h-16 text-[var(--color-text-secondary)] mx-auto mb-4 sm:mb-6 animate-spin" />
                <p className="text-[var(--color-text-secondary)] text-base sm:text-lg mb-2">
                  {currentQuestionSet ? `Loading questions from Set ${currentQuestionSet}...` : 'Loading question sets for this resume & job combination...'}
                </p>
              </motion.div>
            ) : error ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="text-center py-12 sm:py-16"
              >
                <div className="mx-auto mb-4 sm:mb-6 w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <FiAlertCircle className="w-7 h-7 sm:w-8 sm:h-8 text-[var(--color-error)]" />
                </div>
                <p className="text-[var(--color-error)] text-base sm:text-lg font-semibold mb-3">Error loading questions</p>
                <div className="app-inline-error max-w-md mx-auto text-left" role="alert">
                  <FiAlertCircle className="app-inline-error-icon" aria-hidden="true" />
                  <span>{error}</span>
                </div>
              </motion.div>
            ) : availableQuestionSets.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="text-center py-12 sm:py-16"
              >
                <FiFileText className="w-12 h-12 sm:w-16 sm:h-16 text-[var(--color-text-secondary)] mx-auto mb-4 sm:mb-6" />
                <p className="text-[var(--color-text-secondary)] text-base sm:text-lg mb-2">No question sets available</p>
                <p className="text-[var(--color-text-secondary)] text-sm">Complete an interview to generate questions.</p>
              </motion.div>
            ) : (
              <>
                {filteredQuestions.map((questionGroup, index) => (
                  <motion.div
                    key={questionGroup.question_id}
                    custom={index}
                    variants={questionCardVariants}
                    initial="hidden"
                    animate="visible"
                    whileHover={{ y: -4, scale: 1.006 }}
                    className="bg-[var(--color-card)] rounded-xl sm:rounded-2xl lg:rounded-3xl shadow-lg sm:shadow-xl lg:shadow-2xl border border-[var(--color-border)] overflow-hidden"
                  >
                    <div 
                      className="p-4 sm:p-6 lg:p-8 cursor-pointer hover:bg-[var(--color-input-bg)] transition-colors"
                      onClick={() => toggleQuestion(questionGroup.question_id)}
                    >
                      <div className="flex items-start sm:items-center justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-3 sm:mb-4">
                            <span className="text-xs sm:text-sm font-medium text-[var(--color-text-secondary)] bg-[var(--color-input-bg)] px-2 sm:px-4 py-1 sm:py-2 rounded-lg sm:rounded-xl">
                              Q{index + 1}
                            </span>
                            <span className={`px-2 sm:px-4 py-1 sm:py-2 text-xs sm:text-sm font-medium rounded-lg sm:rounded-xl border ${getLevelColor(questionGroup.level)}`}>
                              {formatLabel(questionGroup.level)}
                            </span>
                          </div>
                          <h3 className="text-base sm:text-lg lg:text-xl font-semibold text-[var(--color-text-primary)] leading-relaxed">
                            {questionGroup.question}
                          </h3>
                        </div>
                        <div className="flex-shrink-0">
                          {expandedQuestions.has(questionGroup.question_id) ? (
                            <ChevronUpIcon className="h-5 w-5 sm:h-6 sm:w-6 text-[var(--color-text-secondary)]" />
                          ) : (
                            <ChevronDownIcon className="h-5 w-5 sm:h-6 sm:w-6 text-[var(--color-text-secondary)]" />
                          )}
                        </div>
                      </div>
                    </div>
   
                    
                    <AnimatePresence>
                      {expandedQuestions.has(questionGroup.question_id) && (
                        <motion.div
                          initial={{ opacity: 0, height: 0, y: -12, filter: 'blur(8px)' }}
                          animate={{ opacity: 1, height: 'auto', y: 0, filter: 'blur(0px)' }}
                          exit={{ opacity: 0, height: 0, y: -12, filter: 'blur(8px)' }}
                          transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
                          className="px-4 sm:px-6 lg:px-8 pb-4 sm:pb-6 lg:pb-8 border-t border-[var(--color-border)]"
                        >
                          <div className="mt-4 sm:mt-6">
                            <motion.div
                              variants={answerCardVariants}
                              initial="hidden"
                              animate="visible"
                              className="bg-[var(--color-input-bg)] rounded-lg sm:rounded-xl p-4 sm:p-6 border border-[var(--color-border)]"
                            >
                              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
                                <h4 className="text-sm font-medium text-[var(--color-text-primary)] flex items-center">
                                  <FiCode className="mr-2" size={16} />
                                  Sample Answer
                                </h4>
                              </div>
                              <div className="bg-[var(--color-card)] rounded-lg sm:rounded-xl p-3 sm:p-6 border border-[var(--color-border)]">
                                {questionGroup.missing ? (
                                  <p className="text-sm sm:text-base text-[var(--color-text-secondary)] leading-relaxed">
                                    No sample answer was generated for this question yet.
                                  </p>
                                ) : (
                                  <AnswerContent answer={questionGroup.answer} />
                                )}
                              </div>
                            </motion.div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                ))}
              </>
            )}

            {!loading && !error && availableQuestionSets.length > 0 && filteredQuestions.length === 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="text-center py-12 sm:py-16"
              >
                <FiFileText className="w-12 h-12 sm:w-16 sm:h-16 text-[var(--color-text-secondary)] mx-auto mb-4 sm:mb-6" />
                <p className="text-[var(--color-text-secondary)] text-base sm:text-lg mb-2">
                  No questions found matching your criteria in Set {currentQuestionSet} for this resume & job combination.
                </p>
                <p className="text-[var(--color-text-secondary)] text-sm">Try adjusting your filters or search terms.</p>
              </motion.div>
            )}
          </motion.div>



          {/* Action Buttons - Bottom of Page */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.4 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-8 sm:mt-12"
          >
            {/* Match Dashboard: Resume while in progress; Retake only after a completed interview */}
            {activeInterview ? (
              <>
                <button
                  onClick={handleResumeInterview}
                  className="inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 text-sm sm:text-base font-semibold rounded-xl sm:rounded-2xl transition-all duration-200 transform hover:scale-105 bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-500 text-white shadow-lg hover:shadow-xl"
                >
                  <FiPlay className="w-4 h-4 sm:w-5 sm:h-5" />
                  Resume Interview
                </button>
                <button
                  onClick={() => window.location.href = '/dashboard'}
                  className="inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 text-sm sm:text-base font-semibold rounded-xl sm:rounded-2xl transition-all duration-200 transform hover:scale-105 bg-[var(--color-card)] hover:bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] shadow-lg hover:shadow-xl"
                >
                  <FiEye className="w-4 h-4 sm:w-5 sm:h-5" />
                  View Dashboard
                </button>
              </>
            ) : hasCompletedInterview ? (
              <>
                <button
                  onClick={handleRetakeInterview}
                  disabled={isPaymentLoading}
                  className={`inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 text-sm sm:text-base font-semibold rounded-xl sm:rounded-2xl transition-all duration-200 transform hover:scale-105 bg-gradient-to-r from-[var(--color-primary)] to-purple-600 hover:from-purple-600 hover:to-[var(--color-primary)] text-white shadow-lg hover:shadow-xl ${
                    isPaymentLoading ? 'opacity-60 cursor-not-allowed' : ''
                  }`}
                >
                  <FiRefreshCw className={`w-4 h-4 sm:w-5 sm:h-5 ${isPaymentLoading ? 'animate-spin' : ''}`} />
                  {isPaymentLoading ? 'Processing...' : 'Retake Interview'}
                </button>
                <button
                  onClick={() => window.location.href = '/dashboard'}
                  className="inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 text-sm sm:text-base font-semibold rounded-xl sm:rounded-2xl transition-all duration-200 transform hover:scale-105 bg-[var(--color-card)] hover:bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] shadow-lg hover:shadow-xl"
                >
                  <FiEye className="w-4 h-4 sm:w-5 sm:h-5" />
                  View Dashboard
                </button>
              </>
            ) : (
              <button
                onClick={handlePayment}
                disabled={isPaymentLoading}
                className={`inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 text-sm sm:text-base font-semibold rounded-xl sm:rounded-2xl transition-all duration-200 transform hover:scale-105 ${
                  isPaymentLoading
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-gradient-to-r from-[var(--color-primary)] to-purple-600 hover:from-purple-600 hover:to-[var(--color-primary)] text-white shadow-lg hover:shadow-xl'
                }`}
              >
                <FiCreditCard className="w-4 h-4 sm:w-5 sm:h-5" />
                {scheduleButtonLabel}
              </button>
            )}
          </motion.div>
        </div>
      </PageWavesShell>
      {showQuestionModal && pairingContext && typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
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
                    Regenerate Questions
                  </h2>
                </div>
                <button
                  onClick={() => {
                    setShowQuestionModal(false);
                    setQuestionValidationError('');
                  }}
                  className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors p-1 rounded-lg hover:bg-[var(--color-hover)]"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-6">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      Question Difficulty Distribution
                    </h3>
                    <span className="text-sm font-medium px-3 py-1 rounded-full bg-[var(--color-primary)]/10 text-[var(--color-primary)]">
                      Total: {easyQuestions + mediumQuestions + hardQuestions + codingQuestions} questions
                    </span>
                  </div>

                  <div className={`grid ${pairingContext.technical === true ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4' : 'grid-cols-1 md:grid-cols-3'} gap-4`}>
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
                        onChange={(e) => setEasyQuestions(parseInt(e.target.value, 10))}
                        className="w-full h-2 bg-green-200/50 dark:bg-green-700/30 rounded-lg appearance-none cursor-pointer slider-green"
                      />
                    </div>

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
                        onChange={(e) => setMediumQuestions(parseInt(e.target.value, 10))}
                        className="w-full h-2 bg-yellow-200/50 dark:bg-yellow-700/30 rounded-lg appearance-none cursor-pointer slider-yellow"
                      />
                    </div>

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
                        onChange={(e) => setHardQuestions(parseInt(e.target.value, 10))}
                        className="w-full h-2 bg-red-200/50 dark:bg-red-700/30 rounded-lg appearance-none cursor-pointer slider-red"
                      />
                    </div>

                    {pairingContext.technical === true && (
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
                          onChange={(e) => setCodingQuestions(parseInt(e.target.value, 10))}
                          className="w-full h-2 bg-blue-200/50 dark:bg-blue-700/30 rounded-lg appearance-none cursor-pointer slider-blue"
                        />
                      </div>
                    )}
                  </div>

                  {questionValidationError && (
                    <div className="mt-4 app-inline-error" role="alert">
                      <FiAlertCircle className="app-inline-error-icon" aria-hidden="true" />
                      <p>{questionValidationError}</p>
                    </div>
                  )}
                </div>

                <div className="space-y-4">
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
                            <div className="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
                              <span>Resume</span>
                              <span>Job Description</span>
                            </div>
                            <input
                              type="range"
                              min="0"
                              max="100"
                              value={splitResumePercentage}
                              onChange={(e) => setSplitResumePercentage(parseInt(e.target.value, 10))}
                              className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer slider mt-3"
                            />
                            <div className="flex justify-between text-sm font-medium text-[var(--color-text-primary)] mt-2">
                              <span>{splitResumePercentage}%</span>
                              <span>{100 - splitResumePercentage}%</span>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

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
                            <div className="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
                              <span>Resume Weight</span>
                              <span>Job Description Weight</span>
                            </div>
                            <input
                              type="range"
                              min="0"
                              max="100"
                              value={blendResumePercentage}
                              onChange={(e) => setBlendResumePercentage(parseInt(e.target.value, 10))}
                              className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer slider mt-3"
                            />
                            <div className="flex justify-between text-sm font-medium text-[var(--color-text-primary)] mt-2">
                              <span>{blendResumePercentage}%</span>
                              <span>{100 - blendResumePercentage}%</span>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => {
                    setShowQuestionModal(false);
                    setQuestionValidationError('');
                  }}
                  className="flex-1 py-3 px-4 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-hover)] transition-colors font-semibold"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmRegenerateQuestions}
                  disabled={isRegeneratingQuestions || !canRegenerateQuestions()}
                  title={!canRegenerateQuestions() ? getRegenerateDisabledReason() : ''}
                  className="flex-1 py-3 px-4 rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-semibold"
                >
                  {isRegeneratingQuestions ? 'Regenerating...' : 'Update Current Set'}
                </button>
              </div>
            </motion.div>
          </div>,
          document.body
        )}
      <NoticeModal
        isOpen={noticeModal.isOpen}
        onClose={closeNoticeModal}
        title={noticeModal.title}
        message={noticeModal.message}
        variant={noticeModal.variant || 'error'}
        actionButton={noticeModal.actionButton}
        primaryLabel={noticeModal.primaryLabel}
        onPrimary={noticeModal.onPrimary}
        secondaryLabel={noticeModal.secondaryLabel}
        onSecondary={noticeModal.onSecondary}
      />    </>
  );
}
