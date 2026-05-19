import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getSession } from '../lib/authClient';
import { 
  FiUser, 
  FiMail, 
  FiCalendar, 
  FiCamera,
  FiEdit3, 
  FiSave, 
  FiX, 
  FiCreditCard, 
  FiSettings, 
  FiBarChart, 
  FiShield,
  FiBell,
  FiChevronRight,
  FiMenu,
  FiX as FiClose,
  FiDollarSign,
  FiClock,
  FiCheckCircle,
  FiXCircle,
  FiLoader,
  FiHash,
  FiRefreshCw
} from 'react-icons/fi';
import Navbar from '../components/Navbar';
import PageWavesShell from '../components/common/PageWavesShell';
import { getBackendOrigin } from '../utils/apiConfig';

const MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024;
const ACCEPTED_AVATAR_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);

const buildProfileState = (user) => ({
  full_name: user?.user_metadata?.full_name || user?.full_name || '',
  nickname: user?.user_metadata?.nickname || user?.nickname || '',
  date_of_birth: user?.user_metadata?.date_of_birth || user?.date_of_birth || '',
  email: user?.email || '',
  username: user?.username || '',
  avatar_url: user?.user_metadata?.avatar_url || user?.avatar_url || '',
  created_at: user?.created_at || '',
});

const getProfileInitials = (value = '') => {
  const words = value.trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }
  return 'IC';
};

const validateAvatarFile = (file) => {
  if (!file) {
    return 'Please choose an image file.';
  }
  if (!ACCEPTED_AVATAR_TYPES.has(file.type)) {
    return 'Use a JPG, PNG, GIF, or WEBP image.';
  }
  if (file.size > MAX_AVATAR_SIZE_BYTES) {
    return 'Profile pictures must be 5 MB or smaller.';
  }
  return '';
};

