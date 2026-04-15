import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import CodeEditor from '../codeeditor/CodeEditor';
import OutputPanel from '../codeeditor/OutputPanel';
import { apiPost } from '../../api';

const CodeEditorPopup = ({ isOpen, onClose, initialLanguage = 'javascript', questionText, handleEditorSave, maintainCodeAndLang, initialEditorCode }) => {
  const [code, setCode] = useState('');
  const [codeToSave, setCodeToSave] = useState('');
  const [language, setLanguage] = useState(initialLanguage);
  const [isRunning, setIsRunning] = useState(false);
  const [output, setOutput] = useState('');
  const [errors, setErrors] = useState('');
  const [testResults, setTestResults] = useState(null);
  const [executionTime, setExecutionTime] = useState(0);
  const [isTestMode, setIsTestMode] = useState(false);

  // Reset code when popup opens or initialEditorCode changes


  useEffect(() => {
    if (isOpen) {
      setCode(initialEditorCode || '');
      setOutput('');
      setErrors('');
      setTestResults(null);
      setExecutionTime(0);
      setIsTestMode(false);
    }
  }, [isOpen, initialEditorCode]);

  const handleCodeChange = (newCode) => {
    if (newCode !== code) {
      setCode(newCode);
      if (output || errors || testResults) {
        setOutput('');
        setErrors('');
        setTestResults(null);
        setExecutionTime(0);
      }
    }
  };

  const handleRun = async (codeToRun, languageToRun) => {
    if (!codeToRun.trim()) {
      setErrors('Please enter some code to run');
      return;
    }

    setIsRunning(true);
    setErrors('');
    setOutput('');
    setTestResults(null);
    setExecutionTime(0);
    setIsTestMode(false);

    try {
      const startTime = Date.now();
      const response = await apiPost('/api/execute', {
        code: codeToRun,
        language: languageToRun
      });

      const endTime = Date.now();
      setExecutionTime(endTime - startTime);

      if (response.success) {
        setOutput(response.data.output || '');
        if (response.data.error) {
          setErrors(response.data.error);
        }
      } else {
        setErrors(response.message || 'Execution failed');
      }
    } catch (error) {
      setErrors(`Network error: ${error.message}`);
    } finally {
      setIsRunning(false);
    }
  };


  const handlePopupSave = async (code) => {
      // ✅ Validate code is not empty
      if (!code || !code.trim()) {
        setErrors('Please enter some code before submitting.');
        return;
      }
      
      // ✅ Validate code is not just whitespace or comments
      const codeWithoutComments = code
        .replace(/\/\/.*$/gm, '') // Remove single-line comments
        .replace(/\/\*[\s\S]*?\*\//g, '') // Remove multi-line comments
        .trim();
      
      if (!codeWithoutComments) {
        setErrors('Please enter actual code, not just comments.');
        return;
      }
      
      // Clear any previous errors
      setErrors('');
      
      // ✅ Call the submit handler (changed comment from "save handler")
      handleEditorSave(code.trim());
      
      // Reset state
      setCode('');
      setOutput('');
      setErrors('');
      setTestResults(null);
      setExecutionTime(0);
      setIsTestMode(false);
      onClose();
  };

  const handleTest = async (codeToTest, languageToTest) => {
    if (!codeToTest.trim()) {
      setErrors('Please enter some code to test');
      return;
    }

    setIsRunning(true);
    setErrors('');
    setOutput('');
    setTestResults(null);
    setExecutionTime(0);
    setIsTestMode(true);

    try {
      const startTime = Date.now();
      const response = await apiPost('/api/execute', {
        code: codeToTest,
        language: languageToTest,
        test: true
      });

      const endTime = Date.now();
      setExecutionTime(endTime - startTime);

      if (response.success) {
        setOutput(response.data.output || '');
        setTestResults(response.data.testResults || null);
        if (response.data.error) {
          setErrors(response.data.error);
        }
      } else {
        setErrors(response.message || 'Test execution failed');
      }
    } catch (error) {
      setErrors(`Network error: ${error.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleClose = () => {
      maintainCodeAndLang(code, language);
      setOutput('');
      setErrors('');
      setTestResults(null);
      setExecutionTime(0);
      setIsTestMode(false);
      onClose();
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={handleClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-7xl h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Code Editor
              </h2>
              {questionText && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {questionText}
                </p>
              )}
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Enter some code and hit "Submit"
                </p>
            </div>
            <button
              onClick={handleClose}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
            {/* Code Editor */}
            <div className="flex-1 min-h-0">
              <CodeEditor
                initialCode={initialEditorCode}
                language={language}
                onCodeChange={handleCodeChange}
                onRun={handleRun}
                onTest={handleTest}
                onSave={handlePopupSave}
                saveLang = {setLanguage}
                isRunning={isRunning}
                output={output}
                errors={errors}
                testResults={testResults}
                executionTime={executionTime}
              />
            </div>

            {/* Output Panel */}
            <div className="w-full lg:w-96 border-l border-gray-200 dark:border-gray-700">
              <OutputPanel
                output={output}
                errors={errors}
                testResults={testResults}
                executionTime={executionTime}
                isRunning={isRunning}
              />
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default CodeEditorPopup;