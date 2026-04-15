import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FiCheckCircle, FiLoader, FiXCircle } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import { supabase } from '../supabaseClient';

export default function PaymentSuccess() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('processing');
  const [message, setMessage] = useState('Processing your payment...');

  useEffect(() => {
    const processPayment = async () => {
      try {
        // Get parameters from URL
        const interviewId = searchParams.get('interview_id');
        const paymentId = searchParams.get('payment_id');
        const paymentStatus = searchParams.get('status');
        
        // ✅ NEW: Get resume_id, jd_id, question_set from URL (preserved from payment creation)
        const resumeId = searchParams.get('resume_id');
        const jdId = searchParams.get('jd_id');
        const questionSet = searchParams.get('question_set');
        
        console.log('Payment processing:', { 
          interviewId, 
          paymentId, 
          paymentStatus, 
          resumeId, 
          jdId, 
          questionSet 
        });
        
        if (!interviewId) {
          console.error('No interview_id provided');
          navigate('/dashboard');
          return;
        }
        
        // ✅ Check payment status and redirect accordingly
        if (paymentStatus === 'succeeded' || paymentStatus === 'success' || paymentStatus === 'completed') {
          setStatus('success');
          setMessage('Payment successful! Redirecting to interview...');
          
          // Wait a moment for webhook to process, then redirect to interview
          setTimeout(() => {
            navigate(`/interview?interview_id=${interviewId}`);
          }, 2000);
          
        } else {
          // ✅ Payment failed or processing - redirect back to questions page
          // Use preserved URL parameters first, fallback to fetching from interview if needed
          setStatus('error');
          setMessage('Payment was not successful. Redirecting back to questions...');
          
          // ✅ Use preserved parameters from URL if available
          if (resumeId && jdId) {
            console.log('✅ Using preserved parameters from URL:', { resumeId, jdId, questionSet });
            setTimeout(() => {
              const questionSetParam = questionSet ? `&question_set=${questionSet}` : '';
              navigate(`/questions?resume_id=${resumeId}&jd_id=${jdId}${questionSetParam}`);
            }, 3000);
          } else {
            // ✅ Fallback: Try to fetch from interview if URL params are missing
            console.log('⚠️ URL parameters missing, fetching from interview...');
            try {
              const { data: { session } } = await supabase.auth.getSession();
              if (session?.access_token) {
                const response = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/interviews/${interviewId}`, {
                  headers: {
                    'Authorization': `Bearer ${session.access_token}`
                  }
                });
                
                if (response.ok) {
                  const result = await response.json();
                  const interview = result.data;
                  
                  // Only use interview data if it has the values (not null)
                  if (interview.resume_id && interview.jd_id) {
                    console.log('✅ Got parameters from interview:', { 
                      resume_id: interview.resume_id, 
                      jd_id: interview.jd_id, 
                      question_set: interview.question_set 
                    });
                    setTimeout(() => {
                      const questionSetParam = interview.question_set ? `&question_set=${interview.question_set}` : '';
                      navigate(`/questions?resume_id=${interview.resume_id}&jd_id=${interview.jd_id}${questionSetParam}`);
                    }, 3000);
                  } else {
                    // Interview doesn't have the values yet - redirect to dashboard
                    console.warn('⚠️ Interview data incomplete, redirecting to dashboard');
                    setTimeout(() => {
                      navigate('/dashboard');
                    }, 3000);
                  }
                } else {
                  // Fallback to dashboard if we can't get interview details
                  setTimeout(() => {
                    navigate('/dashboard');
                  }, 3000);
                }
              } else {
                // Fallback to dashboard if no session
                setTimeout(() => {
                  navigate('/dashboard');
                }, 3000);
              }
            } catch (error) {
              console.error('Error getting interview details:', error);
              // Fallback to dashboard
              setTimeout(() => {
                navigate('/dashboard');
              }, 3000);
            }
          }
        }
        
      } catch (error) {
        console.error('Error processing payment:', error);
        setStatus('error');
        setMessage('Error processing payment. Redirecting to dashboard...');
        
        setTimeout(() => {
          navigate('/dashboard');
        }, 3000);
      }
    };
    
    processPayment();
  }, [navigate, searchParams]);

  // ✅ Return null to make page invisible - all functionality still runs in useEffect
  return null;
}
