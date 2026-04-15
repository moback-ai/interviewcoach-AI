import React, { useState } from 'react';
import { FiChevronDown, FiChevronUp, FiTrendingUp, FiTrendingDown, FiTarget, FiCheckCircle, FiAlertCircle, FiInfo } from 'react-icons/fi';

const OverallEvaluation = ({ evaluationData }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!evaluationData || !evaluationData.analysis_data) {
    return null;
  }

  const analysis = evaluationData.analysis_data;
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

  // Get trend icon and color
  const getTrendDisplay = (trend) => {
    if (trend === 'improving') {
      return { icon: FiTrendingUp, color: 'text-green-500', label: 'Improving' };
    } else if (trend === 'declining') {
      return { icon: FiTrendingDown, color: 'text-red-500', label: 'Declining' };
    } else {
      return { icon: FiInfo, color: 'text-gray-500', label: 'Stable' };
    }
  };

  const trendDisplay = getTrendDisplay(numericResults.regression_trend);
  const TrendIcon = trendDisplay.icon;

  return (
    <div className="w-full bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] shadow-lg overflow-hidden">
      {/* Collapsible Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 sm:p-6 text-left hover:bg-[var(--color-input-bg)] transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 rounded-t-xl"
      >
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-lg sm:text-xl font-bold text-[var(--color-text-primary)]">
              Overall Performance Analysis
            </h2>
            {numericResults.regression_trend && (
              <div className={`flex items-center gap-1 ${trendDisplay.color}`}>
                <TrendIcon size={20} />
                <span className="text-sm font-medium">{trendDisplay.label}</span>
              </div>
            )}
            {analysis.confidence_level && (
              <span className={`px-2 py-1 text-xs font-semibold rounded border ${getConfidenceColor(analysis.confidence_level)}`}>
                {analysis.confidence_level.toUpperCase()} Confidence
              </span>
            )}
          </div>
          <p className="text-xs sm:text-sm text-[var(--color-text-secondary)]">
            Comprehensive analysis based on {fullAnalysis.total_interviews || 0} interview{fullAnalysis.total_interviews !== 1 ? 's' : ''}
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
          {/* Summary Section */}
          {analysis.summary && (
            <div className="mb-6">
              <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
                <FiInfo className="text-[var(--color-primary)]" size={20} />
                Summary
              </h3>
              <p className="text-sm sm:text-base text-[var(--color-text-secondary)] leading-relaxed bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)]">
                {analysis.summary}
              </p>
            </div>
          )}

          {/* Key Metrics Grid */}
          {numericResults && Object.keys(numericResults).length > 0 && (
            <div className="mb-6">
              <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
                <FiTarget className="text-[var(--color-primary)]" size={20} />
                Key Metrics
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
                {numericResults.mean_score !== undefined && (
                  <div className="bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)]">
                    <div className="text-xs text-[var(--color-text-secondary)] mb-1">Mean Score</div>
                    <div className="text-2xl font-bold text-[var(--color-text-primary)]">
                      {numericResults.mean_score.toFixed(1)}/10
                    </div>
                  </div>
                )}
                {numericResults.percent_change !== undefined && (
                  <div className="bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)]">
                    <div className="text-xs text-[var(--color-text-secondary)] mb-1">Change (First → Second Half)</div>
                    <div className={`text-2xl font-bold ${numericResults.percent_change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {numericResults.percent_change >= 0 ? '+' : ''}{numericResults.percent_change.toFixed(1)}%
                    </div>
                  </div>
                )}
                {numericResults.consistency && (
                  <div className="bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)]">
                    <div className="text-xs text-[var(--color-text-secondary)] mb-1">Consistency</div>
                    <div className="text-2xl font-bold text-[var(--color-text-primary)] capitalize">
                      {numericResults.consistency}
                    </div>
                  </div>
                )}
                {numericResults.volatility && (
                  <div className="bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)]">
                    <div className="text-xs text-[var(--color-text-secondary)] mb-1">Volatility</div>
                    <div className="text-2xl font-bold text-[var(--color-text-primary)] capitalize">
                      {numericResults.volatility}
                    </div>
                  </div>
                )}
                {numericResults.best_metric && (
                  <div className="bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)]">
                    <div className="text-xs text-[var(--color-text-secondary)] mb-1">Best Metric</div>
                    <div className="text-lg font-semibold text-[var(--color-text-primary)] capitalize">
                      {numericResults.best_metric.replace(/_/g, ' ')}
                    </div>
                  </div>
                )}
                {numericResults.weakest_metric && (
                  <div className="bg-[var(--color-input-bg)] p-4 rounded-lg border border-[var(--color-border)]">
                    <div className="text-xs text-[var(--color-text-secondary)] mb-1">Focus Area</div>
                    <div className="text-lg font-semibold text-[var(--color-text-primary)] capitalize">
                      {numericResults.weakest_metric.replace(/_/g, ' ')}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Improvement Areas */}
          {analysis.improvement_areas && analysis.improvement_areas.length > 0 && (
            <div className="mb-6">
              <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
                <FiAlertCircle className="text-orange-500" size={20} />
                Areas for Improvement
              </h3>
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
              <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
                <FiCheckCircle className="text-green-500" size={20} />
                Recommendations
              </h3>
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
          <div className="text-xs text-[var(--color-text-secondary)] text-center pt-4 border-t border-[var(--color-border)]">
            Last updated: {new Date(evaluationData.created_at).toLocaleString('en-US', {
              month: 'numeric',
              day: 'numeric',
              year: 'numeric',
              hour: 'numeric',
              minute: '2-digit',
              hour12: true
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default OverallEvaluation;
