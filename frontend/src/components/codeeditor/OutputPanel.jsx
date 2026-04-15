import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ClockIcon,
  CpuChipIcon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline';

const OutputPanel = ({
  output = '',
  errors = '',
  testResults = null,
  executionTime = 0,
  isRunning = false
}) => {
  const [activeTab, setActiveTab] = useState('output');
  const [isCollapsed, setIsCollapsed] = useState(false);

  const tabs = [
    { id: 'output', label: 'Output', icon: InformationCircleIcon },
    { id: 'errors', label: 'Errors', icon: ExclamationTriangleIcon, count: errors ? 1 : 0 },
    { id: 'tests', label: 'Tests', icon: CheckCircleIcon, count: testResults ? testResults.total : 0 }
  ];

  const formatOutput = (text) => {
    if (!text) return '';
    return text.split('\n').map((line, index) => (
      <div key={index} className="font-mono text-sm">
        {line}
      </div>
    ));
  };

  const formatErrors = (errorText) => {
    if (!errorText) return null;

    // Try to parse JSON error format
    try {
      const errorObj = JSON.parse(errorText);
      return (
        <div className="space-y-2">
          <div className="text-red-400 font-semibold">{errorObj.type || 'Error'}</div>
          <div className="text-red-300">{errorObj.message}</div>
          {errorObj.stack && (
            <pre className="text-xs text-red-200 bg-red-900/20 p-2 rounded overflow-x-auto">
              {errorObj.stack}
            </pre>
          )}
        </div>
      );
    } catch {
      // Fallback to plain text
      return (
        <div className="text-red-300 font-mono text-sm whitespace-pre-wrap">
          {errorText}
        </div>
      );
    }
  };

  const renderTestResults = () => {
    if (!testResults) return null;

    const { total, passed, failed, tests } = testResults;

    return (
      <div className="space-y-4">
        {/* Test Summary */}
        <div className="flex items-center justify-between p-3 bg-[var(--color-card)] rounded-lg border border-[var(--color-border)]">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <CheckCircleIcon className="w-5 h-5 text-green-500" />
              <span className="text-sm font-medium text-[var(--color-text-primary)]">
                {passed} passed
              </span>
            </div>
            {failed > 0 && (
              <div className="flex items-center space-x-2">
                <XCircleIcon className="w-5 h-5 text-red-500" />
                <span className="text-sm font-medium text-[var(--color-text-primary)]">
                  {failed} failed
                </span>
              </div>
            )}
          </div>
          <div className="text-sm text-[var(--color-text-secondary)]">
            {total} total
          </div>
        </div>

        {/* Individual Test Results */}
        {tests && tests.length > 0 && (
          <div className="space-y-2">
            {tests.map((test, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className={`p-3 rounded-lg border ${
                  test.status === 'passed'
                    ? 'bg-green-900/20 border-green-500/30'
                    : 'bg-red-900/20 border-red-500/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {test.status === 'passed' ? (
                      <CheckCircleIcon className="w-4 h-4 text-green-500" />
                    ) : (
                      <XCircleIcon className="w-4 h-4 text-red-500" />
                    )}
                    <span className="text-sm font-medium text-[var(--color-text-primary)]">
                      {test.name}
                    </span>
                  </div>
                  {test.duration && (
                    <span className="text-xs text-[var(--color-text-secondary)]">
                      {test.duration}ms
                    </span>
                  )}
                </div>
                {test.message && (
                  <div className="mt-2 text-sm text-[var(--color-text-secondary)]">
                    {test.message}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const hasContent = output || errors || testResults;

  if (!hasContent && !isRunning) {
    return (
      <div className="h-full flex items-center justify-center bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
        <div className="text-center">
          <InformationCircleIcon className="w-12 h-12 text-[var(--color-text-secondary)] mx-auto mb-3" />
          <p className="text-[var(--color-text-secondary)]">No output yet. Run your code to see results.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`h-full flex flex-col bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg overflow-hidden transition-all duration-300 ${
      isCollapsed ? 'max-h-12' : 'max-h-full'
    }`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3 bg-[var(--color-card)] border-b border-[var(--color-border)] space-y-3 sm:space-y-0">
        <div className="flex items-center space-x-2 sm:space-x-4">
          <div className="flex space-x-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-1 sm:space-x-2 px-2 sm:px-3 py-1.5 text-xs sm:text-sm font-medium rounded-md transition-colors ${
                    activeTab === tab.id
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg)]'
                  }`}
                >
                  <Icon className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                  {tab.count > 0 && (
                    <span className="px-1 sm:px-1.5 py-0.5 text-xs bg-white/20 rounded-full">
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center space-x-2 sm:space-x-3 w-full sm:w-auto">
          {/* Execution Time */}
          {executionTime > 0 && (
            <div className="flex items-center space-x-1 text-xs text-[var(--color-text-secondary)]">
              <CpuChipIcon className="w-3 h-3 sm:w-4 sm:h-4" />
              <span>{executionTime}ms</span>
            </div>
          )}

          {/* Running Indicator */}
          {isRunning && (
            <div className="flex items-center space-x-1 text-xs text-blue-500">
              <ClockIcon className="w-3 h-3 sm:w-4 sm:h-4 animate-spin" />
              <span className="hidden sm:inline">Running...</span>
            </div>
          )}

          {/* Collapse Toggle */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
          >
            {isCollapsed ? (
              <EyeIcon className="w-4 h-4" />
            ) : (
              <EyeSlashIcon className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="flex-1 overflow-auto"
          >
            <div className="p-4 h-full">
              {activeTab === 'output' && (
                <div className="space-y-2">
                  {output ? (
                    <div className="font-mono text-sm text-[var(--color-text-primary)] whitespace-pre-wrap">
                      {formatOutput(output)}
                    </div>
                  ) : (
                    <div className="text-center text-[var(--color-text-secondary)] py-8">
                      No output yet
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'errors' && (
                <div className="space-y-2">
                  {errors ? (
                    <div className="text-red-300">
                      {formatErrors(errors)}
                    </div>
                  ) : (
                    <div className="text-center text-[var(--color-text-secondary)] py-8">
                      No errors
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'tests' && (
                <div className="space-y-2">
                  {testResults ? (
                    renderTestResults()
                  ) : (
                    <div className="text-center text-[var(--color-text-secondary)] py-8">
                      No test results yet
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default OutputPanel;