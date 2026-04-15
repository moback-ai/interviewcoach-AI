import { useState, useEffect, useRef } from 'react';
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { FiSearch, FiFilter, FiCode, FiFileText, FiCopy, FiCreditCard, FiLoader, FiRefreshCw, FiEye } from 'react-icons/fi'; // Add FiLoader, FiRefreshCw, FiEye
import { useTheme } from '../hooks/useTheme';
import Navbar from '../components/Navbar';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { motion, AnimatePresence } from 'framer-motion';
import { supabase } from '../supabaseClient';
import { useAuth } from '../contexts/AuthContext';
import { useSearchParams } from 'react-router-dom';
import { trackEvents } from '../services/mixpanel';


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

const getStrengthColor = (strength) => {
  switch (strength) {
    case 'beginner':
      return 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800';
    case 'intermediate':
      return 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800';
    case 'expert':
      return 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200 dark:bg-gray-900/20 dark:text-gray-400 dark:border-gray-800';
  }
};



// ... existing mock data and helper functions ...

const SyntaxHighlightedCode = ({ code, language = 'python' }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  // Get language display name and file extension
  const getLanguageInfo = (lang) => {
    const languageMap = {
      'python': { name: 'Python', ext: 'py' },
      'javascript': { name: 'JavaScript', ext: 'js' },
      'js': { name: 'JavaScript', ext: 'js' },
      'typescript': { name: 'TypeScript', ext: 'ts' },
      'ts': { name: 'TypeScript', ext: 'ts' },
      'java': { name: 'Java', ext: 'java' },
      'cpp': { name: 'C++', ext: 'cpp' },
      'c++': { name: 'C++', ext: 'cpp' },
      'c': { name: 'C', ext: 'c' },
      'csharp': { name: 'C#', ext: 'cs' },
      'cs': { name: 'C#', ext: 'cs' },
      'php': { name: 'PHP', ext: 'php' },
      'ruby': { name: 'Ruby', ext: 'rb' },
      'go': { name: 'Go', ext: 'go' },
      'rust': { name: 'Rust', ext: 'rs' },
      'swift': { name: 'Swift', ext: 'swift' },
      'kotlin': { name: 'Kotlin', ext: 'kt' },
      'scala': { name: 'Scala', ext: 'scala' },
      'sql': { name: 'SQL', ext: 'sql' },
      'html': { name: 'HTML', ext: 'html' },
      'css': { name: 'CSS', ext: 'css' },
      'bash': { name: 'Bash', ext: 'sh' },
      'shell': { name: 'Shell', ext: 'sh' },
      'json': { name: 'JSON', ext: 'json' },
      'yaml': { name: 'YAML', ext: 'yml' },
      'yml': { name: 'YAML', ext: 'yml' },
      'markdown': { name: 'Markdown', ext: 'md' },
      'md': { name: 'Markdown', ext: 'md' }
    };
    
    return languageMap[lang.toLowerCase()] || { name: lang, ext: lang };
  };

  const langInfo = getLanguageInfo(language);

  return (
    <div className="bg-gray-900 dark:bg-gray-800 rounded-xl my-4 overflow-hidden border border-gray-700 dark:border-gray-600 shadow-lg">
      <div className="flex items-center justify-between px-3 sm:px-4 py-2 sm:py-3 bg-gray-800 dark:bg-gray-700 border-b border-gray-700 dark:border-gray-600">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-red-500"></div>
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-yellow-500"></div>
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-green-500"></div>
          </div>
          <span className="text-xs text-gray-400 dark:text-gray-500 font-mono ml-1 sm:ml-2">
            {langInfo.name}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-300 dark:text-gray-500 dark:hover:text-gray-400 transition-colors px-2 py-1 rounded-lg hover:bg-gray-700 dark:hover:bg-gray-600"
        >
          <FiCopy size={12} />
          <span className="hidden sm:inline">{copied ? 'Copied!' : 'Copy'}</span>
        </button>
      </div>
      <div className="overflow-x-auto">
        <div className="p-3 sm:p-4">
          <SyntaxHighlighter
            language={language.toLowerCase()}
            style={vscDarkPlus}
            customStyle={{
              margin: 0,
              padding: 0,
              fontSize: '0.75rem',
              lineHeight: '1.4',
              backgroundColor: 'transparent',
              minWidth: '100%',
            }}
            showLineNumbers={false}
            wrapLines={true}
            wrapLongLines={true}
          >
            {code}
          </SyntaxHighlighter>
        </div>
      </div>
    </div>
  );
};

