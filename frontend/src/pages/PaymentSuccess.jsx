import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FiCheckCircle, FiXCircle, FiLoader, FiClock, FiArrowLeft } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import PageWavesShell from '../components/common/PageWavesShell';
import { getSession } from '../lib/authClient';
import { getBackendOrigin } from '../utils/apiConfig';

const MAX_POLL_ATTEMPTS = 60;

function pollDelayMs(attempt) {
  return Math.min(1500 + attempt * 500, 5000);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function PaymentSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('processing');
  const [message, setMessage] = useState('Processing payment...');
  const [paymentDetails, setPaymentDetails] = useState(null);
  const hasProcessed = useRef(false);

  const checkoutIntentId = searchParams.get('checkout_intent_id');
  const resumeId = searchParams.get('resume_id');
  const jdId = searchParams.get('jd_id');
  const questionSet = searchParams.get('question_set');

  useEffect(() => {
    const pollStatus = async () => {
      if (hasProcessed.current) return;
      hasProcessed.current = true;

      if (!checkoutIntentId) {
        setStatus('error');
        setMessage('Missing checkout information. Please try scheduling again.');
        return;
      }

      try {
        const session = await getSession();
        if (!session?.access_token) {
          setStatus('error');
          setMessage('Authentication required');
          return;
        }

        for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
          const response = await fetch(
            `${getBackendOrigin()}/api/checkout/${checkoutIntentId}/status`,
            {
              headers: {
                Authorization: `Bearer ${session.access_token}`,
              },
            }
          );

          const result = await response.json();

          if (!response.ok || !result.success) {
            setStatus('error');
            setMessage(result.message || 'Payment verification failed');
            return;
          }

          setPaymentDetails(result);

          if (result.status === 'fulfilled' && result.interview_id) {
            setStatus('success');
            setMessage('Payment successful! Redirecting to your interview...');
            setTimeout(() => {
              navigate(`/interview?interview_id=${result.interview_id}`);
            }, 2000);
            return;
          }

          if (result.status === 'paid_needs_review') {
            setStatus('error');
            setMessage(
              'Your payment was received but requires manual review. Please contact support with your payment reference.'
            );
            return;
          }

          if (result.status === 'failed') {
            setStatus('error');
            setMessage('Payment failed or was cancelled. Please try again.');
            return;
          }

          if (result.status === 'expired') {
            setStatus('error');
            setMessage('Checkout session expired. Please schedule again.');
            return;
          }

          if (result.status === 'checkout_creation_failed') {
            setStatus('error');
            setMessage('Unable to start checkout. Please try again.');
            return;
          }

          if (attempt < MAX_POLL_ATTEMPTS - 1) {
            await sleep(pollDelayMs(attempt));
          }
        }

        setStatus('pending');
        setMessage('Payment is still processing. You can wait or return to questions and try again shortly.');
      } catch (error) {
        console.error('Payment status error:', error);
        setStatus('error');
        setMessage('Payment processing failed. Please try again.');
      }
    };

    pollStatus();
  }, [checkoutIntentId, navigate]);

  const contextResumeId = resumeId || paymentDetails?.resume_id;
  const contextJdId = jdId || paymentDetails?.jd_id;
  const contextQuestionSet = questionSet || paymentDetails?.question_set;

  const backToQuestions = () => {
    if (contextResumeId && contextJdId) {
      const qs = contextQuestionSet ? `&question_set=${contextQuestionSet}` : '';
      navigate(`/questions?resume_id=${contextResumeId}&jd_id=${contextJdId}${qs}`);
      return;
    }
    navigate('/dashboard');
  };

  return (
    <>
      <Navbar />
      <PageWavesShell contentClassName="pt-20 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-md bg-[var(--color-card)] text-[var(--color-text-primary)] p-8 rounded-2xl shadow-lg border border-[var(--color-border)]">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-[var(--color-primary)] mb-2">Payment Status</h2>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Confirming your interview payment
            </p>
          </div>

          <div className="text-center">
            {status === 'processing' && (
              <>
                <FiLoader className="w-16 h-16 text-[var(--color-primary)] mx-auto mb-4 animate-spin" />
                <h3 className="text-xl font-semibold mb-2">Processing Payment</h3>
                <p className="text-[var(--color-text-secondary)]">{message}</p>
              </>
            )}

            {status === 'success' && (
              <>
                <FiCheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
                <h3 className="text-xl font-semibold mb-2">Payment Successful!</h3>
                <p className="text-[var(--color-text-secondary)] mb-4">{message}</p>
                {paymentDetails?.transaction_id && (
                  <p className="text-sm text-[var(--color-text-secondary)]">
                    Payment ID: {paymentDetails.transaction_id}
                  </p>
                )}
              </>
            )}

            {status === 'pending' && (
              <>
                <FiClock className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
                <h3 className="text-xl font-semibold mb-2">Payment Pending</h3>
                <p className="text-[var(--color-text-secondary)] mb-4">{message}</p>
                <button
                  onClick={backToQuestions}
                  className="w-full bg-[var(--color-primary)] text-white px-6 py-3 rounded-lg font-semibold"
                >
                  <FiArrowLeft className="inline mr-2" />
                  Back to Questions
                </button>
              </>
            )}

            {status === 'error' && (
              <>
                <FiXCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
                <h3 className="text-xl font-semibold mb-2 text-[var(--color-error)]">Payment Issue</h3>
                <p className="text-[var(--color-error)] font-medium mb-4" role="alert">{message}</p>
                <button
                  onClick={backToQuestions}
                  className="w-full bg-[var(--color-primary)] text-white px-6 py-3 rounded-lg font-semibold"
                >
                  <FiArrowLeft className="inline mr-2" />
                  Back to Questions
                </button>
              </>
            )}
          </div>
        </div>
      </PageWavesShell>
    </>
  );
}
