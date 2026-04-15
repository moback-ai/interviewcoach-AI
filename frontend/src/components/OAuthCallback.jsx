import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../supabaseClient';
import { performSmartRedirect } from '../utils/smartRouting';

const OAuthCallback = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const handleOAuthRedirect = async () => {
      const { data, error } = await supabase.auth.getSession();

      if (data?.session) {
        // You are now logged in - use smart redirect
        performSmartRedirect(navigate);
      } else {
        // No session found, maybe an error occurred
        navigate('/login');
      }
    };

    handleOAuthRedirect();
  }, [navigate]);

  return <p className="text-center p-10">Logging in...</p>;
};

export default OAuthCallback;
