import React from 'react';
import { SimpleVoiceTest } from './components/SimpleVoiceTest';

export const App: React.FC = () => {
  return (
    <main style={{ minHeight: '100vh', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <SimpleVoiceTest />
    </main>
  );
};

export default App;
