import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Brain, 
  MessageSquare, 
  TrendingUp, 
  CheckCircle,
  Clock,
  Target
} from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';

function FeedbackLoading({ progress = 0, onProgressComplete }) {
  const { isDark } = useTheme();
  const [currentStep, setCurrentStep] = useState(0);

  const steps = [
    {
      icon: Brain,
      title: 'Analyzing Responses',
      description: 'Processing your interview answers and evaluating technical knowledge'
    },
    {
      icon: MessageSquare,
      title: 'Assessing Communication',
      description: 'Evaluating clarity, confidence, and communication effectiveness'
    },
    {
      icon: TrendingUp,
      title: 'Identifying Strengths',
      description: 'Highlighting your key strengths and positive attributes'
    },
    {
      icon: Target,
      title: 'Finding Opportunities',
      description: 'Identifying areas for improvement and growth'
    },
    {
      icon: CheckCircle,
      title: 'Generating Summary',
      description: 'Creating your personalized feedback report'
    }
  ];

  useEffect(() => {
    // Update current step based on progress
    const stepProgress = (progress / 100) * steps.length;
    const newStep = Math.min(Math.floor(stepProgress), steps.length - 1);
    setCurrentStep(newStep);

    // Notify parent when progress is complete
    if (progress >= 100 && onProgressComplete) {
      onProgressComplete();
    }
  }, [progress, steps.length, onProgressComplete]);

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--color-bg)' }}>
      <div className="max-w-2xl w-full mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mx-auto mb-6"
          >
            <Brain size={32} className="text-white" />
          </motion.div>
          
          <h1 
            className="text-3xl font-bold mb-3"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Generating Your Feedback
          </h1>
          <p 
            className="text-lg"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            We're analyzing your interview performance to provide personalized insights
          </p>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span 
              className="text-sm font-medium"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Progress
            </span>
            <span 
              className="text-sm font-medium"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {Math.round(progress)}%
            </span>
          </div>
          
          <div 
            className="w-full h-3 rounded-full overflow-hidden"
            style={{ backgroundColor: 'var(--color-border)' }}
          >
            <motion.div
              className="h-full rounded-full"
              style={{ backgroundColor: 'var(--color-primary)' }}
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>

        {/* Current Step */}
        <div className="mb-8">
          {steps.map((step, index) => {
            const Icon = step.icon;
            const isActive = index === currentStep;
            const isCompleted = index < currentStep;
            
            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ 
                  opacity: isActive || isCompleted ? 1 : 0.3,
                  x: 0
                }}
                transition={{ duration: 0.3 }}
                className={`flex items-center gap-4 p-4 rounded-xl mb-3 transition-all duration-300 ${
                  isActive 
                    ? 'shadow-lg scale-105' 
                    : isCompleted 
                      ? 'opacity-60' 
                      : 'opacity-30'
                }`}
                style={{ 
                  backgroundColor: isActive ? 'var(--color-card)' : 'transparent',
                  border: isActive ? '1px solid var(--color-border)' : 'none'
                }}
              >
                <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                  isCompleted 
                    ? 'bg-green-100 dark:bg-green-900/20' 
                    : isActive 
                      ? 'bg-blue-100 dark:bg-blue-900/20' 
                      : 'bg-gray-100 dark:bg-gray-800'
                }`}>
                  {isCompleted ? (
                    <CheckCircle size={20} className="text-green-500" />
                  ) : (
                    <Icon size={20} className={isActive ? 'text-blue-500' : 'text-gray-400'} />
                  )}
                </div>
                
                <div className="flex-1">
                  <h3 
                    className={`font-semibold mb-1 ${
                      isActive ? 'text-lg' : 'text-base'
                    }`}
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {step.title}
                  </h3>
                  <p 
                    className="text-sm"
                    style={{ color: 'var(--color-text-secondary)' }}
                  >
                    {step.description}
                  </p>
                </div>
                
                {isActive && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  >
                    <Clock size={16} className="text-blue-500" />
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </div>

        {/* Encouraging Message */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 1 }}
          className="text-center p-6 rounded-xl"
          style={{ backgroundColor: 'var(--color-card)' }}
        >
          {progress >= 100 ? (
            <>
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.5 }}
                className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center mx-auto mb-4"
              >
                <CheckCircle size={24} className="text-green-500" />
              </motion.div>
              <p 
                className="text-lg font-medium mb-2"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Analysis Complete! 🎉
              </p>
              <p 
                className="text-sm"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Your personalized feedback is ready. Redirecting you to the results...
              </p>
            </>
          ) : (
            <>
              <p 
                className="text-lg font-medium mb-2"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Great job completing your interview! 🎉
              </p>
              <p 
                className="text-sm"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Your feedback will be ready in just a moment. This analysis will help you improve for future interviews.
              </p>
            </>
          )}
        </motion.div>
      </div>
    </div>
  );
}

export default FeedbackLoading;
