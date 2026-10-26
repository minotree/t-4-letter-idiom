import React from 'react';
import { createRoot } from 'react-dom/client';
import { TDSMobileAITProvider } from '@toss/tds-mobile-ait';
import App from './App';
import './styles.css';

class ErrorBoundary extends React.Component<React.PropsWithChildren, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <main><h1>화면을 불러오지 못했어요</h1><button onClick={() => location.reload()}>다시 시도</button></main> : this.props.children;
  }
}
createRoot(document.getElementById('root')!).render(
  <React.StrictMode><ErrorBoundary><TDSMobileAITProvider brandPrimaryColor="#2d6050"><App /></TDSMobileAITProvider></ErrorBoundary></React.StrictMode>,
);
