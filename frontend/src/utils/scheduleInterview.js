import { getSession } from '../lib/authClient';
import { getBackendOrigin } from './apiConfig';
import { trackEvents } from '../services/mixpanel';

async function authHeaders() {
  const session = await getSession();
  if (!session?.access_token) {
    throw new Error('No active session');
  }
  return {
    Authorization: `Bearer ${session.access_token}`,
    'Content-Type': 'application/json',
  };
}

export async function fetchInterviewQuota() {
  const headers = await authHeaders();
  const response = await fetch(`${getBackendOrigin()}/api/interview-quota`, { headers });
  const result = await response.json();
  if (!response.ok || !result.success) {
    throw new Error(result.message || 'Failed to load interview quota');
  }
  return result.data;
}

/**
 * Schedule or retake an interview: free start when quota allows, otherwise Dodo checkout.
 * On success navigates to the interview page or checkout URL.
 */
export async function scheduleInterview({
  resumeId,
  jdId,
  questionSet,
  retakeFrom = null,
}) {
  if (!resumeId || !jdId || questionSet == null) {
    throw new Error('Resume, job description, and question set are required.');
  }

  const quota = await fetchInterviewQuota();
  const headers = await authHeaders();
  const body = {
    resume_id: resumeId,
    jd_id: jdId,
    question_set: questionSet,
  };
  if (retakeFrom) {
    body.retake_from = retakeFrom;
  }

  if (quota.payment_required) {
    trackEvents.paymentPage({
      resume_id: resumeId,
      jd_id: jdId,
      question_set: questionSet,
      payment_timestamp: new Date().toISOString(),
    });

    const response = await fetch(`${getBackendOrigin()}/api/checkout`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(result.message || 'Failed to start checkout');
    }
    const checkoutUrl = result.checkout_url || result.payment_url;
    if (!checkoutUrl) {
      throw new Error('Checkout URL missing from server response');
    }
    window.location.href = checkoutUrl;
    return { mode: 'checkout', quota };
  }

  const response = await fetch(`${getBackendOrigin()}/api/interviews/start`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok || !result.success) {
    throw new Error(result.message || 'Failed to start interview');
  }
  const interviewId = result.interview_id || result.data?.interview_id;
  if (!interviewId) {
    throw new Error('Interview ID missing from server response');
  }
  window.location.href = `/interview?interview_id=${interviewId}`;
  return { mode: 'free', interviewId, quota };
}