// ... rest of the component remains the same ...

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

const AnswerContent = ({ answer }) => {
  if (!answer) return null;
  
  // First, try to split by markdown code blocks
  const markdownParts = answer.split(/(```[\w]*\n[\s\S]*?```)/);
  
  // If we found markdown blocks, use them
  if (markdownParts.length > 1) {
    return (
      <div className="space-y-4">
        {markdownParts.map((part, index) => {
          if (part.startsWith('```')) {
            // Extract the language and code from the markdown code block
            const codeMatch = part.match(/```(\w*)\n([\s\S]*?)```/);
            if (codeMatch) {
              const language = codeMatch[1] || 'text';
              const code = codeMatch[2].trim();
              return <SyntaxHighlightedCode key={index} code={code} language={language} />;
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
                {line || '\u00A0'}
              </p>
            ))}
          </div>
        ) : (
          <div className="text-[var(--color-text-primary)] leading-relaxed">
            {text.split('\n').map((line, lineIndex) => (
              <p key={lineIndex} className="mb-2 text-sm sm:text-base">
                {line || '\u00A0'}
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
          return <SyntaxHighlightedCode key={`code-${baseIndex}-${index}`} code={item.content} language={language} />;
        } else {
          return (
            <div key={`text-${baseIndex}-${index}`} className="text-[var(--color-text-primary)] leading-relaxed">
              {item.content.split('\n').map((line, lineIndex) => (
                <p key={lineIndex} className="mb-2 text-sm sm:text-base">
                  {line || '\u00A0'}
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
  const { theme } = useTheme();
  const [expandedQuestions, setExpandedQuestions] = useState(new Set());
  const [filterLevel, setFilterLevel] = useState('all');
  const [filterStrength, setFilterStrength] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [isPaymentLoading, setIsPaymentLoading] = useState(false);
  // Database state
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentQuestionSet, setCurrentQuestionSet] = useState(null);
  const [availableQuestionSets, setAvailableQuestionSets] = useState([]);
  const [paymentStatus, setPaymentStatus] = useState(null);
  const [signatureOk, setSignatureOk] = useState(null);
  const [paymentDebug, setPaymentDebug] = useState([]);
  const [currentResumeId, setCurrentResumeId] = useState(null);
  const [currentJdId, setCurrentJdId] = useState(null);
  const [interviewHistory, setInterviewHistory] = useState([]);
  const [hasExistingInterviews, setHasExistingInterviews] = useState(false);
  
  // Prevent duplicate event tracking
  const hasTrackedQuestionsAccessed = useRef(false);

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

        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          throw new Error('No active session');
        }

        const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
        
        // First, get all available question sets for this specific resume_id + jd_id combination
        const questionSetsResponse = await fetch(`${supabaseUrl}/functions/v1/questions?resume_id=${resumeIdFromUrl}&jd_id=${jdIdFromUrl}`, {
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
          const questionsResponse = await fetch(`${supabaseUrl}/functions/v1/questions?resume_id=${resumeIdFromUrl}&jd_id=${jdIdFromUrl}&question_set=${targetQuestionSet}`, {
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
        setError(error.message);
      } finally {
        setLoading(false);
      }
    };

    fetchQuestions();
  }, [searchParams]); // ✅ Add searchParams as dependency

  // ✅ New function to fetch interview history for the current question set
  const fetchInterviewHistory = async (resumeId, jdId, questionSet, accessToken) => {
    try {
      const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
      
      // Fetch interview history for this specific question set
      const response = await fetch(`${supabaseUrl}/functions/v1/dashboard`, {
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
        // Find the current question set
        const currentQuestionSetData = currentPairing.questionSets.find(qs => 
          qs.questionSetNumber === questionSet
        );

        if (currentQuestionSetData) {
          setInterviewHistory(currentQuestionSetData.interviews || []);
          setHasExistingInterviews(currentQuestionSetData.total_attempts > 0);
          console.log('[DEBUG] Interview history for question set', questionSet, ':', currentQuestionSetData);
        }
      }
    } catch (error) {
      console.warn('Error fetching interview history:', error);
      // Don't fail the entire page load if this fails
    }
  };

  // Group questions by question_text to show all strength levels together
  const groupedQuestions = questions.reduce((acc, item) => {
    const questionKey = item.question_text; // Use question_text as the key
    
    if (!acc[questionKey]) {
      acc[questionKey] = {
        question_id: item.id, // Use database ID
        question: item.question_text,
        level: item.difficulty_category, // Map from database field
        answers: []
      };
    }
    
    acc[questionKey].answers.push({
      strength: item.difficulty_experience, // Map from database field
      answer: item.expected_answer || 'No answer provided'
    });
    
    return acc;
  }, {});


  // Sort questions by difficulty level (easy -> medium -> hard)
  const sortQuestionsByDifficulty = (questions) => {
    const difficultyOrder = { 'easy': 1, 'medium': 2, 'hard': 3 };
    return questions.sort((a, b) => {
      const aOrder = difficultyOrder[a.level] || 999;
      const bOrder = difficultyOrder[b.level] || 999;
      return aOrder - bOrder;
    });
  };

  // Sort answers by experience level (beginner -> intermediate -> expert)
  const sortAnswersByExperience = (answers) => {
    const experienceOrder = { 'beginner': 1, 'intermediate': 2, 'expert': 3 };
    return answers.sort((a, b) => {
      const aOrder = experienceOrder[a.strength] || 999;
      const bOrder = experienceOrder[b.strength] || 999;
      return aOrder - bOrder;
    });
  };

  // Sort grouped questions and their answers
  const sortedGroupedQuestions = Object.values(groupedQuestions).map(q => ({
    ...q,
    answers: sortAnswersByExperience(q.answers)
  }));

  const filteredQuestions = sortQuestionsByDifficulty(
    sortedGroupedQuestions.filter(q => {
    const matchesLevel = filterLevel === 'all' || q.level === filterLevel;
    const matchesSearch = q.question.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesLevel && matchesSearch;
    })
  );

  const toggleQuestion = (questionId) => {
    const newExpanded = new Set(expandedQuestions);
    if (newExpanded.has(questionId)) {
      newExpanded.delete(questionId);
    } else {
      newExpanded.add(questionId);
    }
    setExpandedQuestions(newExpanded);
  };
  const { user } = useAuth();

  const buildRedirectUrl = (resumeId, jdId, transactionId) => {
    const baseUrl = `${window.location.origin}/payment-status`;
    const params = new URLSearchParams({
      resume_id: resumeId,
      jd_id: jdId,
      transaction_id: transactionId
    });
    return `${baseUrl}?${params.toString()}`;
  };

  const handlePayment = async () => {
    if (!currentResumeId || !currentJdId) {
      alert('Please ensure resume and job description are uploaded first.');
      return;
    }
    
    // Track payment page visit
    trackEvents.paymentPage({
      resume_id: currentResumeId,
      jd_id: currentJdId,
      question_set: currentQuestionSet,
      payment_timestamp: new Date().toISOString()
    });
    
    try {
      // ✅ STEP 1: Create blank interview record first
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('No active session');
      }

      // Create blank interview with minimal data
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
          resume_id: currentResumeId,
          jd_id: currentJdId,
          question_set: currentQuestionSet,
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
  };

  // ✅ Updated function to handle retake interview
  const handleRetakeInterview = async () => {
    if (!currentResumeId || !currentJdId || !currentQuestionSet) {
      alert('Please ensure resume, job description, and question set are available.');
      return;
    }

    try {
      // Get the original interview ID for retake context
      const originalInterview = interviewHistory.find(interview => 
        interview.status === 'completed' || interview.status === 'ENDED'
      );
      
      if (!originalInterview) {
        alert('No completed interview found to retake from.');
        return;
      }

      // ✅ STEP 1: Create blank interview record first
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('No active session');
      }

      // Find existing interviews to determine attempt number
      const existingInterviewsResponse = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/interviews?resume_id=${currentResumeId}&jd_id=${currentJdId}&question_set=${currentQuestionSet}`, {
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
          resume_id: currentResumeId,
          jd_id: currentJdId,
          question_set: currentQuestionSet,
          retake_from: originalInterview.id,
          attempt_number: nextAttemptNumber,
          status: 'PENDING', // ✅ PENDING status until payment is confirmed
          scheduled_at: new Date().toISOString()
        })
      });

      if (!blankInterviewResponse.ok) {
        throw new Error('Failed to create interview record');
      }

      const blankInterviewResult = await blankInterviewResponse.json();
      const blankInterviewId = blankInterviewResult.data.id;

      console.log('✅ Blank interview created:', blankInterviewId);

      // ✅ STEP 2: Create payment with interview_id in metadata
      const paymentResponse = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/create-payment`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          resume_id: currentResumeId,
          jd_id: currentJdId,
          question_set: currentQuestionSet,
          retake_from: originalInterview.id,
          interview_id: blankInterviewId // ✅ Pass the blank interview ID
        })
      });
      
      if (!paymentResponse.ok) {
        // ✅ If payment creation fails, delete the blank interview
        await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/interviews/${blankInterviewId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          }
        });
        throw new Error('Failed to create payment');
      }
      
      const paymentResult = await paymentResponse.json();
      console.log('Payment created:', paymentResult);
      
      // ✅ STEP 3: Redirect to Dodo payment page
      window.location.href = paymentResult.payment_url;
      
    } catch (error) {
      console.error('Error initiating retake:', error);
      alert(`Error: ${error.message}`);
    }
  };
  
  
  
  const pollPaymentStatus = async (transactionId, accessToken) => {
    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
      const res = await fetch(`${apiBaseUrl}/check-payment-status?transaction_id=${transactionId}`, {
        headers: { 'Authorization': `Bearer ${accessToken}` },
      });
      const data = await res.json();

      if (!res.ok || !data.success) return;

      setPaymentStatus(data.status || null);
      setSignatureOk(
        typeof data.signature_ok === 'boolean' ? data.signature_ok : null
      );

      if (Array.isArray(data.debug)) {
        setPaymentDebug(data.debug);
      }

      if (['succeeded', 'failed', 'cancelled'].includes(data.status)) {
        // stop polling
        return;
      }
      // continue polling
      setTimeout(() => pollPaymentStatus(transactionId, accessToken), 1500);
    } catch (err) {
      console.error('Status check error:', err);
      setTimeout(() => pollPaymentStatus(transactionId, accessToken), 2500);
    }
  };



  

  return (
    <>
      <Navbar />
      <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text-primary)] px-3 sm:px-4 py-6 sm:py-8 md:py-12 lg:py-16 flex justify-center">
        <div className="w-full max-w-6xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="text-center mb-8 sm:mb-10"
          >
            <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tight text-[var(--color-primary)] mb-3 sm:mb-4">
              Interview Questions & Answers
            </h1>
            <p className="text-sm sm:text-base md:text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto leading-relaxed px-2 mb-4">
              Review generated questions and sample answers for your interview preparation
            </p>
            

            {/* Question Set Display */}
            {currentQuestionSet && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.3 }}
                className="flex items-center justify-center gap-4 mt-6"
              >
                <div className="flex items-center gap-2 text-sm sm:text-base text-[var(--color-text-secondary)] bg-[var(--color-input-bg)] px-4 py-2 rounded-full border border-[var(--color-border)]">
                  <div className="w-2 h-2 bg-[var(--color-primary)] rounded-full animate-pulse"></div>
                  <span className="font-medium">Question Set {currentQuestionSet}</span>
                </div>
                <div className="flex items-center gap-2 text-xs sm:text-sm text-[var(--color-text-secondary)] bg-[var(--color-card)] px-3 py-1 rounded-full border border-[var(--color-border)]">
                  <span className="font-medium">{Object.keys(groupedQuestions).length}</span>
                  <span className="opacity-75">questions</span>
                </div>
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
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="sm:col-span-2 lg:col-span-1">
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

              <div>
                <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2 flex items-center">
                  <FiFilter className="mr-2" size={16} />
                   Answer Depth
                </label>
                 <div className="relative">
                <select
                  value={filterStrength}
                  onChange={(e) => setFilterStrength(e.target.value)}
                     className="appearance-none w-full px-3 sm:px-4 py-2 sm:py-3 pr-10 border border-[var(--color-border)] rounded-lg sm:rounded-xl bg-[var(--color-input-bg)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] transition-all duration-200 text-sm sm:text-base hover:border-[var(--color-primary)] cursor-pointer"
                   >
                     <option value="all">All Experience Levels</option>
                     <option value="beginner">Beginner</option>
                     <option value="intermediate">Intermediate</option>
                     <option value="expert">Expert</option>
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
                <FiFileText className="w-12 h-12 sm:w-16 sm:h-16 text-[var(--color-text-secondary)] mx-auto mb-4 sm:mb-6" />
                <p className="text-[var(--color-text-secondary)] text-base sm:text-lg mb-2">Error loading questions</p>
                <p className="text-[var(--color-text-secondary)] text-sm">{error}</p>
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
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: index * 0.08 }}
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
                              {questionGroup.level}
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
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.3 }}
                          className="px-4 sm:px-6 lg:px-8 pb-4 sm:pb-6 lg:pb-8 border-t border-[var(--color-border)]"
                        >
                          <div className="mt-4 sm:mt-6 space-y-4 sm:space-y-6">
                            {questionGroup.answers
                              .filter(answer => filterStrength === 'all' || answer.strength === filterStrength)
                              .map((answer, answerIndex) => (
                                <motion.div
                                  key={answerIndex}
                                  initial={{ opacity: 0, y: 20 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{ duration: 0.3, delay: answerIndex * 0.1 }}
                                  className="bg-[var(--color-input-bg)] rounded-lg sm:rounded-xl p-4 sm:p-6 border border-[var(--color-border)]"
                                >
                                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
                                    <h4 className="text-sm font-medium text-[var(--color-text-primary)] flex items-center">
                                      <FiCode className="mr-2" size={16} />
                                      Answer ({answer.strength})
                                    </h4>
                                    <span className={`px-3 sm:px-4 py-1 sm:py-2 text-xs sm:text-sm font-medium rounded-lg sm:rounded-xl border ${getStrengthColor(answer.strength)}`}>
                                      {answer.strength}
                                    </span>
                                  </div>
                                  <div className="bg-[var(--color-card)] rounded-lg sm:rounded-xl p-3 sm:p-6 border border-[var(--color-border)]">
                                    <AnswerContent answer={answer.answer} />
                                  </div>
                                </motion.div>
                              ))}
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
            {/* Show different buttons based on interview status */}
            {hasExistingInterviews ? (
              <>
                {/* Retake Interview Button */}
                <button
                  onClick={handleRetakeInterview}
                  className="inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 text-sm sm:text-base font-semibold rounded-xl sm:rounded-2xl transition-all duration-200 transform hover:scale-105 bg-gradient-to-r from-[var(--color-primary)] to-purple-600 hover:from-purple-600 hover:to-[var(--color-primary)] text-white shadow-lg hover:shadow-xl"
                >
                  <FiRefreshCw className="w-4 h-4 sm:w-5 sm:h-5" />
                  Retake Interview
                </button>
                
                {/* View Dashboard Button */}
                <button
                  onClick={() => window.location.href = '/dashboard'}
                  className="inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 text-sm sm:text-base font-semibold rounded-xl sm:rounded-2xl transition-all duration-200 transform hover:scale-105 bg-[var(--color-card)] hover:bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border border-[var(--color-border)] shadow-lg hover:shadow-xl"
                >
                  <FiEye className="w-4 h-4 sm:w-5 sm:h-5" />
                  View Dashboard
                </button>
              </>
            ) : (
              /* Schedule Interview Button - Only show when no interviews exist */
              <button
                onClick={handlePayment}
                disabled={isPaymentLoading}
                className={`inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 text-sm sm:text-base font-semibold rounded-xl sm:rounded-2xl transition-all duration-200 transform hover:scale-105 ${
                  isPaymentLoading
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-gradient-to-r from-[var(--color-primary)] to-purple-600 hover:from-purple-600 hover:to-[var(--color-primary)] text-white shadow-lg hover:shadow-xl'
                }`}
              >
                <FiCreditCard className="w-4 h-4 sm:w-5 sm:w-5" />
                {isPaymentLoading ? 'Processing...' : 'Schedule Interview'}
              </button>
            )}
          </motion.div>
        </div>
      </div>
    </>
  );
}