// Component for Profile Section
const ProfileSection = ({
  profileData,
  setProfileData,
  isEditing,
  setIsEditing,
  loading,
  handleSave,
  handleCancel,
  formatDate,
  statusMessage,
  statusTone,
  avatarPreview,
  avatarFile,
  avatarError,
  handleAvatarFileChange,
}) => {
  const avatarSource = avatarPreview || profileData.avatar_url;
  const displayName = profileData.full_name || profileData.nickname || profileData.email || 'InterviewCoach';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">
          Personal Information
        </h2>
        {!isEditing ? (
          <button
            onClick={() => setIsEditing(true)}
            className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-[var(--color-primary)] hover:bg-[var(--color-input-bg)] rounded-lg transition"
          >
            <FiEdit3 size={16} />
            <span>Edit Profile</span>
          </button>
        ) : (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleSave}
              disabled={loading}
              className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-white bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] rounded-lg transition disabled:opacity-50"
            >
              <FiSave size={16} />
              <span>{loading ? 'Saving...' : 'Save'}</span>
            </button>
            <button
              onClick={handleCancel}
              className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-input-bg)] rounded-lg transition"
            >
              <FiX size={16} />
              <span>Cancel</span>
            </button>
          </div>
        )}
      </div>

      {statusMessage ? (
        <div
          className={`rounded-xl border px-4 py-3 text-sm ${
            statusTone === 'success'
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200'
              : 'border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-200'
          }`}
        >
          {statusMessage}
        </div>
      ) : null}

      <div className="space-y-6">
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-[var(--color-surface-shadow)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border border-[var(--color-border)] bg-[var(--color-input-bg)] text-2xl font-semibold text-[var(--color-primary)]">
                {avatarSource ? (
                  <img
                    src={avatarSource}
                    alt="Profile"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span>{getProfileInitials(displayName)}</span>
                )}
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-medium text-[var(--color-text-primary)]">
                  Profile picture
                </h3>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  Upload a JPG, PNG, GIF, or WEBP image up to 5 MB.
                </p>
                <p className="text-xs text-[var(--color-text-secondary)]">
                  {avatarFile ? `Selected: ${avatarFile.name}` : avatarSource ? 'Current photo ready to update.' : 'Using initials until you upload a photo.'}
                </p>
              </div>
            </div>

            {isEditing ? (
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-4 py-2 text-sm font-medium text-[var(--color-text-primary)] transition hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]">
                <FiCamera size={16} />
                <span>{avatarSource ? 'Change photo' : 'Upload photo'}</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="hidden"
                  onChange={handleAvatarFileChange}
                />
              </label>
            ) : null}
          </div>

          {avatarError ? (
            <p className="mt-3 text-sm text-rose-600 dark:text-rose-300">{avatarError}</p>
          ) : null}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
              <FiUser className="inline mr-2" size={16} />
              Full Name
            </label>
            {isEditing ? (
              <input
                type="text"
                value={profileData.full_name}
                onChange={(e) => setProfileData({...profileData, full_name: e.target.value})}
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                placeholder="Enter your full name"
              />
            ) : (
              <p className="text-[var(--color-text-primary)]">
                {profileData.full_name || 'Not provided'}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
              <FiHash className="inline mr-2" size={16} />
              Nickname
            </label>
            {isEditing ? (
              <input
                type="text"
                value={profileData.nickname}
                onChange={(e) => setProfileData({ ...profileData, nickname: e.target.value })}
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                placeholder="How you want to be addressed"
              />
            ) : (
              <p className="text-[var(--color-text-primary)]">
                {profileData.nickname || 'Not provided'}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
              <FiMail className="inline mr-2" size={16} />
              Email Address
            </label>
            <p className="text-[var(--color-text-primary)]">
              {profileData.email}
            </p>
            <p className="text-xs text-[var(--color-text-secondary)] mt-1">
              Email cannot be changed
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
              <FiCalendar className="inline mr-2" size={16} />
              Date of Birth
            </label>
            {isEditing ? (
              <input
                type="date"
                value={profileData.date_of_birth}
                onChange={(e) => setProfileData({ ...profileData, date_of_birth: e.target.value })}
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-input-bg)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            ) : (
              <p className="text-[var(--color-text-primary)]">
                {formatDate(profileData.date_of_birth, 'Not provided')}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
              <FiHash className="inline mr-2" size={16} />
              Username
            </label>
            <p className="text-[var(--color-text-primary)]">
              {profileData.username || 'Not available'}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-2">
              <FiCalendar className="inline mr-2" size={16} />
              Account Created
            </label>
            <p className="text-[var(--color-text-primary)]">
              {formatDate(profileData.created_at, 'Not available')}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

// New Payment History Section Component
const PaymentsSection = () => {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchPaymentHistory();
  }, []);

  const fetchPaymentHistory = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get user session
      const session = await getSession();
      
      if (!session?.access_token) {
        setError('Authentication required');
        setLoading(false);
        return;
      }

      // Fetch all payments for the user using the edge function
      const response = await fetch(`${getBackendOrigin()}/functions/v1/payments?get_all=true`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        }
      });

      const result = await response.json();

      if (response.ok && result.success) {
        setPayments(result.data || []);
      } else {
        setError(result.message || 'Failed to fetch payment history');
      }
    } catch (error) {
      console.error('Error fetching payment history:', error);
      setError('Failed to load payment history');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchPaymentHistory();
    setRefreshing(false);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'succeeded':
      case 'success':
        return <FiCheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <FiXCircle className="w-5 h-5 text-red-500" />;
      case 'pending':
      case 'processing':
        return <FiClock className="w-5 h-5 text-yellow-500" />;
      default:
        return <FiDollarSign className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'succeeded':
      case 'success':
        return 'text-green-600 bg-green-100';
      case 'failed':
        return 'text-red-600 bg-red-100';
      case 'pending':
      case 'processing':
        return 'text-yellow-600 bg-yellow-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatAmount = (amount) => {
    // Convert from paise to rupees
    return `₹${(amount / 100).toFixed(2)}`;
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    // You could add a toast notification here
  };

  // Calculate summary statistics
  const totalPayments = payments.length;
  const successfulPayments = payments.filter(p => p.payment_status === 'succeeded' || p.payment_status === 'success').length;
  const totalAmount = payments.reduce((sum, p) => sum + (p.amount || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">
            Payment History
          </h2>
          <p className="text-[var(--color-text-secondary)] mt-1">
            View and manage your payment transactions
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center space-x-2 px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:bg-opacity-90 transition-colors disabled:opacity-50"
        >
          <FiRefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-4">
          <div className="flex items-center space-x-3">
            <FiCreditCard className="w-6 h-6 text-[var(--color-primary)]" />
            <div>
              <div className="text-2xl font-bold text-[var(--color-text-primary)]">{totalPayments}</div>
              <div className="text-sm text-[var(--color-text-secondary)]">Total Payments</div>
            </div>
          </div>
        </div>
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-4">
          <div className="flex items-center space-x-3">
            <FiCheckCircle className="w-6 h-6 text-green-500" />
            <div>
              <div className="text-2xl font-bold text-[var(--color-text-primary)]">{successfulPayments}</div>
              <div className="text-sm text-[var(--color-text-secondary)]">Successful</div>
            </div>
          </div>
        </div>
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-4">
          <div className="flex items-center space-x-3">
            <FiDollarSign className="w-6 h-6 text-[var(--color-primary)]" />
            <div>
              <div className="text-2xl font-bold text-[var(--color-text-primary)]">{formatAmount(totalAmount)}</div>
              <div className="text-sm text-[var(--color-text-secondary)]">Total Spent</div>
            </div>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-100 border border-red-300 rounded-lg">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {/* Payment List */}
      {loading ? (
        <div className="text-center py-12">
          <FiLoader className="w-8 h-8 text-[var(--color-primary)] mx-auto mb-4 animate-spin" />
          <p className="text-[var(--color-text-secondary)]">Loading payment history...</p>
        </div>
      ) : payments.length === 0 ? (
        <div className="text-center py-12">
          <FiDollarSign className="w-16 h-16 text-[var(--color-text-secondary)] mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">
            No payments found
          </h3>
          <p className="text-[var(--color-text-secondary)]">
            You haven't made any payments yet.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {payments.map((payment) => (
            <div
              key={payment.id}
              className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-6 hover:shadow-md transition-shadow"
            >
              {/* Main Payment Info */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-4">
                  {getStatusIcon(payment.payment_status)}
                  <div>
                    <h3 className="font-semibold text-[var(--color-text-primary)] text-lg">
                      {payment.provider?.toUpperCase()} Payment
                    </h3>
                    <p className="text-sm text-[var(--color-text-secondary)]">
                      {formatDate(payment.paid_at)}
                    </p>
                  </div>
                </div>
                
                <div className="text-right">
                  <div className="text-2xl font-bold text-[var(--color-text-primary)]">
                    {formatAmount(payment.amount)}
                  </div>
                  <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(payment.payment_status)}`}>
                    {payment.payment_status}
                  </span>
                </div>
              </div>

              {/* Payment IDs Section */}
              <div className="bg-[var(--color-bg)] rounded-lg p-4 mb-4">
                <h4 className="font-medium text-[var(--color-text-primary)] mb-3 flex items-center">
                  <FiHash className="w-4 h-4 mr-2" />
                  Payment Identifiers
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Payment ID (Dodo's ID) */}
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                      Payment ID (Dodo)
                    </label>
                    <div className="flex items-center space-x-2">
                      <code className="flex-1 bg-[var(--color-card)] px-3 py-2 rounded text-sm font-mono text-[var(--color-text-primary)] border border-[var(--color-border)]">
                        {payment.transaction_id}
                      </code>
                      <button
                        onClick={() => copyToClipboard(payment.transaction_id)}
                        className="px-2 py-2 text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors"
                        title="Copy Payment ID"
                      >
                        <FiCreditCard className="w-4 h-4" />
                      </button>
                    </div>
                    <p className="text-xs text-[var(--color-text-secondary)]">
                      External payment processor ID
                    </p>
                  </div>

                  {/* Transaction ID (Internal) */}
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                      Transaction ID (Internal)
                    </label>
                    <div className="flex items-center space-x-2">
                      <code className="flex-1 bg-[var(--color-card)] px-3 py-2 rounded text-sm font-mono text-[var(--color-text-primary)] border border-[var(--color-border)]">
                        {payment.id}
                      </code>
                      <button
                        onClick={() => copyToClipboard(payment.id)}
                        className="px-2 py-2 text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors"
                        title="Copy Transaction ID"
                      >
                        <FiHash className="w-4 h-4" />
                      </button>
                    </div>
                    <p className="text-xs text-[var(--color-text-secondary)]">
                      Internal system reference
                    </p>
                  </div>
                </div>
              </div>

              {/* Additional Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                    Interview ID
                  </label>
                  <div className="bg-[var(--color-bg)] px-3 py-2 rounded border border-[var(--color-border)]">
                    <code className="font-mono text-[var(--color-text-primary)]">
                      {payment.interview_id || 'Not assigned'}
                    </code>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                    Payment Provider
                  </label>
                  <div className="bg-[var(--color-bg)] px-3 py-2 rounded border border-[var(--color-border)]">
                    <span className="text-[var(--color-text-primary)] capitalize">
                      {payment.provider || 'Unknown'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Component for Analytics Section
const AnalyticsSection = () => {
    const [interviews, setInterviews] = useState([]);
    const [resumes, setResumes] = useState([]);
    const [job_descriptions, setJobDescriptions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [refreshing, setRefreshing] = useState(false);

    //Initialized structures to be used in RecentActivity
    let searchableResumes;
    let searchableJDs;
    let searchableInterviews;

    useEffect(() => {
        fetchInterviewHistory();
        fetchResumeHistory();
        fetchJDHistory();
    }, []);

    const fetchInterviewHistory = async () => {
        try{
            setLoading(true);
            setError(null);

            // Get user session
            const session = await getSession();

            if (!session?.access_token) {
                setError('Authentication required');
                setLoading(false);
                return;
            }

            // Fetch all interviews for the user using the edge function
            const response = await fetch(`${getBackendOrigin()}/functions/v1/interviews`, {
                method: 'GET',
                headers:{
                    'Authorization': `Bearer ${session.access_token}`,
                    'Content-Type': 'application/json'
                    }
                });

            const result = await response.json();

            if (response.ok && result.success){
                setInterviews(result.data || []);
            } else {
                setError(result.message || 'Failed to fetch interview history');
            }
        } catch (error) {
            console.error('Error fetching interview history', error);
            setError('Failed to load interview history');
        } finally {
            setLoading(false);
        }
    };

    const fetchResumeHistory = async () => {
        try{
            setLoading(true);
            setError(null);

            // Get user session
            const session = await getSession();

            if (!session?.access_token) {
                setError('Authentication required');
                setLoading(false);
                return;
            }

            // Fetch all resume uploads for the user using the edge function
            const response = await fetch(`${getBackendOrigin()}/functions/v1/resumes`, {
                method: 'GET',
                headers:{
                    'Authorization': `Bearer ${session.access_token}`,
                    'Content-Type': 'application/json'
                    }
                });

            const result = await response.json();

            if (response.ok && result.success){
                setResumes(result.data || []);
            } else {
                setError(result.message || 'Failed to fetch resume history');
            }
        } catch (error) {
            console.error('Error fetching resume history', error);
            setError('Failed to load resume history');
        } finally {
            setLoading(false);
        }
    };

    const fetchJDHistory = async () => {
        try{
            setLoading(true);
            setError(null);

            // Get user session
            const session = await getSession();

            if (!session?.access_token) {
                setError('Authentication required');
                setLoading(false);
                return;
            }

            // Fetch all uploaded job descriptions for the user using the edge function
            const response = await fetch(`${getBackendOrigin()}/functions/v1/job-descriptions`, {
                method: 'GET',
                headers:{
                    'Authorization': `Bearer ${session.access_token}`,
                    'Content-Type': 'application/json'
                    }
                });

            const result = await response.json();

            if (response.ok && result.success){
                setJobDescriptions(result.data || []);
            } else {
                setError(result.message || 'Failed to fetch job description history');
            }
        } catch (error) {
            console.error('Error fetching job description history', error);
            setError('Failed to load job description history');
        } finally {
            setLoading(false);
        }
    };

    const handleRefresh = async () => {
        setRefreshing(true);
        await fetchInterviewHistory();
        await fetchResumeHistory();
        await fetchJDHistory();
        setRefreshing(false);
    };

    // Reformat resumes and job_descriptions to be searchable
    const makeSearchable = () => {
        searchableResumes = JSON.parse(JSON.stringify(resumes));
        searchableJDs = JSON.parse(JSON.stringify(job_descriptions));
        searchableInterviews = JSON.parse(JSON.stringify(interviews));
    };

    // Filter resumes for a resume_id coming from Interviews
    const searchResumes = (r_id) => {
        let filteredResumes;
        let Resume;

        // Avoids undeclared structure errors
        if (searchableResumes.length > 0){
            filteredResumes = searchableResumes.filter((r) => r.id.includes(r_id));
            Resume = filteredResumes[0];
        } else {
            return "None";
        }
        return Resume.file_name;
    };

    // Filter job descriptions for a jd_id coming from Interviews
    const searchJobDescriptions = (jd_id) => {
        let filteredJobDescriptions;
        let JD;

        //Avoids undeclared structure errors
        if (searchableJDs.length > 0) {
            filteredJobDescriptions = searchableJDs.filter((jd) => jd.id.includes(jd_id));
            JD = filteredJobDescriptions[0];
        } else {
            return "None";
        }
        return JD.title;
    };

    const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

    // Calculate summary statistics
    makeSearchable();

    // Filter for interviews with an 'ENDED' status
    const totalInterviews = (searchableInterviews.filter((interview) => interview.status.includes("ENDED"))).length;
    const totalResumes = resumes.length;

    // Concatenated array of all Recent Activity, limited to 5 most recent
    const recentActivity = interviews.concat(resumes, job_descriptions).slice(0,5);

    return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">
        Analytics & Performance
      </h2>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6 text-center">
          <div className="text-2xl font-bold text-[var(--color-primary)] mb-2">{totalInterviews}</div>
          <div className="text-sm text-[var(--color-text-secondary)]">Interviews Completed</div>
        </div>
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6 text-center">
          <div className="text-2xl font-bold text-[var(--color-primary)] mb-2">{totalResumes}</div>
          <div className="text-sm text-[var(--color-text-secondary)]">Resumes Uploaded</div>
        </div>
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6 text-center">
          <div className="text-2xl font-bold text-[var(--color-primary)] mb-2">0</div>
          <div className="text-sm text-[var(--color-text-secondary)]">Practice Sessions</div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-100 border border-red-300 rounded-lg">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {/* Recent Activity List */}
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
        <h3 className="text-lg font-medium text-[var(--color-text-primary)] mb-4">
          Recent Activity
        </h3>
        {loading ? (
            <div className="text-center py-12">
                <FiLoader className="w-8 h-8 text-[var(--color-primary)] mx-auto mb-4 animate-spin" />
                <p className="text-[var(--color-text-secondary)]">Loading recent activity...</p>
            </div>
        ) : recentActivity.length === 0 ? (
        <div className="text-center py-12">
            <FiBarChart size={48} className="mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">
            No recent activity found
          </h3>
        </div>
      ) : (
          // Main Activity Info
         <div className="space-y-4">
          {recentActivity.map((ra) => (
              //scheduled_at attribute is only present in an Interview */}
              ra.scheduled_at ? (
              <div key={ra.id}
                className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-6 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-[var(--color-text-primary)] text-lg">
                 Interview Created
                    </h3>
                    <div>
                        <p className="text-sm text-[var(--color-text-secondary)]">
                      {formatDate(ra.created_at)}
                    </p>
                  </div>

                  {/* Interview Information Section */}
                  <div className="bg-[var(--color-bg)] rounded-lg p-4 mb-4">
                <h4 className="font-medium text-[var(--color-text-primary)] mb-3 flex items-center">
                  <FiHash className="w-4 h-4 mr-2" />
                  Interview Information
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                    {/* Resume File Name Card */}
                    <div className="space-y-2">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                      Resume
                    </label>
                    <div className="flex items-center space-x-2">
                      <p id="resume_file_name" className="flex-1 bg-[var(--color-card)] px-3 py-2 rounded text-sm font-mono text-[var(--color-text-primary)] border border-[var(--color-border)]">
                        {searchResumes(ra.resume_id)}
                      </p>
                    </div>
                    </div>

                    {/* Job Description Title Card */}
                    <div className="space-y-2">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                      Job Description
                    </label>
                    <div className="flex items-center space-x-2">
                      <p className="flex-1 bg-[var(--color-card)] px-3 py-2 rounded text-sm font-mono text-[var(--color-text-primary)] border border-[var(--color-border)]">
                        {searchJobDescriptions(ra.jd_id)}
                      </p>
                    </div>
                    </div>
              </div>
              </div>
              </div>
              </div>
              // title attribute is only present in Job Descriptions
              ) : ra.title ? (
                  <div key={ra.id}
                    className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-6 hover:shadow-md transition-shadow">
                    <div className="flex items-center justify-between mb-4 space-x-2">
                    <h3 className="font-semibold text-[var(--color-text-primary)] text-lg">
                    Job Description Uploaded
                    </h3>
                    <div>
                        <p className="text-sm text-[var(--color-text-secondary)]">
                      {formatDate(ra.created_at)}
                    </p>
                  </div>

                  {/* Job Description Information Section */}
                  <div className="bg-[var(--color-bg)] rounded-lg p-4 mb-4">
                <h4 className="font-medium text-[var(--color-text-primary)] mb-3 flex items-center">
                  <FiHash className="w-4 h-4 mr-2" />
                  Job Description Information
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                  {/* Job Description Title Card */}
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                      Title
                    </label>
                    <div className="flex items-center space-x-2">
                      <p className="flex-1 bg-[var(--color-card)] px-3 py-2 rounded text-sm font-mono text-[var(--color-text-primary)] border border-[var(--color-border)]">
                        {ra.title}
                      </p>
                    </div>
                    </div>

                  {/* Job Description Preview Card */}
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                      Description
                    </label>
                    <div className="flex items-center space-x-2">
                      <p className="flex-1 bg-[var(--color-card)] px-3 py-2 rounded text-sm font-mono text-[var(--color-text-primary)] border border-[var(--color-border)]">
                        {/* Limited description to 35 characters */}
                        {ra.description.slice(0,35) + "..."}
                      </p>
                    </div>
                    </div>

                  </div>
                  </div>
                  </div>
                  </div>

                  // If no title or scheduled_at attribute, activity is a Resume Upload
              ) : (<div key={ra.id}
                    className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-6 hover:shadow-md transition-shadow">
                    <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-[var(--color-text-primary)] text-lg">
                    Resume Uploaded
                    </h3>
                    <div>
                        <p className="text-sm text-[var(--color-text-secondary)]">
                      {formatDate(ra.uploaded_at)}
                    </p>
                  </div>

                  {/* Resume Information Section */}
                  <div className="bg-[var(--color-bg)] rounded-lg p-4 mb-4">
                <h4 className="font-medium text-[var(--color-text-primary)] mb-3 flex items-center">
                  <FiHash className="w-4 h-4 mr-2" />
                  Resume Information
                </h4>

                {/* Resume File Name Card */}
                <div className="space-y-2">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
                      File Name
                    </label>
                    <div className="flex items-center space-x-2">
                      <p className="flex-1 bg-[var(--color-card)] px-3 py-2 rounded text-sm font-mono text-[var(--color-text-primary)] border border-[var(--color-border)]">
                        {ra.file_name}
                      </p>
                    </div>
                    </div>

                  </div>
                  </div>
                  </div>
                  )
          ))}
        </div>
        )}
      </div>
    </div>
  );
};

// Component for Settings Section
const SettingsSection = () => {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">
        Account Settings
      </h2>

      <div className="space-y-4">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FiBell size={20} className="text-[var(--color-primary)]" />
              <div>
                <h3 className="font-medium text-[var(--color-text-primary)]">Notifications</h3>
                <p className="text-sm text-[var(--color-text-secondary)]">Manage your notification preferences</p>
              </div>
            </div>
            <button className="text-[var(--color-primary)] hover:underline">Configure</button>
          </div>
        </div>

        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FiShield size={20} className="text-[var(--color-primary)]" />
              <div>
                <h3 className="font-medium text-[var(--color-text-primary)]">Privacy & Security</h3>
                <p className="text-sm text-[var(--color-text-secondary)]">Manage your privacy settings</p>
              </div>
            </div>
            <button className="text-[var(--color-primary)] hover:underline">Configure</button>
          </div>
        </div>

        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FiSettings size={20} className="text-[var(--color-primary)]" />
              <div>
                <h3 className="font-medium text-[var(--color-text-primary)]">Preferences</h3>
                <p className="text-sm text-[var(--color-text-secondary)]">Customize your experience</p>
              </div>
            </div>
            <button className="text-[var(--color-primary)] hover:underline">Configure</button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Add this component for the Payment History link
const PaymentHistoryLink = () => {
  const navigate = useNavigate();
  
  return (
    <button
      onClick={() => navigate('/payment-history')}
      className="flex items-center justify-between w-full p-4 text-left hover:bg-[var(--color-input-bg)] rounded-lg transition-colors"
    >
      <div className="flex items-center space-x-3">
        <FiCreditCard className="w-5 h-5 text-[var(--color-primary)]" />
        <div>
          <h3 className="font-medium text-[var(--color-text-primary)]">
            Payment History
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)]">
            View all your payment transactions
          </p>
        </div>
      </div>
      <FiChevronRight className="w-5 h-5 text-[var(--color-text-secondary)]" />
    </button>
  );
};

function ProfilePage() {
  const { user, updateProfile } = useAuth();
  const [activeSection, setActiveSection] = useState('profile');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [profileStatus, setProfileStatus] = useState(null);
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState('');
  const [avatarError, setAvatarError] = useState('');
  const [profileData, setProfileData] = useState(() => buildProfileState(user));

  useEffect(() => {
    setProfileData(buildProfileState(user));
  }, [user]);

  useEffect(() => (
    () => {
      if (avatarPreview?.startsWith('blob:')) {
        URL.revokeObjectURL(avatarPreview);
      }
    }
  ), [avatarPreview]);

  const navigationItems = [
    { id: 'profile', label: 'Profile', icon: FiUser, description: 'Personal information' },
    { id: 'payments', label: 'Payments', icon: FiCreditCard, description: 'Billing & subscriptions' },
    { id: 'analytics', label: 'Analytics', icon: FiBarChart, description: 'Performance metrics' },
    { id: 'settings', label: 'Settings', icon: FiSettings, description: 'Account preferences' },
  ];

  const clearAvatarDraft = () => {
    if (avatarPreview?.startsWith('blob:')) {
      URL.revokeObjectURL(avatarPreview);
    }
    setAvatarPreview('');
    setAvatarFile(null);
    setAvatarError('');
  };

  const handleAvatarFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const validationMessage = validateAvatarFile(file);
    if (validationMessage) {
      setAvatarError(validationMessage);
      event.target.value = '';
      return;
    }

    const nextPreview = URL.createObjectURL(file);
    if (avatarPreview?.startsWith('blob:')) {
      URL.revokeObjectURL(avatarPreview);
    }

    setAvatarFile(file);
    setAvatarPreview(nextPreview);
    setAvatarError('');
    setProfileStatus(null);
    event.target.value = '';
  };

  const uploadAvatar = async (file) => {
    const session = await getSession();
    if (!session?.access_token || !user?.id) {
      throw new Error('Please sign in again before updating your profile picture.');
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('folder', `avatars/${user.id}`);

    const response = await fetch(`${getBackendOrigin()}/functions/v1/upload-file`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
      },
      body: formData,
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) {
      throw new Error(result.error || result.message || 'Failed to upload your profile picture.');
    }

    return result.data?.public_url || '';
  };

  const handleSave = async () => {
    setLoading(true);
    setProfileStatus(null);
    try {
      let nextAvatarUrl = profileData.avatar_url;

      if (avatarFile) {
        nextAvatarUrl = await uploadAvatar(avatarFile);
      }

      const nextUser = await updateProfile({
        full_name: profileData.full_name.trim(),
        nickname: profileData.nickname.trim(),
        date_of_birth: profileData.date_of_birth || null,
        avatar_url: nextAvatarUrl,
      });

      setProfileData(buildProfileState(nextUser));
      clearAvatarDraft();
      setIsEditing(false);
      setProfileStatus({
        tone: 'success',
        message: 'Profile updated successfully.',
      });
    } catch (error) {
      console.error('Error updating profile:', error);
      setProfileStatus({
        tone: 'error',
        message: error?.message || 'Failed to update profile.',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setProfileData(buildProfileState(user));
    clearAvatarDraft();
    setProfileStatus(null);
    setIsEditing(false);
  };

  const formatDate = (dateString, fallback = 'Not available') => {
    if (!dateString) {
      return fallback;
    }
    const normalizedValue = /^\d{4}-\d{2}-\d{2}$/.test(dateString)
      ? `${dateString}T00:00:00`
      : dateString;
    const parsedDate = new Date(normalizedValue);
    if (Number.isNaN(parsedDate.getTime())) {
      return fallback;
    }
    return parsedDate.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const renderActiveSection = () => {
    const profileSection = (
      <ProfileSection
        profileData={profileData}
        setProfileData={setProfileData}
        isEditing={isEditing}
        setIsEditing={setIsEditing}
        loading={loading}
        handleSave={handleSave}
        handleCancel={handleCancel}
        formatDate={formatDate}
        statusMessage={profileStatus?.message || ''}
        statusTone={profileStatus?.tone || 'success'}
        avatarPreview={avatarPreview}
        avatarFile={avatarFile}
        avatarError={avatarError}
        handleAvatarFileChange={handleAvatarFileChange}
      />
    );

    switch (activeSection) {
      case 'profile':
        return profileSection;
      case 'payments':
        return <PaymentsSection />;
      case 'analytics':
        return <AnalyticsSection />;
      case 'settings':
        return <SettingsSection />;
      default:
        return profileSection;
    }
  };

  return (
    <>
      <Navbar />
      <PageWavesShell>
        {/* Mobile Header */}
        <div className="md:hidden bg-[var(--color-card)] border-b border-[var(--color-border)] px-4 py-3">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg hover:bg-[var(--color-input-bg)]"
            >
              {sidebarOpen ? <FiClose size={20} /> : <FiMenu size={20} />}
            </button>
            <h1 className="text-lg font-semibold text-[var(--color-text-primary)]">
              {navigationItems.find(item => item.id === activeSection)?.label}
            </h1>
            <div className="w-8"></div> {/* Spacer for centering */}
          </div>
        </div>

        <div className="flex">
          {/* Sidebar */}
          <div className={`
            fixed md:static inset-y-0 left-0 z-40 w-64 bg-[var(--color-card)] border-r border-[var(--color-border)] transform transition-transform duration-300 ease-in-out
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          `}>
            <div className="p-6">
              <h2 className="text-xl font-bold text-[var(--color-text-primary)] mb-6">
                Account Settings
              </h2>
              
              <nav className="space-y-2">
                {navigationItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        setActiveSection(item.id);
                        setSidebarOpen(false);
                      }}
                      className={`
                        w-full flex items-center justify-between p-3 rounded-lg transition-all duration-200
                        ${activeSection === item.id 
                          ? 'bg-[var(--color-primary)] text-white shadow-sm' 
                          : 'text-[var(--color-text-primary)] hover:bg-[var(--color-input-bg)]'
                        }
                      `}
                    >
                      <div className="flex items-center space-x-3">
                        <Icon size={18} />
                        <div className="text-left">
                          <div className="font-medium">{item.label}</div>
                          <div className="text-xs opacity-75">{item.description}</div>
                        </div>
                      </div>
                      <FiChevronRight size={16} className="opacity-50" />
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>

          {/* Overlay for mobile */}
          {sidebarOpen && (
            <div 
              className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
              onClick={() => setSidebarOpen(false)}
            />
          )}

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            <div className="max-w-4xl mx-auto px-6 py-8">
              {/* Desktop Header */}
              <div className="hidden md:block mb-8">
                <div className="flex items-center space-x-2 text-sm text-[var(--color-text-secondary)] mb-2">
                  <span>Account</span>
                  <FiChevronRight size={14} />
                  <span>{navigationItems.find(item => item.id === activeSection)?.label}</span>
                </div>
                <h1 className="text-3xl font-bold text-[var(--color-text-primary)]">
                  {navigationItems.find(item => item.id === activeSection)?.label}
                </h1>
                <p className="text-[var(--color-text-secondary)] mt-1">
                  {navigationItems.find(item => item.id === activeSection)?.description}
                </p>
              </div>

              {/* Content */}
              <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6 shadow-sm">
                {renderActiveSection()}
              </div>
            </div>
          </div>
        </div>
      </PageWavesShell>
    </>
  );
}

export default ProfilePage;
