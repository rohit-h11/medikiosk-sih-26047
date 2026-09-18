import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, Navigate, useLocation } from 'react-router-dom';
import { VoiceProvider } from './context/VoiceContext';
import { ScreenD_Qr } from './pages/ScreenD_Qr';
import { ScreenD4_PatientProfile } from './pages/ScreenD4_PatientProfile';
import { ScreenD4_UploadDocument } from './pages/ScreenD4_UploadDocument';
import { ScreenD4_Records } from './pages/ScreenD4_Records';
import { ScreenD_Chatbot } from './pages/ScreenD_Chatbot';
import { MobileUploadPage } from './pages/MobileUploadPage';
import { SimpleVoiceTest } from './components/SimpleVoiceTest';
import { AbhaProfile } from './types/abha';

const AppRoutes: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [activePatient, setActivePatient] = useState<AbhaProfile | null>(null);
  const [activeDocument, setActiveDocument] = useState<any>(null);

  // Rehydrate active patient from Kiosk Database on mount / page refresh
  useEffect(() => {
    const fetchSession = async () => {
      try {
        const res = await fetch('/api/v1/kiosk/session');
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated && data.patient) {
            setActivePatient({
              abhaNumber: data.patient.abha_number,
              abhaAddress: data.patient.abha_address || 'rohit.hudlikar@abdm',
              name: data.patient.name,
              gender: data.patient.gender,
              age: data.patient.age,
              mobile: data.patient.phone,
              photoUrl: data.patient.photo_url,
              prakriti: data.patient.prakriti,
              recordsCount: 8,
              documentsCount: 0,
            });
          }
        }
      } catch (err) {
        console.warn('Could not fetch active kiosk session from DB:', err);
      }
    };
    fetchSession();
  }, []);

  // When patient successfully enters OTP on Screen 2 (Screen D)
  const handleLoginSuccess = (profile: AbhaProfile) => {
    setActivePatient(profile);
    navigate('/profile');
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/v1/kiosk/session/logout', { method: 'POST' });
    } catch (e) {
      console.warn('Kiosk session logout notice:', e);
    }
    setActivePatient(null);
    setActiveDocument(null);
    navigate('/');
  };


  return (
    <Routes>
      {/* 1. Screen 2: QR Scanner & ABHA OTP Login */}
      <Route
        path="/"
        element={
          <ScreenD_Qr
            onBack={() => navigate('/')}
            onLoginSuccess={handleLoginSuccess}
          />
        }
      />
      <Route path="/login" element={<Navigate to="/" replace />} />

      {/* 2. Screen D4: 1:1 Verified Patient Profile & Records Dashboard */}
      <Route
        path="/profile"
        element={
          <ScreenD4_PatientProfile
            profile={activePatient}
            onBack={() => navigate('/')}
            onLogout={handleLogout}
            onStartConsultation={() => navigate('/consultation')}
            onUploadDocument={() => navigate('/upload-document')}
            onViewRecords={() => navigate('/records')}
          />
        }
      />
      <Route path="/d4" element={<Navigate to="/profile" replace />} />

      {/* 3. Screen D4 i: 1:1 Figma Document Upload Screen (Scan Camera / Upload from Device) */}
      <Route
        path="/upload-document"
        element={
          <ScreenD4_UploadDocument
            profile={activePatient}
            onBack={() => navigate('/profile')}
            onProceedConsultation={(doc) => {
              if (doc) setActiveDocument(doc);
              navigate('/consultation');
            }}
          />
        }
      />
      <Route path="/scan-document" element={<Navigate to="/upload-document" replace />} />
      <Route path="/d4/upload" element={<Navigate to="/upload-document" replace />} />

      {/* 4. Screen D4 ii: 1:1 Figma Patient Summary & Past Reports (Node 273:2914) */}
      <Route
        path="/records"
        element={
          <ScreenD4_Records
            profile={activePatient}
            onBack={() => navigate('/profile')}
            onProceedConsultation={() => navigate('/consultation')}
          />
        }
      />
      <Route path="/d4/records" element={<Navigate to="/records" replace />} />
      <Route path="/past-records" element={<Navigate to="/records" replace />} />

      {/* 5. Screen 3: Clinical Consultation & Voice Interview (1:1 Figma Dchatbot) */}
      <Route
        path="/consultation"
        element={
          <ScreenD_Chatbot
            profile={activePatient}
            attachedDocument={activeDocument}
            onBack={() => navigate('/profile')}
            onFinish={() => navigate('/profile')}
          />
        }
      />
      <Route path="/voice-interview" element={<Navigate to="/consultation" replace />} />

      {/* Mobile Upload Flow */}
      <Route path="/mobile-upload" element={<MobileUploadPage />} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <VoiceProvider defaultLanguage="hi">
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </VoiceProvider>
  );
};

export default App;
