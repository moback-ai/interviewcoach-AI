import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { OperationProvider } from './contexts/OperationContext';
import { ThemeProvider } from './contexts/ThemeContext';
import App from './App';
import './index.css';
import { initAuthInterceptor } from './utils/authInterceptor';

initAuthInterceptor();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <OperationProvider>
            <App />
          </OperationProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>
);
