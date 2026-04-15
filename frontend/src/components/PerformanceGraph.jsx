import React, { useMemo, useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FiTrendingUp, FiTrendingDown, FiChevronDown, FiChevronUp, FiInfo, FiAlertCircle, FiCheckCircle, FiTarget, FiHelpCircle } from 'react-icons/fi';
import { supabase } from '../supabaseClient';

const PerformanceGraph = ({ resumeJobPairings }) => {
  // State for collapsible section
  const [isExpanded, setIsExpanded] = useState(false);
  // State for overall evaluation
  const [overallEvaluation, setOverallEvaluation] = useState(null);
  const [loadingEvaluation, setLoadingEvaluation] = useState(false);
  // State for tooltips
  const [showHelpTooltip, setShowHelpTooltip] = useState(null);

  // Fetch overall evaluation data
  useEffect(() => {
    const fetchOverallEvaluation = async () => {
      try {
        setLoadingEvaluation(true);
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const { data, error } = await supabase
          .from('overall_evaluation')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(1)
          .single();

        if (error && error.code !== 'PGRST116') { // PGRST116 = no rows returned
          console.error('Error fetching overall evaluation:', error);
        } else if (data) {
          setOverallEvaluation(data);
        }
      } catch (error) {
        console.error('Error fetching overall evaluation:', error);
      } finally {
        setLoadingEvaluation(false);
      }
    };

    // Only fetch if we have 2+ interviews
    if (resumeJobPairings.length > 0) {
      const totalInterviews = resumeJobPairings.reduce((count, pairing) => {
        return count + pairing.questionSets.reduce((qCount, qSet) => {
          return qCount + qSet.interviews.filter(i => 
            i.metrics && (i.status === 'completed' || i.status === 'ENDED')
          ).length;
        }, 0);
      }, 0);

      if (totalInterviews >= 2) {
        fetchOverallEvaluation();
      }
    }
  }, [resumeJobPairings]);

  // Extract all interviews with metrics in chronological order
  const chartData = useMemo(() => {
    const allInterviews = [];
    
    // Collect all interviews from all pairings
    resumeJobPairings.forEach(pairing => {
      pairing.questionSets.forEach(questionSet => {
        questionSet.interviews.forEach(interview => {
          if (interview.metrics && (interview.status === 'completed' || interview.status === 'ENDED')) {
            allInterviews.push({
              interviewId: interview.id,
              attemptNumber: interview.attempt_number,
              scheduledAt: interview.scheduled_at,
              pairingId: pairing.id,
              resumeName: pairing.resumeName,
              jobTitle: pairing.jobTitle,
              questionSet: questionSet.questionSetNumber,
              ...interview.metrics
            });
          }
        });
      });
    });
    
    // Sort by scheduled_at (chronological order)
    allInterviews.sort((a, b) => new Date(a.scheduledAt) - new Date(b.scheduledAt));
    
    // Format for chart - create interview labels
    return allInterviews.map((interview, index) => ({
      interviewNumber: index + 1,
      interviewLabel: `#${index + 1}`,
      date: new Date(interview.scheduledAt).toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
      }),
      knowledge_depth: interview.knowledge_depth || 0,
      communication_clarity: interview.communication_clarity || 0,
      confidence_tone: interview.confidence_tone || 0,
      reasoning_ability: interview.reasoning_ability || 0,
      relevance_to_question: interview.relevance_to_question || 0,
      motivation_indicator: interview.motivation_indicator || 0,
    }));
  }, [resumeJobPairings]);

  // Calculate trend for each metric
  const calculateTrend = (metricKey) => {
    if (chartData.length < 2) return null;
    const first = chartData[0][metricKey];
    const last = chartData[chartData.length - 1][metricKey];
    return last - first;
  };

  // Metric configuration with detailed descriptions
  const metricsConfig = [
    { 
      key: 'knowledge_depth', 
      label: 'Knowledge Depth', 
      color: '#3b82f6',
      description: 'Depth of technical knowledge demonstrated',
      detailedDescription: 'Measures how well you demonstrate deep understanding of technical concepts, use specific examples, and show expertise in your field. Higher scores indicate more comprehensive and detailed answers.'
    },
    { 
      key: 'communication_clarity', 
      label: 'Communication Clarity', 
      color: '#10b981',
      description: 'Clarity and effectiveness of communication',
      detailedDescription: 'Assesses how clearly and effectively you communicate your ideas. Includes structure, articulation, and the ability to explain complex concepts in an understandable way.'
    },
    { 
      key: 'confidence_tone', 
      label: 'Confidence Tone', 
      color: '#f59e0b',
      description: 'Level of confidence in responses',
      detailedDescription: 'Evaluates the confidence and assertiveness in your delivery. Higher scores reflect a confident, professional tone without being overconfident or arrogant.'
    },
    { 
      key: 'reasoning_ability', 
      label: 'Reasoning Ability', 
      color: '#8b5cf6',
      description: 'Quality of logical reasoning',
      detailedDescription: 'Measures your ability to think logically, solve problems systematically, and provide well-reasoned answers. Includes analytical thinking and structured problem-solving approaches.'
    },
    { 
      key: 'relevance_to_question', 
      label: 'Relevance to Question', 
      color: '#ec4899',
      description: 'How relevant answers are to questions',
      detailedDescription: 'Evaluates how directly and accurately your answers address the questions asked. Higher scores mean you stay on topic and provide relevant information without going off on tangents.'
    },
    { 
      key: 'motivation_indicator', 
      label: 'Motivation Indicator', 
      color: '#06b6d4',
      description: 'Demonstrated motivation and enthusiasm',
      detailedDescription: 'Assesses the level of enthusiasm, passion, and motivation you demonstrate during the interview. Shows genuine interest in the role and company.'
    },
  ];

  // Tooltip component for help text
  const HelpTooltip = ({ text, id }) => {
    if (showHelpTooltip !== id) return null;
    
    // Determine position based on tooltip ID
    // Key Metrics tooltips should appear to the right of the icon to avoid going out of bounds
    const isKeyMetric = ['mean-score', 'regression-trend', 'best-metric'].includes(id);
    
    return (
      <div 
        className={`absolute z-50 bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg shadow-xl text-xs text-[var(--color-text-primary)] ${
          isKeyMetric 
            ? 'left-full ml-2 top-0' 
            : 'mt-1 left-0 sm:left-auto sm:right-0'
        }`}
        style={{
          maxWidth: '260px',
          minWidth: '180px',
          padding: '10px 12px',
          whiteSpace: 'normal',
          display: 'block',
          lineHeight: '1.4',
          wordBreak: 'break-word',
          overflowWrap: 'break-word',
          textAlign: 'left',
          width: 'auto'
        }}
      >
        {text}
        <div 
          className={`absolute w-2 h-2 bg-[var(--color-card)] border-l border-t border-[var(--color-border)] transform rotate-45 ${
            isKeyMetric 
              ? 'left-0 top-3 -ml-1' 
              : '-top-1 left-4'
          }`}
        ></div>
      </div>
    );
  };

  // Individual metric graph component
  const MetricGraph = ({ metric, data }) => {
    const trend = calculateTrend(metric.key);
    const currentValue = data.length > 0 ? data[data.length - 1][metric.key] : 0;
    const avgValue = data.length > 0 
      ? (data.reduce((sum, d) => sum + d[metric.key], 0) / data.length).toFixed(2)
      : 0;

  return (
      <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] p-3 sm:p-4 lg:p-5 shadow-md hover:shadow-lg transition-shadow relative">
        {/* Header */}
        <div className="mb-3 sm:mb-4">
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm sm:text-base font-semibold text-[var(--color-text-primary)] truncate">
                  {metric.label}
          </h3>
                <div className="relative">
            <button
                    onMouseEnter={() => setShowHelpTooltip(`metric-${metric.key}`)}
                    onMouseLeave={() => setShowHelpTooltip(null)}
                    className="text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors"
            >
                    <FiHelpCircle size={14} />
            </button>
                  <HelpTooltip 
                    id={`metric-${metric.key}`}
                    text={metric.detailedDescription}
                  />
          </div>
        </div>
              <p className="text-xs text-[var(--color-text-secondary)] mt-0.5 hidden sm:block">
                {metric.description}
              </p>
            </div>
                  <div
              className="w-3 h-3 sm:w-4 sm:h-4 rounded-sm flex-shrink-0 ml-2"
                    style={{ backgroundColor: metric.color }}
                  />
          </div>
          
          {/* Stats Row */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs sm:text-sm">
            <div className="flex items-center gap-1">
              <span className="text-[var(--color-text-secondary)]">Current:</span>
              <span className="font-semibold text-[var(--color-text-primary)]">
                {currentValue.toFixed(1)}/10
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[var(--color-text-secondary)]">Avg:</span>
              <span className="font-medium text-[var(--color-text-primary)]">
                {avgValue}/10
                  </span>
                </div>
            {trend !== null && (
              <div className="flex items-center gap-1">
                {trend >= 0 ? (
                  <FiTrendingUp className="text-green-500" size={14} />
                ) : (
                  <FiTrendingDown className="text-red-500" size={14} />
                )}
                <span className={`font-medium ${trend >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {trend >= 0 ? '+' : ''}{trend.toFixed(2)}
                  </span>
              </div>
            )}
        </div>
      </div>
      
        {/* Chart */}
        <ResponsiveContainer width="100%" height={200}>
          <LineChart 
            data={data} 
            margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
          >
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="var(--color-border)" 
              opacity={0.3}
            />
          <XAxis 
            dataKey="interviewLabel" 
            stroke="var(--color-text-secondary)"
              tick={{ fill: 'var(--color-text-secondary)', fontSize: 10 }}
              interval="preserveStartEnd"
          />
          <YAxis 
            domain={[0, 10]}
            stroke="var(--color-text-secondary)"
              tick={{ fill: 'var(--color-text-secondary)', fontSize: 10 }}
              width={30}
            label={{ 
                value: 'Score', 
              angle: -90, 
              position: 'insideLeft',
                fill: 'var(--color-text-secondary)',
                fontSize: 10
            }}
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: 'var(--color-card)', 
              border: '1px solid var(--color-border)',
                borderRadius: '6px',
                padding: '8px',
                fontSize: '12px'
            }}
              formatter={(value) => [value.toFixed(2) + '/10', metric.label]}
              labelFormatter={(label) => `Interview ${label}`}
          />
            <Line 
              type="monotone" 
              dataKey={metric.key} 
              stroke={metric.color} 
              strokeWidth={2.5}
              dot={{ r: 3, fill: metric.color }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  };

  // Show helpful message if less than 2 interviews (need at least 2 for trends)
  if (chartData.length < 2) {
    const interviewCount = chartData.length;
    const progressPercentage = (interviewCount / 2) * 100;
    
    return (
      <div className="w-full bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] shadow-lg overflow-hidden">
        <div className="p-6 sm:p-8">
          <div className="max-w-md mx-auto">
            {/* Icon */}
            <div className="mb-4 flex justify-center">
              <div className="relative">
                <FiTarget className="text-[var(--color-primary)]" size={40} />
                {interviewCount > 0 && (
                  <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-[var(--color-card)] animate-pulse"></div>
                )}
              </div>
            </div>

            {/* Title with question mark tooltip */}
            <div className="flex items-center justify-center gap-2 mb-2">
              <h3 className="text-lg sm:text-xl font-bold text-[var(--color-text-primary)]">
                Performance Trends Unlocking Soon
              </h3>
              <div className="relative">
                <button
                  onMouseEnter={() => setShowHelpTooltip('unlock-explanation')}
                  onMouseLeave={() => setShowHelpTooltip(null)}
                  className="text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors"
                >
                  <FiHelpCircle size={18} />
                </button>
                <HelpTooltip 
                  id="unlock-explanation"
                  text="Performance trends require comparing multiple interviews to identify patterns, improvements, and areas for growth over time."
                />
              </div>
            </div>

            {/* Subtitle */}
            <p className="text-sm text-[var(--color-text-secondary)] mb-6 text-center">
              {interviewCount === 0 
                ? "Complete 2 interviews to view your personalized insights."
                : `You've completed ${interviewCount} of 2 interviews.`
              }
            </p>

            {/* Progress Bar */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-[var(--color-text-secondary)]">
                  Progress
                </span>
                <span className="text-xs font-semibold text-[var(--color-primary)]">
                  {interviewCount}/2
                </span>
              </div>
              <div className="w-full h-2.5 bg-[var(--color-input-bg)] rounded-full overflow-hidden border border-[var(--color-border)]">
                <div 
                  className="h-full bg-gradient-to-r from-[var(--color-primary)] to-blue-500 rounded-full transition-all duration-500 ease-out relative overflow-hidden"
                  style={{ width: `${progressPercentage}%` }}
                >
                  {progressPercentage > 0 && (
                    <div className="absolute inset-0 bg-white/20 animate-shimmer"></div>
                  )}
                </div>
              </div>
              <div className="text-center mt-2">
                <span className="text-xs font-semibold text-[var(--color-text-primary)]">
                  {progressPercentage.toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Extract overall evaluation data
  const analysis = overallEvaluation?.analysis_data || {};
  const fullAnalysis = analysis.full_analysis || {};
  const numericResults = fullAnalysis.numeric_results || {};
  const llmExplanations = fullAnalysis.llm_explanations || {};

  // Get confidence level badge color
  const getConfidenceColor = (level) => {
    switch (level?.toLowerCase()) {
      case 'high':
        return 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800';
      case 'low':
        return 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200 dark:bg-gray-900/20 dark:text-gray-400 dark:border-gray-800';
    }
  };

  // Metric explanation component
  const MetricExplanation = ({ label, value, description, tooltip }) => (
    <div className="bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)] relative">
      <div className="flex items-start justify-between mb-1">
        <div className="text-xs text-[var(--color-text-secondary)] flex items-center gap-1">
          {label}
          {tooltip && (
            <div className="relative">
              <button
                onMouseEnter={() => setShowHelpTooltip(tooltip)}
                onMouseLeave={() => setShowHelpTooltip(null)}
                className="text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors"
              >
                <FiHelpCircle size={12} />
              </button>
              <HelpTooltip id={tooltip} text={description} />
            </div>
          )}
        </div>
      </div>
      {value}
    </div>
  );

  return (
    <div className="w-full bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] shadow-lg overflow-hidden">
      {/* Collapsible Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 sm:p-6 text-left hover:bg-[var(--color-input-bg)] transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 rounded-t-xl"
      >
        <div className="flex-1">
          <h2 className="text-lg sm:text-xl font-bold text-[var(--color-text-primary)] mb-1">
            Performance Trends
          </h2>
          <p className="text-xs sm:text-sm text-[var(--color-text-secondary)]">
            Individual metric performance over {chartData.length} interview{chartData.length !== 1 ? 's' : ''}
            {overallEvaluation && (
              <span className="ml-2">
                • Analysis available
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-4">
          {isExpanded && (
            <span className="text-xs text-[var(--color-text-secondary)] hidden sm:inline">
              Click to collapse
            </span>
          )}
          {isExpanded ? (
            <FiChevronUp className="text-[var(--color-text-secondary)]" size={24} />
          ) : (
            <FiChevronDown className="text-[var(--color-text-secondary)]" size={24} />
          )}
        </div>
      </button>

      {/* Collapsible Content */}
      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isExpanded ? 'max-h-[10000px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="p-4 sm:p-6 pt-0">
          {/* Info Section - Scoring System Explanation */}
          <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/10 rounded-lg border border-blue-200 dark:border-blue-800">
            <div className="flex items-start gap-2">
              <FiInfo className="text-blue-500 mt-0.5 flex-shrink-0" size={18} />
              <div className="flex-1">
                <h4 className="text-sm font-semibold text-[var(--color-text-primary)] mb-2">
                  Understanding Your Scores
                </h4>
                <ul className="text-xs sm:text-sm text-[var(--color-text-secondary)] space-y-1">
                  <li>• <strong>Scoring Scale:</strong> All metrics are scored from 0-10, where 10 represents excellent performance</li>
                  <li>• <strong>Current:</strong> Your score in the most recent interview</li>
                  <li>• <strong>Avg:</strong> Average score across all your interviews</li>
                  <li>• <strong>Trend (↑/↓):</strong> Change from first to last interview (positive = improving, negative = declining)</li>
                  <li>• <strong>Hover over the (?) icon</strong> next to each metric for detailed explanations</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Grid of Individual Metric Graphs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5 lg:gap-6 mb-6 sm:mb-8">
            {metricsConfig.map((metric) => (
              <MetricGraph 
                key={metric.key} 
                metric={metric} 
                data={chartData}
              />
            ))}
          </div>

          {/* Overall Evaluation Summary Section */}
          {overallEvaluation && analysis && (
            <div className="mt-6 sm:mt-8 pt-6 sm:pt-8 border-t border-[var(--color-border)]">
              <div className="mb-4 sm:mb-6">
                <h3 className="text-lg sm:text-xl font-bold text-[var(--color-text-primary)] mb-2 flex items-center gap-2">
                  <FiTarget className="text-[var(--color-primary)]" size={22} />
                  Overall Performance Analysis
                </h3>
                {analysis.confidence_level && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`inline-block px-2 py-1 text-xs font-semibold rounded border ${getConfidenceColor(analysis.confidence_level)}`}>
                      {analysis.confidence_level.toUpperCase()} Confidence
                    </span>
                    <div className="relative">
                      <button
                        onMouseEnter={() => setShowHelpTooltip('confidence-level')}
                        onMouseLeave={() => setShowHelpTooltip(null)}
                        className="text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors"
                      >
                        <FiHelpCircle size={14} />
                      </button>
                      <HelpTooltip 
                        id="confidence-level"
                        text="Confidence level indicates how reliable the analysis is based on score consistency. High confidence = consistent scores, Low confidence = highly variable scores."
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Summary */}
              {analysis.summary && (
                <div className="mb-6">
                  <h4 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
                    <FiInfo className="text-[var(--color-primary)]" size={18} />
                    Summary
                  </h4>
                  <p className="text-sm sm:text-base text-[var(--color-text-secondary)] leading-relaxed bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)]">
                    {analysis.summary}
                  </p>
                </div>
              )}

              {/* Key Metrics */}
              {numericResults && Object.keys(numericResults).length > 0 && (
                <div className="mb-6">
                  <h4 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
                    <FiTarget className="text-[var(--color-primary)]" size={18} />
                    Key Metrics
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
                    {numericResults.mean_score !== undefined && (
                      <MetricExplanation
                        label="Mean Score"
                        value={
                          <div className="text-2xl font-bold text-[var(--color-text-primary)]">
                            {numericResults.mean_score.toFixed(1)}/10
                          </div>
                        }
                        description="The average of all your overall interview scores across all interviews. This gives you a general sense of your performance level."
                        tooltip="mean-score"
                      />
                    )}
                    {numericResults.regression_trend && (
                      <MetricExplanation
                        label="Trend"
                        value={
                          <div className="text-lg font-semibold text-[var(--color-text-primary)] capitalize flex items-center gap-2">
                            {numericResults.regression_trend === 'improving' ? (
                              <FiTrendingUp className="text-green-500" size={18} />
                            ) : numericResults.regression_trend === 'declining' ? (
                              <FiTrendingDown className="text-red-500" size={18} />
                            ) : null}
                            {numericResults.regression_trend}
                          </div>
                        }
                        description="Overall direction of your performance based on linear regression analysis. 'Improving' = scores increasing over time, 'Declining' = scores decreasing, 'Stable' = relatively consistent."
                        tooltip="regression-trend"
                      />
                    )}
                    {numericResults.best_metric && (
                      <MetricExplanation
                        label="Best Metric"
                        value={
                          <div className="text-lg font-semibold text-[var(--color-text-primary)] capitalize">
                            {numericResults.best_metric.replace(/_/g, ' ')}
                          </div>
                        }
                        description="The metric showing the best performance or least decline. This is your strongest area relative to other metrics."
                        tooltip="best-metric"
                      />
                    )}
                  </div>
                </div>
              )}

              {/* Improvement Areas */}
              {analysis.improvement_areas && analysis.improvement_areas.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
                    <FiAlertCircle className="text-orange-500" size={18} />
                    Areas for Improvement
                  </h4>
                  <ul className="space-y-2">
                    {analysis.improvement_areas.map((area, index) => (
                      <li
                        key={index}
                        className="flex items-start gap-3 bg-orange-50 dark:bg-orange-900/10 p-3 sm:p-4 rounded-lg border border-orange-200 dark:border-orange-800"
                      >
                        <span className="text-orange-500 mt-0.5 flex-shrink-0">•</span>
                        <span className="text-sm sm:text-base text-[var(--color-text-primary)] flex-1">
                          {area}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Recommendations */}
              {analysis.recommendations && analysis.recommendations.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
                    <FiCheckCircle className="text-green-500" size={18} />
                    Recommendations
                  </h4>
                  <ul className="space-y-2">
                    {analysis.recommendations.map((rec, index) => (
                      <li
                        key={index}
                        className="flex items-start gap-3 bg-green-50 dark:bg-green-900/10 p-3 sm:p-4 rounded-lg border border-green-200 dark:border-green-800"
                      >
                        <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>
                        <span className="text-sm sm:text-base text-[var(--color-text-primary)] flex-1">
                          {rec}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Last Updated */}
              {overallEvaluation.created_at && (
                <div className="text-xs text-[var(--color-text-secondary)] text-center pt-4 border-t border-[var(--color-border)]">
                  Last updated: {new Date(overallEvaluation.created_at).toLocaleString('en-US', {
                    month: 'numeric',
                    day: 'numeric',
                    year: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true
                  })}
                </div>
              )}
            </div>
          )}

          {/* Loading state for evaluation */}
          {loadingEvaluation && (
            <div className="mt-6 sm:mt-8 pt-6 sm:pt-8 border-t border-[var(--color-border)] text-center">
              <p className="text-sm text-[var(--color-text-secondary)]">Loading performance analysis...</p>
            </div>
          )}

          {/* Footer Info */}
          <div className="mt-4 sm:mt-6 text-xs sm:text-sm text-[var(--color-text-secondary)] text-center">
            <p>
              All metrics are scored on a scale of 0-10. Hover over data points to see detailed values.
            </p>
        <p className="mt-1">
              Click the (?) icon next to any metric or value for detailed explanations.
        </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceGraph;
