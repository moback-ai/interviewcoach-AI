import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { OperationProvider } from './contexts/OperationContext';
import App from './App';
import './index.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <OperationProvider>
          <App />
        </OperationProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
