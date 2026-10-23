import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './register-pwa';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
