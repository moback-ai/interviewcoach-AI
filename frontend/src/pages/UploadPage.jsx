import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import PageWavesShell from '../components/common/PageWavesShell';
import UploadBox from '../components/upload/UploadBox';
import { FiTrash2, FiLoader, FiFileText, FiCheck, FiSettings, FiX } from 'react-icons/fi';
import { useOperation } from '../contexts/OperationContext';
import { uploadFile } from '../api';
import SuccessModal from '../components/SuccessModal';
import NoticeModal from '../components/common/NoticeModal';
import { trackEvents } from '../services/mixpanel';
import { getBackendOrigin } from '../utils/apiConfig';
import { mapEmptyUploadFileError } from '../utils/uploadErrors';
import {
  filesHaveSameContent,
  SAME_RESUME_JD_FILE_MESSAGE,
} from '../utils/fileIdentity';
import { getSession } from '../lib/authClient';
import { unlockBodyScroll } from '../utils/unlockBodyScroll';
import { devLog, devWarn } from '../utils/devLog';

const JD_FETCH_ERROR_MESSAGE =
  "We couldn't fetch this job description from the link. Please paste it manually or upload the JD file.";

const JD_MANUAL_PASTE_MESSAGE =
  "We couldn't fetch the job description from this link. " +
  "Please paste it manually in the 'Paste Description' tab.";

const MAX_SELECTED_SKILLS = 10;

const SUGGESTED_SKILLS_POOL = [
  'Java', 'JavaScript', 'Python', 'React', 'Node.js', 'SQL', 'Git', 'Agile', 'REST APIs',
  'Microservices', 'AWS', 'Docker', 'Kubernetes', 'MySQL', 'MongoDB', 'TypeScript',
  '.NET Framework', 'ASP.NET MVC', 'ASP.NET Core', 'C#', 'Spring Boot',
  'Agile Testing', 'Web Development', 'Software Design', 'Troubleshooting', 'JDK',
  'Display Advertising', 'Oracle Database', 'Project Management', 'Communication',
  'Leadership', 'Problem Solving', 'Data Analysis', 'Machine Learning', 'DevOps',
];

