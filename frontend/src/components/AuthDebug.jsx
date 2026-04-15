import { useAuth } from '../contexts/AuthContext';

export default function AuthDebug() {
  const { user, loading, isAuthenticated } = useAuth();

  return (
    <div className="fixed top-4 right-4 bg-white p-4 rounded-lg shadow-lg border max-w-sm">
      <h3 className="font-bold mb-2">Auth Debug</h3>
      <div className="text-sm space-y-1">
        <p><strong>Loading:</strong> {loading ? 'Yes' : 'No'}</p>
        <p><strong>Authenticated:</strong> {isAuthenticated ? 'Yes' : 'No'}</p>
        <p><strong>User:</strong> {user ? user.email : 'None'}</p>
        <p><strong>User ID:</strong> {user?.id || 'None'}</p>
      </div>
    </div>
  );
}