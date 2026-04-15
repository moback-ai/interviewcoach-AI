import TestAuth from '../components/TestAuth';

export default function TestPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="container mx-auto px-4">
        <h1 className="text-3xl font-bold text-center mb-8">
          Backend Authentication Test
        </h1>
        <TestAuth />
      </div>
    </div>
  );
}