function UploadPage() {
  const navigate = useNavigate();
  const { setIsOperationInProgress } = useOperation();

  const [profileInputMode, setProfileInputMode] = useState('resume'); // 'resume' | 'skills'
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [skillsInputValue, setSkillsInputValue] = useState('');
  const [skillsError, setSkillsError] = useState('');
  const [skillsDropdownOpen, setSkillsDropdownOpen] = useState(false);
  const skillsSearchRef = useRef(null);
  const [resume, setResume] = useState(null);
  const [jobDesc, setJobDesc] = useState(null);
  const [resumeError, setResumeError] = useState('');
  const [jobDescError, setJobDescError] = useState('');
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [parsingJobDesc, setParsingJobDesc] = useState(false);
  const [jobDescParsed, setJobDescParsed] = useState(false);
  const [jobDescInputMode, setJobDescInputMode] = useState('file'); // 'file' | 'paste' | 'link'
  const [jobUrl, setJobUrl] = useState('');
  const [jobUrlLoading, setJobUrlLoading] = useState(false);
  const [clearCounter, setClearCounter] = useState(0);
  const [successModal, setSuccessModal] = useState({ isOpen: false, title: '', message: '', details: null });
  const [noticeModal, setNoticeModal] = useState({
    isOpen: false,
    title: '',
    message: '',
    variant: 'error',
    primaryLabel: 'OK',
    secondaryLabel: undefined,
    onSecondary: undefined,
    details: undefined,
  });
  const pendingPairContinueRef = useRef(null);
  const pendingDossierRetryRef = useRef(null);
  const lastGenerateAttemptRef = useRef(null);
  const [lastCreatedIds, setLastCreatedIds] = useState({ resumeId: null, jdId: null, questionSet: null });

  // New state for question generation settings
  const [easyQuestions, setEasyQuestions] = useState(1); // ✅ Changed from 2 to 1
  const [mediumQuestions, setMediumQuestions] = useState(1); // ✅ Changed from 2 to 1
  const [hardQuestions, setHardQuestions] = useState(1); // ✅ Changed from 2 to 1
  const [codingQuestions, setCodingQuestions] = useState(0); // New coding questions slider
  const [isTechnical, setIsTechnical] = useState(false); // Add this line
  const [classifyingTechnical, setClassifyingTechnical] = useState(false); // Add loading state
  const [splitMode, setSplitMode] = useState(false);
  const [blendMode, setBlendMode] = useState(false);
  const [splitResumePercentage, setSplitResumePercentage] = useState(50);
  const [blendResumePercentage, setBlendResumePercentage] = useState(50);
  const [, setQuestionValidationError] = useState('');
  const classifyAbortRef = useRef(null);
  const classifiedFromFileRef = useRef(false);
  const GENERATE_QUESTIONS_TIMEOUT_MS = 300000;

  // Removed debug useEffect for question counts and canGenerateQuestions

  // Debounced function to classify technical role when fields change
  useEffect(() => {
    if (classifiedFromFileRef.current) {
      classifiedFromFileRef.current = false;
      return;
    }

    const trimmedTitle = jobTitle.trim();
    const trimmedDescription = jobDescription.trim();
    
    // Only classify if title has content and JD was parsed
    // If description is empty, we'll use title as description for classification
    if (!jobDescParsed || !trimmedTitle) {
      // Reset if title is empty OR if both fields are empty
      if (!trimmedTitle || (!trimmedTitle && !trimmedDescription)) {
        setIsTechnical(false);
        setCodingQuestions(0);
      }
      return;
    }

    // Prepare description - use title if description is empty
    const descriptionToUse = trimmedDescription || trimmedTitle;

    // Set a timer to debounce the API call
    const timer = setTimeout(async () => {
      if (classifyAbortRef.current) {
        classifyAbortRef.current.abort();
      }
      const controller = new AbortController();
      classifyAbortRef.current = controller;
      setClassifyingTechnical(true);
      
      try {
        const session = await getSession();
        if (!session) {
          return;
        }

        const backendUrl = getBackendOrigin();
        
        const requestPayload = {
          job_title: trimmedTitle,
          job_description: descriptionToUse
        };
        
        const response = await fetch(`${backendUrl}/api/classify-technical-role`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestPayload),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Classification failed: ${response.status}`);
        }

        const result = await response.json();
        
        if (result.success) {
          const newIsTechnical = result.is_technical || false;
          setIsTechnical(newIsTechnical);
          
          // Reset coding questions to 0 if role is not technical
          if (!newIsTechnical) {
            setCodingQuestions(0);
          }
        } else {
          devWarn('[WARNING] Classification returned unsuccessful:', result.message);
          setIsTechnical(false);
          setCodingQuestions(0); // Reset on error
        }
      } catch (error) {
        if (error?.name === 'AbortError') {
          return;
        }
        setIsTechnical(false);
        setCodingQuestions(0);
      } finally {
        if (!controller.signal.aborted) {
          setClassifyingTechnical(false);
        }
      }
    }, 1200);

    return () => {
      clearTimeout(timer);
      if (classifyAbortRef.current) {
        classifyAbortRef.current.abort();
        classifyAbortRef.current = null;
      }
    };
  }, [jobTitle, jobDescription, jobDescParsed]); // Re-run when these change

  const handleClearAll = () => {
    setProfileInputMode('resume');
    setSelectedSkills([]);
    setSkillsInputValue('');
    setSkillsError('');
    setSkillsDropdownOpen(false);
    setResume(null);
    setJobDesc(null);
    setResumeError('');
    setJobDescError('');
    setJobTitle('');
    setJobDescription('');
    setJobDescParsed(false);
    setJobDescInputMode('file');
    setJobUrl('');
    setJobUrlLoading(false);
    setIsTechnical(false);
    setCodingQuestions(0); // Add this line to reset coding questions
    setClearCounter(prev => prev + 1);
  };

  const handleResumeUpload = async (file) => {
    if (!file) {
      setResume(null);
      setResumeError('');
      return;
    }
    if (jobDesc && (await filesHaveSameContent(file, jobDesc))) {
      setResumeError(SAME_RESUME_JD_FILE_MESSAGE);
      return;
    }
    setResume(file);
    setResumeError('');
  };

  const handleJobDescUpload = async (file) => {
    if (!file) {
      setJobDesc(null);
      setJobDescError('');
      setJobDescParsed(false);
      return;
    }
    if (resume && (await filesHaveSameContent(resume, file))) {
      setJobDescError(SAME_RESUME_JD_FILE_MESSAGE);
      return;
    }
    setJobDesc(file);
    setJobDescError('');
    setJobDescParsed(false);

    // Automatically parse the job description file
    await parseJobDescriptionFile(file);
  };

  const parseJobDescriptionFile = async (file) => {
    setParsingJobDesc(true);
    setIsOperationInProgress(true); // ✅ Pause idle timeout during parsing
    
    try {
      // Create FormData for file upload
      const formData = new FormData();
      formData.append('file', file);

      // Use the uploadFile helper function with correct endpoint
      const result = await uploadFile('/parse-job-description', formData, { timeoutMs: 90000 });

      if (!result.success) {
        throw new Error(result.message || 'Failed to parse job description');
      }

      // Populate the fields with parsed data
      setJobTitle(result.data.job_title || '');
      setJobDescription(result.data.job_description || '');
      setIsTechnical(result.data.is_technical || false);
      classifiedFromFileRef.current = true;
      setJobDescParsed(true);
      
    } catch (error) {
      console.error('Error parsing job description:', error);
      const raw = mapEmptyUploadFileError(
        error instanceof Error ? error.message : String(error || '')
      );
      const userMessage = /timed out|504|gateway time-out/i.test(raw)
        ? 'Parsing took too long and the server timed out. Try a smaller PDF/DOCX, or paste the job description text in the fields below.'
        : /job description must be at least \d+ characters/i.test(raw)
          ? 'The uploaded job description is too short. Please add more detail about the role and try again.'
          : raw || 'Could not read that job description file. Try another file or paste the text below.';
      setJobDescError(userMessage);
      setJobDescParsed(false);
      setIsTechnical(false); // Reset on error
    } finally {
      setParsingJobDesc(false);
      setIsOperationInProgress(false); // ✅ Resume idle timeout after parsing
    }
  };

  const handleManualJobDescAccept = async () => {
    const trimmedTitle = jobTitle.trim();
    const trimmedDesc = jobDescription.trim();

    if (!trimmedTitle || !trimmedDesc) {
      setJobDescError('Job title and description are required.');
      return;
    }

    setParsingJobDesc(true);
    setIsOperationInProgress(true);
    setJobDescError('');

    try {
      const backendUrl = getBackendOrigin();
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const response = await fetch(`${backendUrl}/api/parse-job-description`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          job_title: trimmedTitle,
          job_description: trimmedDesc
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Failed to accept job description');
      }

      const result = await response.json();
      if (result.success && result.data) {
        setJobTitle(result.data.job_title || trimmedTitle);
        setJobDescription(result.data.job_description || trimmedDesc);
        setIsTechnical(result.data.is_technical || false);
        classifiedFromFileRef.current = true;
        setJobDescParsed(true);
      } else {
        throw new Error(result.message || 'Failed to accept job description');
      }
    } catch (error) {
      console.error('Error accepting manual job description:', error);
      const raw = error instanceof Error ? error.message : String(error || '');
      setJobDescError(raw || 'Failed to accept job description');
      setJobDescParsed(false);
      setIsTechnical(false);
    } finally {
      setParsingJobDesc(false);
      setIsOperationInProgress(false);
    }
  };

  const handleFetchJobFromUrl = async () => {
    const trimmedUrl = jobUrl.trim();
    if (!trimmedUrl) {
      setJobDescError('Please paste a job posting URL.');
      return;
    }

    setJobDescError('');
    setJobUrlLoading(true);
    setIsOperationInProgress(true);

    try {
      const backendUrl = getBackendOrigin();
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const response = await fetch(`${backendUrl}/api/extract-job-from-url`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: trimmedUrl })
      });

      if (!response.ok) {
        throw new Error(JD_FETCH_ERROR_MESSAGE);
      }

      const result = await response.json();
      if (result.success && result.data) {
        const requiresManualPaste = Boolean(result.data.requires_manual_paste);

        setJobTitle(result.data.job_title || '');
        setIsTechnical(result.data.is_technical || false);

        if (requiresManualPaste) {
          setNoticeModal({
            isOpen: true,
            title: "Can't auto-fetch job description",
            message: JD_MANUAL_PASTE_MESSAGE,
            variant: 'info',
          });
          setJobDescInputMode('paste');
          setJobDescription('');
          setJobDescParsed(false);
        } else {
          setJobDescription(result.data.job_description || '');
          classifiedFromFileRef.current = true;
          setJobDescParsed(true);
        }
      } else {
        throw new Error(JD_FETCH_ERROR_MESSAGE);
      }
    } catch (error) {
      console.error('Error fetching job description from URL:', error);
      setNoticeModal({
        isOpen: true,
        title: 'Unable to fetch job description',
        message: JD_FETCH_ERROR_MESSAGE,
        variant: 'error',
      });
      setJobDescError('');
      setJobDescParsed(false);
      setIsTechnical(false);
    } finally {
      setJobUrlLoading(false);
      setIsOperationInProgress(false);
    }
  };

  const uploadResume = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const result = await uploadFile('/upload-resume', formData);
    if (!result.success) {
      throw new Error(result.message || 'Resume upload failed');
    }
    return {
      resumeId: result.data.resume_id,
      resumeUrl: result.data.url,
    };
  };

  const saveJobDescription = async () => {
    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const backendOrigin = getBackendOrigin();
      const jdResponse = await fetch(`${backendOrigin}/api/job-descriptions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: jobTitle,
          description: jobDescription,
          technical: isTechnical
        })
      });

      if (!jdResponse.ok) {
        const errorData = await jdResponse.json();
        throw new Error(`Failed to save job description: ${errorData.message || 'Unknown error'}`);
      }

      const jdData = await jdResponse.json();
      return { jdId: jdData.data.id };
    } catch (error) {
      console.error('Error saving job description:', error);
      throw error;
    }
  };

  const createSkillsResumeRecord = async (skillsText = '') => {
    const session = await getSession();
    if (!session) {
      throw new Error('No active session');
    }

    const backendOrigin = getBackendOrigin();
    const resumeResponse = await fetch(`${backendOrigin}/api/resumes`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${session.access_token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        file_url: '',
        file_name: 'Skills-based profile',
        skills_text: skillsText,
      }),
    });

    if (!resumeResponse.ok) {
      const errorData = await resumeResponse.json().catch(() => ({}));
      throw new Error(errorData.message || 'Failed to create skills profile record');
    }

    const resumeData = await resumeResponse.json();
    return resumeData.data.id;
  };

  const checkResumeJdPair = async ({ isSkillsMode, skillsTextForApi }) => {
    const session = await getSession();
    if (!session) {
      throw new Error('No active session');
    }
    const backendOrigin = getBackendOrigin();
    const formData = new FormData();
    formData.append('job_title', jobTitle.trim());
    formData.append('job_description', jobDescription.trim());
    if (isSkillsMode) {
      formData.append('skills_text', skillsTextForApi);
    } else if (resume) {
      formData.append('file', resume);
      formData.append('file_name', resume.name || '');
    }
    const response = await fetch(`${backendOrigin}/api/check-resume-jd-pair`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
      },
      body: formData,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.success) {
      throw new Error(payload.message || 'Failed to check existing resume/JD pair');
    }
    return payload.match || {};
  };

  const validateUploadDocuments = async ({ isSkillsMode, skillsTextForApi }) => {
    const session = await getSession();
    if (!session) {
      throw new Error('No active session');
    }
    const backendOrigin = getBackendOrigin();
    const formData = new FormData();
    formData.append('job_title', jobTitle.trim());
    formData.append('job_description', jobDescription.trim());
    if (isSkillsMode) {
      formData.append('skills_text', skillsTextForApi);
    } else if (resume) {
      formData.append('file', resume);
    }
    const response = await fetch(`${backendOrigin}/api/validate-upload-documents`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
      },
      body: formData,
      signal: typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
        ? AbortSignal.timeout(90000)
        : undefined,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.success) {
      const err = new Error(payload.message || 'Document validation failed');
      err.code = payload.code || 'INVALID_DOCUMENT';
      throw err;
    }
    return payload.data || {};
  };

  const closeNoticeModal = () => {
    pendingPairContinueRef.current = null;
    pendingDossierRetryRef.current = null;
    setNoticeModal({
      isOpen: false,
      title: '',
      message: '',
      variant: 'error',
      primaryLabel: 'OK',
      secondaryLabel: undefined,
      onSecondary: undefined,
      details: undefined,
    });
  };

  const handleGenerateQuestions = async (e) => {
    e.preventDefault();

    const isSkillsMode = profileInputMode === 'skills';
    const skillsTextForApi = selectedSkills.length ? selectedSkills.join(', ') : '';

    if (isSkillsMode) {
      if (selectedSkills.length === 0) {
        setSkillsError('Skill is a required field');
        return;
      }
    } else {
      if (!resume || !jobTitle.trim() || !jobDescription.trim()) {
        setNoticeModal({
          isOpen: true,
          title: 'Missing information',
          message: 'Please upload a resume and ensure job title and description are filled.',
          variant: 'info',
        });
        return;
      }
      const MIN_RESUME_BYTES = 100;
      if (resume.size === 0 || resume.size < MIN_RESUME_BYTES) {
        setNoticeModal({
          isOpen: true,
          title: 'Resume file is empty or too small',
          message: 'The file appears to have no content. Please upload a proper resume with work experience, projects, or education.',
          variant: 'error',
        });
        return;
      }
      if (jobDesc && (await filesHaveSameContent(resume, jobDesc))) {
        setNoticeModal({
          isOpen: true,
          title: 'Same file for resume and job description',
          message: SAME_RESUME_JD_FILE_MESSAGE,
          variant: 'error',
        });
        return;
      }
    }

    if (!jobTitle.trim() || !jobDescription.trim()) {
      setNoticeModal({
        isOpen: true,
        title: 'Missing information',
        message: 'Job title and description are required.',
        variant: 'info',
      });
      return;
    }

    // Validate question counts based on mode
    const totalQuestions = easyQuestions + mediumQuestions + hardQuestions + codingQuestions;

    // Only validate when both split AND blend modes are enabled
    if (splitMode && blendMode) {
      // Both modes on - need at least 6 total questions
      if (totalQuestions < 6) {
        // ✅ CHANGE: Use conditional message based on coding slider visibility
        const errorMessage = isTechnical === true && jobTitle.trim() && jobDescription.trim()
          ? 'When both Split and Blend modes are enabled, you need at least 6 total questions, excluding coding questions.'
          : 'When both Split and Blend modes are enabled, you need at least 6 total questions.';
        setQuestionValidationError(errorMessage);
        return;
      }
    }

    // Clear any previous validation errors
    setQuestionValidationError('');

    setLoading(true);
    setIsOperationInProgress(true); // ✅ Pause idle timeout during question generation

    const runWorkflow = async ({
      reuseResumeId = null,
      reuseJdId = null,
      reuseResumeUrl = null,
      forceNew = false,
    } = {}) => {
      try {
        devLog('[DEBUG] Starting complete workflow...', isSkillsMode ? '(skills mode)' : '(resume mode)');

        let resumeId = reuseResumeId;
        let jdId = reuseJdId;
        let resumeUrl = reuseResumeUrl;
        // "Generate new set anyway" → dossier-only (pair already has questions + dossier).
        const dossierOnly = Boolean(forceNew);

        if (!forceNew && !resumeId && !jdId) {
          // 1) Resume/JD type checks (LLM + heuristic fallback)
          await validateUploadDocuments({ isSkillsMode, skillsTextForApi });

          // 2) Existing pair / question-set check
          const match = await checkResumeJdPair({ isSkillsMode, skillsTextForApi });
          if (match.questions_exist) {
            setLoading(false);
            setIsOperationInProgress(false);
            pendingPairContinueRef.current = () => {
              closeNoticeModal();
              setLoading(true);
              setIsOperationInProgress(true);
              runWorkflow({
                reuseResumeId: match.resume_id,
                reuseJdId: match.jd_id,
                reuseResumeUrl: match.resume_url || null,
                forceNew: true,
              });
            };
            const setCount = match.question_set_count || 1;
            const roleLabel = (match.job_title || jobTitle || '').trim();
            setNoticeModal({
              isOpen: true,
              title: 'You already have questions for this pair',
              message:
                setCount === 1
                  ? 'A question set is ready on your Dashboard. Jump there to practice, or create another set if you want fresh questions.'
                  : `You already have ${setCount} question sets for this resume and job description. Open the Dashboard to practice, or generate another set.`,
              variant: 'existing',
              primaryLabel: 'Go to Dashboard',
              secondaryLabel: 'Generate new set anyway',
              details: [
                ...(roleLabel ? [{ label: 'Role', value: roleLabel }] : []),
                {
                  label: 'Question sets',
                  value: String(setCount),
                },
                ...(match.latest_question_set
                  ? [{ label: 'Latest set', value: `#${match.latest_question_set}` }]
                  : []),
              ],
              onSecondary: () => {
                if (pendingPairContinueRef.current) pendingPairContinueRef.current();
              },
            });
            return;
          }

          if (match.filename_match && !match.content_match_resume && !isSkillsMode) {
            // Soft caution only — continue after user acknowledges once via console/devLog
            devWarn('[WARN] Filename already used by this user; content differs — continuing.');
          }

          if (match.resume_id && match.jd_id && match.content_match) {
            resumeId = match.resume_id;
            jdId = match.jd_id;
            resumeUrl = match.resume_url || null;
            devLog('[DEBUG] Reusing existing resume_id/jd_id from content hash match');
          } else {
            if (match.resume_id && match.content_match_resume) {
              resumeId = match.resume_id;
              resumeUrl = match.resume_url || null;
            }
            if (match.jd_id && match.content_match_jd) {
              jdId = match.jd_id;
            }
          }
        }

        if (isSkillsMode) {
          if (!resumeId) {
            devLog('[DEBUG] Step 1: Creating skills profile record...');
            resumeId = await createSkillsResumeRecord(skillsTextForApi);
          }
          if (!jdId) {
            devLog('[DEBUG] Step 2: Saving job description...');
            ({ jdId } = await saveJobDescription());
          }
          trackEvents.jobDescriptionSaved({
            job_title: jobTitle,
            job_description_length: jobDescription.length,
            resume_id: resumeId,
            jd_id: jdId,
            save_timestamp: new Date().toISOString(),
          });
        } else {
          if (!resumeId) {
            // Step 1: Upload resume (stored under resumes/{user_id}/ and saved to DB)
            devLog('[DEBUG] Step 1: Uploading resume file...');
            ({ resumeId, resumeUrl } = await uploadResume(resume));

            // Track resume upload
            trackEvents.resumeUploaded({
              file_name: resume.name,
              file_size: resume.size,
              file_type: resume.type,
              upload_timestamp: new Date().toISOString(),
            });
          }

          if (!jdId) {
            // Step 2: Save job description to database
            devLog('[DEBUG] Step 2: Saving job description...');
            ({ jdId } = await saveJobDescription());
          }

          // Track job description save
          trackEvents.jobDescriptionSaved({
            job_title: jobTitle,
            job_description_length: jobDescription.length,
            resume_id: resumeId,
            jd_id: jdId,
            save_timestamp: new Date().toISOString(),
          });
        }

        // Step 3: Generate questions using backend API
        devLog('[DEBUG] Step 3: Generating questions...', dossierOnly ? '(dossier-only reuse)' : '(first build)');
        lastGenerateAttemptRef.current = {
          resumeUrl: dossierOnly ? undefined : (resumeUrl || undefined),
          skillsText: dossierOnly ? undefined : (isSkillsMode ? skillsTextForApi : undefined),
          jobTitle,
          jobDescription,
          resumeId,
          jdId,
          isSkillsMode,
          resumeName: resume?.name,
          dossierOnly,
        };
        let questionsResult;
        try {
          questionsResult = await generateQuestionsFromBackend({
            resumeUrl: dossierOnly ? undefined : (resumeUrl || undefined),
            skillsText: dossierOnly ? undefined : (isSkillsMode ? skillsTextForApi : undefined),
            jobTitle,
            jobDescription,
            resumeId,
            jdId,
            dossierOnly,
          });
        } catch (genError) {
          const missingFile =
            !dossierOnly &&
            !isSkillsMode &&
            resume &&
            (genError?.code === 'RESUME_FILE_MISSING' ||
              /missing from storage/i.test(genError?.message || ''));
          if (!missingFile) {
            throw genError;
          }
          // Saved resume row exists in DB but the blob is gone — re-upload and retry once.
          devWarn('[WARN] Resume file missing in storage; re-uploading and retrying generation...');
          ({ resumeId, resumeUrl } = await uploadResume(resume));
          lastGenerateAttemptRef.current = {
            ...lastGenerateAttemptRef.current,
            resumeId,
            resumeUrl,
            dossierOnly: false,
          };
          questionsResult = await generateQuestionsFromBackend({
            resumeUrl,
            jobTitle,
            jobDescription,
            resumeId,
            jdId,
          });
        }
      
        if (!questionsResult.success) {
          const err = new Error(
            questionsResult.message || 'Failed to generate questions'
          );
          err.code = questionsResult.code || null;
          throw err;
        }

        // Step 4–5: Save questions and show success
        devLog('[DEBUG] Step 4: Saving questions to database...');
        await finishSuccessfulGeneration({
          resumeId,
          jdId,
          questionsResult,
          isSkillsMode,
          resumeName: resume?.name,
          jobTitle,
        });

      } catch (error) {
        console.error('Error in complete workflow:', error);
        const isDossierFail = error?.code === 'DOSSIER_BUILD_FAILED';
        if (isDossierFail && lastGenerateAttemptRef.current?.resumeId) {
          pendingDossierRetryRef.current = () => {
            void retryDossierAndQuestions();
          };
          setNoticeModal({
            isOpen: true,
            title: 'Could not build interview profile',
            message:
              error.message ||
              'Failed to build the interview dossier from your profile. No questions were generated. Please retry.',
            variant: 'error',
            primaryLabel: 'Retry',
            secondaryLabel: 'Cancel',
            onSecondary: closeNoticeModal,
          });
        } else {
          const msg = error instanceof Error ? error.message : String(error || '');
          const code = error?.code || '';
          const isDocTypeFail =
            code === 'INVALID_RESUME' ||
            code === 'INVALID_JD' ||
            code === 'INVALID_DOCUMENT' ||
            /does not look like a (resume|job)/i.test(msg);
          setNoticeModal({
            isOpen: true,
            title: isDocTypeFail ? 'Invalid document' : 'Upload failed',
            message: mapEmptyUploadFileError(msg),
            variant: 'error',
            primaryLabel: 'OK',
            secondaryLabel: undefined,
            onSecondary: undefined,
          });
        }
      } finally {
        setLoading(false);
        setIsOperationInProgress(false); // ✅ Resume idle timeout after generation
      }
    };

    await runWorkflow();
  };

  // Updated function to call backend API for question generation with new parameters
  const generateQuestionsFromBackend = async ({
    resumeUrl,
    skillsText,
    jobTitle,
    jobDescription,
    resumeId,
    jdId,
    dossierOnly = false,
  }) => {
    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const backendUrl = getBackendOrigin();

      const body = {
        job_title: jobTitle,
        job_description: jobDescription,
        resume_id: resumeId,
        jd_id: jdId,
        question_counts: {
          beginner: easyQuestions,
          medium: mediumQuestions,
          hard: hardQuestions,
          coding: codingQuestions,
        },
        split: splitMode,
        resume_pct: splitResumePercentage,
        jd_pct: 100 - splitResumePercentage,
        blend: blendMode,
        blend_pct_resume: blendResumePercentage,
        blend_pct_jd: 100 - blendResumePercentage,
      };
      // First build needs source; reuse/"new set anyway" is dossier-only.
      if (!dossierOnly) {
        if (skillsText) {
          body.skills_text = skillsText;
        } else if (resumeUrl) {
          body.resume_url = resumeUrl;
        }
      }

      const response = await fetch(`${backendUrl}/api/generate-questions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        signal: typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
          ? AbortSignal.timeout(GENERATE_QUESTIONS_TIMEOUT_MS)
          : undefined,
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('text/html')) {
          if (response.status === 504) {
            throw new Error(
              'Question generation timed out on the server. Deploy the latest backend or retry with fewer questions.'
            );
          }
          throw new Error(`Server error (${response.status}). Please try again.`);
        }
        let errorData = {};
        try {
          errorData = await response.json();
        } catch {
          errorData = {};
        }
        const err = new Error(errorData.message || `Backend API error: ${response.status}`);
        err.code = errorData.code || null;
        throw err;
      }

      return await response.json();
    } catch (error) {
      console.error('Error calling backend API:', error);
      if (error?.name === 'TimeoutError' || error?.name === 'AbortError') {
        throw new Error(
          'Question generation timed out. The server may still be busy try again with fewer questions.'
        );
      }
      throw error;
    }
  };

  const finishSuccessfulGeneration = async ({
    resumeId,
    jdId,
    questionsResult,
    isSkillsMode,
    resumeName,
    jobTitle,
  }) => {
    const questionsSaveResult = await saveQuestionsToDatabase(
      resumeId,
      jdId,
      questionsResult.data.questions
    );

    if (!questionsSaveResult.success) {
      throw new Error(`Failed to save questions: ${questionsSaveResult.message}`);
    }

    const savedQuestionSet = questionsSaveResult.data[0]?.question_set || 'unknown';

    const uniqueQuestions = questionsSaveResult.data.reduce((acc, item) => {
      if (!acc.has(item.question_text)) {
        acc.add(item.question_text);
      }
      return acc;
    }, new Set());

    trackEvents.questionsGenerated({
      resume_id: resumeId,
      jd_id: jdId,
      question_set: savedQuestionSet,
      total_questions: uniqueQuestions.size,
      job_title: jobTitle,
      generation_timestamp: new Date().toISOString()
    });

    setLastCreatedIds({
      resumeId: resumeId,
      jdId: jdId,
      questionSet: savedQuestionSet
    });

    setSuccessModal({
      isOpen: true,
      title: 'Upload & Generation Complete!',
      message: isSkillsMode
        ? `Skills profile, job description, and questions generated successfully! Question Set ${savedQuestionSet} has been created with ${uniqueQuestions.size} questions.`
        : `Resume, job description, and questions generated successfully! Question Set ${savedQuestionSet} has been created with ${uniqueQuestions.size} questions.`,
      details: [
        `Question Set: ${savedQuestionSet}`,
        `Total Questions: ${uniqueQuestions.size}`,
        isSkillsMode ? 'Profile: Skills-based' : `Resume: ${resumeName || 'resume'}`,
        `Job Title: ${jobTitle}`,
        'Status: Ready for interview preparation',
      ],
    });
  };

  const retryDossierAndQuestions = async () => {
    const attempt = lastGenerateAttemptRef.current;
    if (!attempt?.resumeId || !attempt?.jdId) {
      return;
    }
    closeNoticeModal();
    setLoading(true);
    setIsOperationInProgress(true);
    try {
      const questionsResult = await generateQuestionsFromBackend({
        resumeUrl: attempt.resumeUrl,
        skillsText: attempt.skillsText,
        jobTitle: attempt.jobTitle,
        jobDescription: attempt.jobDescription,
        resumeId: attempt.resumeId,
        jdId: attempt.jdId,
        dossierOnly: Boolean(attempt.dossierOnly),
      });
      if (!questionsResult.success) {
        const err = new Error(questionsResult.message || 'Failed to generate questions');
        err.code = questionsResult.code || null;
        throw err;
      }
      await finishSuccessfulGeneration({
        resumeId: attempt.resumeId,
        jdId: attempt.jdId,
        questionsResult,
        isSkillsMode: attempt.isSkillsMode,
        resumeName: attempt.resumeName,
        jobTitle: attempt.jobTitle,
      });
    } catch (error) {
      console.error('Error retrying dossier build:', error);
      const isDossierFail = error?.code === 'DOSSIER_BUILD_FAILED';
      if (isDossierFail) {
        pendingDossierRetryRef.current = () => {
          void retryDossierAndQuestions();
        };
        setNoticeModal({
          isOpen: true,
          title: 'Could not build interview profile',
          message:
            error.message ||
            'Failed to build the interview dossier. No questions were generated. Please retry.',
          variant: 'error',
          primaryLabel: 'Retry',
          secondaryLabel: 'Cancel',
          onSecondary: closeNoticeModal,
        });
      } else {
        setNoticeModal({
          isOpen: true,
          title: 'Upload failed',
          message: mapEmptyUploadFileError(
            error instanceof Error ? error.message : String(error || '')
          ),
          variant: 'error',
          primaryLabel: 'OK',
          secondaryLabel: undefined,
          onSecondary: undefined,
        });
      }
    } finally {
      setLoading(false);
      setIsOperationInProgress(false);
    }
  };

  // New function to save questions to database via edge function
  const saveQuestionsToDatabase = async (resumeId, jdId, questions) => {
    try {
      const session = await getSession();
      if (!session) {
        throw new Error('No active session');
      }

      const backendOrigin = getBackendOrigin();
      
      // First, get the current highest question set number for this specific resume_id + jd_id combination
      const getCurrentQuestionSetsResponse = await fetch(`${backendOrigin}/functions/v1/questions?resume_id=${resumeId}&jd_id=${jdId}`, {
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
        var nextQuestionSet = 1;
      } else {
        const maxSet = Math.max(...existingQuestionSets);
        nextQuestionSet = maxSet + 1;
      }
      
      // Now save the new questions with the incremented question set number
      const response = await fetch(`${backendOrigin}/functions/v1/questions`, {
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

  const canGenerateQuestions = useMemo(() => {
    const hasProfile = profileInputMode === 'resume'
      ? !!resume
      : selectedSkills.length > 0;
    if (!hasProfile || !jobTitle.trim() || !jobDescription.trim() || !jobDescParsed || loading || parsingJobDesc || jobUrlLoading) {
      return false;
    }

    if (splitMode && blendMode) {
      const totalQuestions = easyQuestions + mediumQuestions + hardQuestions;
      return totalQuestions >= 6;
    }

    return true;
  }, [
    profileInputMode,
    resume,
    selectedSkills,
    jobTitle,
    jobDescription,
    jobDescParsed,
    loading,
    parsingJobDesc,
    jobUrlLoading,
    splitMode,
    blendMode,
    easyQuestions,
    mediumQuestions,
    hardQuestions,
  ]);

  const getDisabledReason = () => {
    if (loading || parsingJobDesc || jobUrlLoading) {
      return null; // Don't show message during loading/parsing
    }
    
    if (profileInputMode === 'resume' && !resume) {
      return 'Please upload a resume to generate questions.';
    }

    if (profileInputMode === 'skills' && selectedSkills.length === 0) {
      return 'Please add at least one skill to generate questions.';
    }

    if (!jobDescParsed) {
      return 'Please provide a job description (upload, paste, or URL).';
    }
    
    if (!jobTitle.trim()) {
      return 'Job title is required. Please enter a job title.';
    }
    
    if (!jobDescription.trim()) {
      return 'Job description is required. Please enter a job description.';
    }
    
    if (splitMode && blendMode) {
      // ✅ CHANGE: Only count easy, medium, hard (exclude coding questions)
      const totalQuestions = easyQuestions + mediumQuestions + hardQuestions;
      if (totalQuestions < 6) {
        // ✅ CHANGE: Show different message based on whether coding slider is visible
        if (isTechnical === true && jobTitle.trim() && jobDescription.trim()) {
          return 'When both Split and Blend modes are enabled, you need at least 6 total questions, excluding coding questions.';
        } else {
          return 'When both Split and Blend modes are enabled, you need at least 6 total questions.';
        }
      }
    }
    
    return null; // Button should be enabled
  };

  // Close success modal and go to the new question set (View Questions only)
  const handleNavigateToQuestions = () => {
    setSuccessModal({ isOpen: false, title: '', message: '', details: null });
    unlockBodyScroll();

    if (lastCreatedIds.resumeId && lastCreatedIds.jdId && lastCreatedIds.questionSet) {
      navigate(`/questions?resume_id=${lastCreatedIds.resumeId}&jd_id=${lastCreatedIds.jdId}&question_set=${lastCreatedIds.questionSet}`);
    } else {
      // Fallback to dashboard if IDs are not available
      navigate('/dashboard');
    }
  };

  // Check if any critical operations are in progress
  const isCriticalOperationInProgress = loading || parsingJobDesc || jobUrlLoading;

  // Handle beforeunload event (page refresh/close) - only block during critical operations
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isCriticalOperationInProgress) {
        // Only block navigation during critical operations (parsing or generating)
        e.preventDefault();
        e.returnValue = 'You have a critical operation in progress. Are you sure you want to leave?';
        return e.returnValue;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [isCriticalOperationInProgress]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (skillsSearchRef.current && !skillsSearchRef.current.contains(e.target)) {
        setSkillsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const skillsSuggestions = SUGGESTED_SKILLS_POOL
    .filter((s) => {
      const normalized = s.toLowerCase();
      const input = skillsInputValue.trim().toLowerCase();
      const alreadySelected = selectedSkills.some(
        (existing) => existing.toLowerCase() === normalized
      );
      if (alreadySelected) return false;
      if (!input) return true;
      return normalized.startsWith(input) || normalized.includes(input);
    })
    .sort((a, b) => {
      const input = skillsInputValue.trim().toLowerCase();
      if (!input) return 0;
      const aStarts = a.toLowerCase().startsWith(input);
      const bStarts = b.toLowerCase().startsWith(input);
      if (aStarts !== bStarts) return aStarts ? -1 : 1;
      return a.localeCompare(b);
    })
    .slice(0, 8);

  const addSkill = (skill) => {
    const trimmed = (skill || '').trim();
    if (!trimmed) return;

    if (selectedSkills.length >= MAX_SELECTED_SKILLS) {
      setSkillsError(`You can add up to ${MAX_SELECTED_SKILLS} skills only.`);
      setSkillsDropdownOpen(false);
      return;
    }

    const normalizedNew = trimmed.toLowerCase();
    const isDuplicate = selectedSkills.some(
      (existing) => existing.toLowerCase() === normalizedNew
    );

    if (isDuplicate) {
      setSkillsError('Skill already present/selected.');
      setSkillsDropdownOpen(false);
      return;
    }

    setSelectedSkills((prev) => [...prev, trimmed]);
    setSkillsInputValue('');
    setSkillsError('');
    setSkillsDropdownOpen(false);
  };

  // Helper function to get mode description
  const getModeDescription = () => {
    if (splitMode && blendMode) {
      return "Hybrid Mode: Mix of split and blended questions";
    } else if (splitMode) {
      return "Split Mode: Separate questions from resume vs job description";
    } else if (blendMode) {
      return "Blend Mode: Questions that blend resume and job description content";
    } else {
      return "Standard Mode: Balanced questions from both sources";
    }
  };

  return (
    <>
      <Navbar disableNavigation={isCriticalOperationInProgress} />
      <PageWavesShell
        contentClassName="text-[var(--color-text-primary)] px-4 py-8 sm:py-12 md:py-16 flex justify-center"
      >
        <div className="w-full max-w-4xl bg-[var(--color-card)]/95 border border-[var(--color-border)] rounded-2xl sm:rounded-3xl shadow-xl sm:shadow-2xl p-6 sm:p-8 md:p-10 upload-panel-reveal backdrop-blur-sm">
          <div className="text-center mb-10">
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--color-primary)] mb-4">
            Prepare With Confidence
            </h1>
            <p className="text-base sm:text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto leading-relaxed">
            Upload your resume and job description to receive tailor-made interview questions.  
            We help you walk into interviews fully prepared and confident.
            </p>
          </div>
          
            <form onSubmit={handleGenerateQuestions} className="space-y-8">
              <div className="space-y-3">
                <label className="block text-sm font-medium text-[var(--color-text-primary)]">
                  Your profile
                </label>
                <div className="flex rounded-xl border border-[var(--color-border)] overflow-hidden bg-[var(--color-input-bg)] p-1">
                  <button
                    type="button"
                    onClick={() => {
                      setProfileInputMode('resume');
                      setSkillsError('');
                      setSelectedSkills([]);
                      setSkillsInputValue('');
                    }}
                    className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition ${
                      profileInputMode === 'resume'
                        ? 'bg-[var(--color-primary)] text-white'
                        : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
                    }`}
                  >
                    Upload Resume
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setProfileInputMode('skills');
                      setResume(null);
                      setResumeError('');
                      setSkillsError('');
                    }}
                    className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition ${
                      profileInputMode === 'skills'
                        ? 'bg-[var(--color-primary)] text-white'
                        : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
                    }`}
                  >
                    Enter Skills
                  </button>
                </div>
              </div>

              {profileInputMode === 'resume' ? (
                <UploadBox
                  key={`resume-${clearCounter}`}
                  label="Resume"
                  accept=".pdf,.doc,.docx"
                  file={resume}
                  setFile={handleResumeUpload}
                  error={resumeError}
                  setError={setResumeError}
                  dragging={dragging}
                  setDragging={setDragging}
                  type="resume"
                  disabled={loading}
                />
              ) : (
                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 sm:p-6 space-y-5">
                  <div>
                    <h3 className="text-lg font-semibold text-[var(--color-text-primary)]">Add skill</h3>
                    <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">* Indicates required</p>
                  </div>

                  {selectedSkills.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-[var(--color-text-secondary)]">
                        Selected skills ({selectedSkills.length}/{MAX_SELECTED_SKILLS})
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {selectedSkills.map((skill) => (
                          <span
                            key={skill}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-[var(--color-primary)] text-white shadow-sm"
                          >
                            {skill}
                            <button
                              type="button"
                              onClick={() => setSelectedSkills((prev) => prev.filter((s) => s !== skill))}
                              className="hover:bg-white/20 rounded-full p-0.5 transition"
                              aria-label={`Remove ${skill}`}
                            >
                              <FiX className="w-3.5 h-3.5" />
                            </button>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="space-y-2" ref={skillsSearchRef}>
                    <label className="block text-sm font-medium text-[var(--color-text-primary)]">
                      Skill <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={skillsInputValue}
                        onChange={(e) => {
                          if (selectedSkills.length >= MAX_SELECTED_SKILLS) return;
                          setSkillsInputValue(e.target.value);
                          setSkillsError('');
                          setSkillsDropdownOpen(true);
                        }}
                        onFocus={() => {
                          if (selectedSkills.length < MAX_SELECTED_SKILLS) {
                            setSkillsDropdownOpen(true);
                          }
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            const v = skillsInputValue.trim();
                            if (skillsSuggestions.length > 0) {
                              addSkill(skillsSuggestions[0]);
                            } else if (v) {
                              addSkill(v);
                            }
                          }
                          if (e.key === 'Escape') setSkillsDropdownOpen(false);
                        }}
                        placeholder={
                          selectedSkills.length >= MAX_SELECTED_SKILLS
                            ? `Maximum ${MAX_SELECTED_SKILLS} skills reached`
                            : 'Search for a skill (e.g. Java, Project Management)'
                        }
                        disabled={loading || selectedSkills.length >= MAX_SELECTED_SKILLS}
                        className={`w-full px-4 py-3 pr-10 border rounded-xl transition ${
                          skillsError
                            ? 'border-red-500 dark:border-red-500 focus:ring-2 focus:ring-red-500'
                            : 'border-[var(--color-border)] focus:ring-2 focus:ring-[var(--color-primary)]'
                        } bg-[var(--color-input-bg)] text-[var(--color-text-primary)] focus:outline-none`}
                      />
                      {skillsInputValue && (
                        <button
                          type="button"
                          onClick={() => { setSkillsInputValue(''); setSkillsDropdownOpen(true); }}
                          className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-[var(--color-border)] text-[var(--color-text-secondary)]"
                          aria-label="Clear search"
                        >
                          <FiX className="w-4 h-4" />
                        </button>
                      )}
                      {skillsDropdownOpen && selectedSkills.length < MAX_SELECTED_SKILLS && (
                        <div className="absolute z-20 left-0 right-0 mt-1 py-1 bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl shadow-lg max-h-60 overflow-auto">
                          {skillsSuggestions.length > 0 ? (
                            skillsSuggestions.map((skill) => (
                              <button
                                key={skill}
                                type="button"
                                onClick={() => addSkill(skill)}
                                className="w-full text-left px-4 py-2.5 text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-primary)]/10 transition"
                              >
                                {skill}
                              </button>
                            ))
                          ) : skillsInputValue.trim() ? (
                            <button
                              type="button"
                              onClick={() => addSkill(skillsInputValue.trim())}
                              className="w-full text-left px-4 py-2.5 text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-primary)]/10 transition"
                            >
                              Add &quot;{skillsInputValue.trim()}&quot;
                            </button>
                          ) : (
                            <p className="px-4 py-3 text-sm text-[var(--color-text-secondary)]">Type to search skills</p>
                          )}
                        </div>
                      )}
                    </div>
                    {skillsError && (
                      <p className="text-sm text-red-600 dark:text-red-400">{skillsError}</p>
                    )}
                  </div>
                </div>
              )}

            {/* Job Description Input Modes */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-[var(--color-text-primary)]">
                Job Description
              </label>
              <div className="flex rounded-xl border border-[var(--color-border)] overflow-hidden bg-[var(--color-input-bg)] p-1">
                {[
                  { mode: 'file', label: 'Upload File' },
                  { mode: 'paste', label: 'Paste Description' },
                  { mode: 'link', label: 'Job URL' },
                ].map(({ mode, label }) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => {
                      setJobDescInputMode(mode);
                      setJobDescError('');
                    }}
                    className={`flex-1 py-2.5 px-4 text-sm font-medium rounded-lg transition ${
                      jobDescInputMode === mode
                        ? 'bg-[var(--color-primary)] text-white'
                        : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
                    }`}
                    disabled={loading || parsingJobDesc || jobUrlLoading}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {jobDescInputMode === 'file' && (
                <UploadBox
                  key={`jobdesc-${clearCounter}`}
                  label="Job Description File"
                  accept=".pdf,.txt,.doc,.docx"
                  file={jobDesc}
                  setFile={handleJobDescUpload}
                  error={jobDescError}
                  setError={setJobDescError}
                  dragging={dragging}
                  setDragging={setDragging}
                  type="job"
                  otherFileExists={!!resume}
                  multiple={false}
                  parsing={parsingJobDesc}
                  disabled={loading}
                />
              )}

              {jobDescInputMode === 'paste' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
                      Job Title
                    </label>
                    <input
                      type="text"
                      value={jobTitle}
                      onChange={(e) => setJobTitle(e.target.value)}
                      placeholder="e.g., Senior Software Engineer"
                      disabled={loading || parsingJobDesc}
                      className="w-full px-4 py-3 border rounded-xl bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
                      Job Description
                    </label>
                    <textarea
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                      placeholder="Paste the full job description here..."
                      rows={6}
                      disabled={loading || parsingJobDesc}
                      className="w-full px-4 py-3 border rounded-xl bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] resize-none"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    {jobDescError && (
                      <p className="text-sm text-red-600 dark:text-red-400">
                        {jobDescError}
                      </p>
                    )}
                    <button
                      type="button"
                      onClick={handleManualJobDescAccept}
                      disabled={loading || parsingJobDesc}
                      className="ml-auto inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] text-white shadow-md hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {parsingJobDesc && (
                        <FiLoader className="w-4 h-4 animate-spin" />
                      )}
                      <span>Accept Job Description</span>
                    </button>
                  </div>
                </div>
              )}

              {jobDescInputMode === 'link' && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
                      Job Posting URL
                    </label>
                    <input
                      type="url"
                      value={jobUrl}
                      onChange={(e) => setJobUrl(e.target.value)}
                      placeholder="Paste a public job posting link (e.g., LinkedIn, company careers page)"
                      disabled={loading || jobUrlLoading}
                      className="w-full px-4 py-3 border rounded-xl bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    {jobDescError && (
                      <p className="text-sm text-red-600 dark:text-red-400">
                        {jobDescError}
                      </p>
                    )}
                    <button
                      type="button"
                      onClick={handleFetchJobFromUrl}
                      disabled={loading || jobUrlLoading}
                      className="ml-auto inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-[var(--color-primary)] text-white shadow-sm hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {jobUrlLoading && (
                        <FiLoader className="w-4 h-4 animate-spin" />
                      )}
                      <span>Fetch Job Description</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Job Title and Description Fields - Only show after parsing */}
              {jobDescParsed ? (
                  <div className="space-y-6 upload-collapse-reveal">
                    {/* Success Message */}
                    <div className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl">
                      <FiCheck className="w-5 h-5 text-green-600 dark:text-green-400" />
                      <span className="text-green-800 dark:text-green-200 font-medium">
                        Job description parsed successfully!
                      </span>
                    </div>

                    {/* Job Title Input */}
                    <div>
                      <label className={`block text-sm font-medium mb-2 ${
                        !jobTitle.trim() && jobDescParsed ? 'text-red-600 dark:text-red-400' : 'text-[var(--color-text-primary)]'
                      }`}>
                        Job Title
                      </label>
                      <input
                        type="text"
                        value={jobTitle}
                        onChange={(e) => setJobTitle(e.target.value)}
                        placeholder="e.g., Senior Software Engineer"
                        disabled={loading}
                        className={`w-full px-4 py-3 border rounded-xl transition resize-none ${
                          loading
                            ? 'bg-[var(--color-text-secondary)]/20 text-[var(--color-text-secondary)] cursor-not-allowed opacity-60 border-[var(--color-border)]'
                            : !jobTitle.trim() && jobDescParsed
                            ? 'bg-[var(--color-input-bg)] text-red-600 dark:text-red-400 border-red-500 dark:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500'
                            : 'bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]'
                        }`}
                        required
                      />
                    </div>

                    {/* Job Description Input */}
                    <div>
                      <label className={`block text-sm font-medium mb-2 ${
                        !jobDescription.trim() && jobDescParsed ? 'text-red-600 dark:text-red-400' : 'text-[var(--color-text-primary)]'
                      }`}>
                        Job Description
                        {classifyingTechnical && (
                          <span className="ml-2 text-xs text-blue-500">
                            <FiLoader className="inline w-3 h-3 animate-spin" /> Classifying...
                          </span>
                        )}
                      </label>
                      <textarea
                        value={jobDescription}
                        onChange={(e) => setJobDescription(e.target.value)}
                        placeholder="Paste the job description here or upload a file to parse the job description..."
                        rows={6}
                        disabled={loading}
                        className={`w-full px-4 py-3 border rounded-xl transition resize-none ${
                          loading
                            ? 'bg-[var(--color-text-secondary)]/20 text-[var(--color-text-secondary)] cursor-not-allowed opacity-60 border-[var(--color-border)]'
                            : !jobDescription.trim() && jobDescParsed
                            ? 'bg-[var(--color-input-bg)] text-red-600 dark:text-red-400 border-red-500 dark:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500'
                            : 'bg-[var(--color-input-bg)] text-[var(--color-text-primary)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]'
                        }`}
                        required
                      />
                    </div>

                    {/* Question Generation Settings */}
                    <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-xl p-6">
                      <div className="flex items-center gap-2 mb-4">
                        <FiSettings className="w-5 h-5 text-[var(--color-primary)]" />
                        <h3 className="text-lg font-semibold text-[var(--color-text-primary)]">
                          Question Generation Settings
                        </h3>
                      </div>

                      {/* Mode Description */}
                      <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                        <p className="text-sm text-blue-800 dark:text-blue-200 font-medium">
                          {getModeDescription()}
                        </p>
                      </div>

                      {/* Question Counts */}
                      <div className="space-y-4 mb-6">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-medium text-[var(--color-text-primary)]">
                            Question Difficulty Distribution
                          </h4>
                          <div className="text-xs text-[var(--color-text-secondary)]">
                            Total: {easyQuestions + mediumQuestions + hardQuestions + (isTechnical ? codingQuestions : 0)} questions
                          </div>
                        </div>
                        
                        <div className={`grid ${isTechnical ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4' : 'grid-cols-1 md:grid-cols-3'} gap-4`}>
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
                              disabled={loading}
                              className="w-full h-2 bg-green-200/50 dark:bg-green-700/30 rounded-lg appearance-none cursor-pointer slider-green"
                            />
                            <div className="flex justify-between text-xs text-green-600/70 dark:text-green-400/70 mt-1">
                              <span>1</span>
                              <span>5</span>
                            </div>
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
                              onChange={(e) => setMediumQuestions(parseInt(e.target.value))}
                              disabled={loading}
                              className="w-full h-2 bg-yellow-200/50 dark:bg-yellow-700/30 rounded-lg appearance-none cursor-pointer slider-yellow"
                            />
                            <div className="flex justify-between text-xs text-yellow-600/70 dark:text-yellow-400/70 mt-1">
                              <span>1</span>
                              <span>5</span>
                            </div>
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
                              onChange={(e) => setHardQuestions(parseInt(e.target.value))}
                              disabled={loading}
                              className="w-full h-2 bg-red-200/50 dark:bg-red-700/30 rounded-lg appearance-none cursor-pointer slider-red"
                            />
                            <div className="flex justify-between text-xs text-red-600/70 dark:text-red-400/70 mt-1">
                              <span>1</span>
                              <span>5</span>
                            </div>
                          </div>

                          {/* Coding Questions Slider - Only show if technical role AND fields have content */}
                          {isTechnical === true && jobTitle.trim() && jobDescription.trim() && (
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
                                disabled={loading}
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
                        {!canGenerateQuestions && splitMode && blendMode && (
                          <div className="p-3 bg-red-50/50 dark:bg-red-900/10 border border-red-200/50 dark:border-red-800/30 rounded-lg">
                            <p className="text-sm text-red-700 dark:text-red-300">
                              {/* ✅ CHANGE: Conditional message based on coding slider visibility */}
                              {isTechnical === true && jobTitle.trim() && jobDescription.trim()
                                ? 'When both Split and Blend modes are enabled, you need at least 6 total questions, excluding coding questions.'
                                : 'When both Split and Blend modes are enabled, you need at least 6 total questions.'}
                            </p>
                          </div>
                        )}

                        {/* Mode-specific validation hints */}
                        {splitMode && blendMode && (
                          <div className="p-3 bg-blue-50/50 dark:bg-blue-900/10 border border-blue-200/50 dark:border-blue-800/30 rounded-lg">
                            <p className="text-sm text-blue-700 dark:text-blue-300">
                              💡 <strong>Hybrid Mode:</strong> With both modes enabled, you need at least 6 total questions to ensure a good mix of split and blended questions.
                            </p>
                          </div>
                        )}
                      </div>

                      {/* Mode Toggles */}
                      <div className="space-y-4">
                        {/* Split Mode Section */}
                        <div>
                          <div className="flex items-center justify-between">
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
                              disabled={loading}
                              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                splitMode ? 'bg-[var(--color-primary)]' : 'bg-gray-200 dark:bg-gray-700'
                              } ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                            >
                              <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                  splitMode ? 'translate-x-6' : 'translate-x-1'
                                }`}
                              />
                            </button>
                          </div>

                          {/* Split Mode Slider */}
                          {splitMode ? (
                              <div className="mt-4 upload-panel-reveal">
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
                                      disabled={loading}
                                      className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer slider"
                                    />
                                    <div className="flex justify-between text-sm font-medium text-[var(--color-text-primary)]">
                                      <span>{splitResumePercentage}%</span>
                                      <span>{100 - splitResumePercentage}%</span>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            ) : null}
                        </div>

                        {/* Blend Mode Section */}
                        <div>
                          <div className="flex items-center justify-between">
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
                              disabled={loading}
                              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                blendMode ? 'bg-[var(--color-primary)]' : 'bg-gray-200 dark:bg-gray-700'
                              } ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                            >
                              <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                  blendMode ? 'translate-x-6' : 'translate-x-1'
                                }`}
                              />
                            </button>
                          </div>

                          {/* Blend Mode Slider */}
                          {blendMode ? (
                              <div className="mt-4 upload-panel-reveal">
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
                                      disabled={loading}
                                      className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer slider"
                                    />
                                    <div className="flex justify-between text-sm font-medium text-[var(--color-text-primary)]">
                                      <span>{blendResumePercentage}%</span>
                                      <span>{100 - blendResumePercentage}%</span>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            ) : null}
                        </div>
                      </div>

                    </div>
                  </div>
                ) : null}

            {(resume || jobDesc) && (
              <div className="flex justify-end">
                                <button
                type="button"
                onClick={handleClearAll}
                disabled={parsingJobDesc || loading}
                className={`flex items-center gap-2 py-2 px-4 text-base border rounded-xl transition ${
                  parsingJobDesc || loading
                    ? 'text-gray-400 border-gray-300 dark:text-gray-500 dark:border-gray-600 cursor-not-allowed opacity-50'
                    : 'text-[var(--color-error)] border-[var(--color-error)] hover:bg-[var(--color-error-bg)]'
                }`}
              >
                <FiTrash2 className="w-5 h-5" />
                {parsingJobDesc ? 'Parsing...' : loading ? 'Generation in Progress...' : 'Clear All Files'}
                </button>
              </div>
            )}
              
              {/* Remove the disabled reason message box - using red field borders instead */}
              
                <button
                type="submit"
                disabled={!canGenerateQuestions}
                title={!canGenerateQuestions ? getDisabledReason() : ''}
                className="w-full py-3 text-base sm:text-lg font-semibold bg-[var(--color-primary)] text-white rounded-xl transition hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <FiLoader className="w-5 h-5 animate-spin" />
                    Generating Questions...
                  </>
                ) : (
                  'Generate Interview Questions'
                )}
                </button>
          </form>
        </div>
      </PageWavesShell>

      {/* Success Modal */}
      <SuccessModal
        isOpen={successModal.isOpen}
        onClose={() => {
          unlockBodyScroll();
          setSuccessModal({ isOpen: false, title: '', message: '', details: null });
        }}
        title={successModal.title}
        message={successModal.message}
        details={successModal.details}
        customAction={{
          label: 'View Questions',
          onClick: handleNavigateToQuestions
        }}
      />
      <NoticeModal
        isOpen={noticeModal.isOpen}
        onClose={closeNoticeModal}
        onPrimary={() => {
          if (noticeModal.primaryLabel === 'Go to Dashboard') {
            closeNoticeModal();
            navigate('/dashboard');
            return;
          }
          if (noticeModal.primaryLabel === 'Retry' && pendingDossierRetryRef.current) {
            pendingDossierRetryRef.current();
            return;
          }
          closeNoticeModal();
        }}
        title={noticeModal.title}
        message={noticeModal.message}
        variant={noticeModal.variant}
        primaryLabel={noticeModal.primaryLabel || 'OK'}
        secondaryLabel={noticeModal.secondaryLabel}
        onSecondary={noticeModal.onSecondary}
        details={noticeModal.details}
      />
    </>
  );
}

export default UploadPage;
