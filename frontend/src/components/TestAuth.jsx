import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { apiCall } from '../api';

export default function TestAuth() {
  const { user, loading, isAuthenticated } = useAuth();
  const [testResult, setTestResult] = useState(null);
  const [loadingTest, setLoadingTest] = useState(false);
  const [error, setError] = useState(null);

  const testBackendAuth = async () => {
    setLoadingTest(true);
    setError(null);
    setTestResult(null);

    try {
      const result = await apiCall('/api/test');
      setTestResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingTest(false);
    }
  };

  const testHealthCheck = async () => {
    setLoadingTest(true);
    setError(null);
    setTestResult(null);

    try {
      const result = await apiCall('/api/health');
      setTestResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingTest(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-8 p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4">Authentication Test</h2>
      
      <div className="mb-4">
        <h3 className="text-lg font-semibold mb-2">Auth State:</h3>
        <div className="space-y-2">
          <div className={`p-2 rounded ${loading ? 'bg-yellow-100' : 'bg-gray-100'}`}>
            <strong>Loading:</strong> {loading ? 'Yes' : 'No'}
          </div>
          <div className={`p-2 rounded ${isAuthenticated ? 'bg-green-100' : 'bg-red-100'}`}>
            <strong>Authenticated:</strong> {isAuthenticated ? 'Yes' : 'No'}
          </div>
          {user && (
            <div className="bg-green-100 p-3 rounded">
              <p><strong>Email:</strong> {user.email}</p>
              <p><strong>ID:</strong> {user.id}</p>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-3">
        <button
          onClick={testBackendAuth}
          disabled={!isAuthenticated || loadingTest}
          className="w-full bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600 disabled:bg-gray-400"
        >
          {loadingTest ? 'Testing...' : 'Test Backend Authentication'}
        </button>

        <button
          onClick={testHealthCheck}
          disabled={loadingTest}
          className="w-full bg-green-500 text-white py-2 px-4 rounded hover:bg-green-600 disabled:bg-gray-400"
        >
          {loadingTest ? 'Testing...' : 'Test Health Check'}
        </button>
      </div>

      {testResult && (
        <div className="mt-4 bg-gray-100 p-3 rounded">
          <h4 className="font-semibold mb-2">API Response:</h4>
          <pre className="text-sm overflow-auto">
            {JSON.stringify(testResult, null, 2)}
          </pre>
        </div>
      )}

      {error && (
        <div className="mt-4 bg-red-100 p-3 rounded">
          <h4 className="font-semibold mb-2 text-red-800">Error:</h4>
          <p className="text-red-700">{error}</p>
        </div>
      )}
    </div>
  );
}