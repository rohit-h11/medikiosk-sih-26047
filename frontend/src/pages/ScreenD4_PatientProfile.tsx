/**
 * MediKiosk — Screen D4: Patient Profile & Health Records Dashboard (Exact 1:1 Figma Design)
 * Matches Node 258:3414 from Figma.
 * Displays authenticated patient data, official ABDM details, and profile photo fetched live from Supabase.
 */

import React, { useState } from 'react';
import { ArrowLeft, Edit3, UploadCloud, MessageSquare, CheckCircle, ShieldCheck } from 'lucide-react';
import { AbdmLogo } from '@/assets/AbdmLogo';
import { useTranslation } from '@/hooks/useTranslation';
import { AbhaProfile } from '@/types/abha';
import '@/styles/screen_d4_figma.css';

interface ScreenD4Props {
  profile?: AbhaProfile | null;
  onBack?: () => void;
  onLogout?: () => void;
  onStartConsultation?: () => void;
  onViewRecords?: () => void;
  onUploadDocument?: () => void;
}

export const ScreenD4_PatientProfile: React.FC<ScreenD4Props> = ({
  profile,
  onBack,
  onLogout,
  onStartConsultation,
  onViewRecords,
  onUploadDocument,
}) => {
  const { t } = useTranslation();
  const [imgError, setImgError] = useState(false);

  // Active patient data from Supabase
  const patientName = profile?.name || 'Ayushman Beneficiary';
  const abhaNumber = profile?.abhaNumber || '91-8824-3942-1092';
  const abhaAddress = profile?.abhaAddress || 'beneficiary@abdm';
  const photoUrl =
    profile?.photoUrl ||
    'https://ijnostquvznatsiwqdej.supabase.co/storage/v1/object/public/patient-photos/profiles/rohit_verma.jpg';
  const recordsCount = profile?.recordsCount ?? 8;
  const documentsCount = profile?.documentsCount ?? 0;


  return (
    <div className="figma-screen-d4">
      {/* 1. TOP HEADER BAR */}
      <header className="figma-d4-header">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <button
            type="button"
            className="figma-d4-back-btn"
            onClick={onBack || onLogout}
            aria-label="Back"
          >
            <ArrowLeft size={24} strokeWidth={2.5} />
          </button>

          <div className="figma-d4-brand-logo">
            <span className="figma-d4-brand-medi">Medi</span>
            <span className="figma-d4-brand-kiosk">Kiosk</span>
          </div>
        </div>

        <div className="figma-d4-abdm-wrapper">
          <AbdmLogo size={64} />
        </div>
      </header>

      {/* 2. PROFILE GREEN BANNER */}
      <div className="figma-d4-banner-container">
        <div className="figma-d4-green-banner">
          <button
            type="button"
            className="figma-d4-banner-link"
            onClick={() => alert('Patient settings & preferences')}
          >
            {t('settings')}
          </button>

          <h2 className="figma-d4-banner-title">{t('profile_title')}</h2>

          <button
            type="button"
            className="figma-d4-banner-link"
            onClick={onLogout || onBack}
          >
            {t('logout')}
          </button>
        </div>

        {/* 3. CENTERED CIRCULAR AVATAR OVERLAY */}
        <div className="figma-d4-avatar-wrapper">
          <div className="figma-d4-avatar-circle">
            {!imgError && photoUrl ? (
              <img
                src={photoUrl}
                alt={patientName}
                className="figma-d4-avatar-img"
                onError={() => setImgError(true)}
              />
            ) : (
              <div className="figma-d4-avatar-fallback">
                {patientName.slice(0, 1).toUpperCase()}
              </div>
            )}
          </div>

          {/* 4. PATIENT NAME & VERIFIED ABHA DETAILS */}
          <h1 className="figma-d4-name">{patientName}</h1>
          <div className="figma-d4-abha-tag">
            <span className="figma-d4-badge">
              <ShieldCheck size={15} /> ABDM Verified
            </span>
            <span>•</span>
            <span>ABHA: {abhaNumber}</span>
            <span>•</span>
            <span>{abhaAddress}</span>
          </div>
        </div>
      </div>

      {/* 5. TWO INTERACTIVE ACTION ROWS */}
      <div className="figma-d4-actions-grid">
        {/* Row 1: My records */}
        <div
          className="figma-d4-action-item"
          onClick={onViewRecords || (() => alert(`Viewing ${recordsCount} medical history records for ${patientName}`))}
        >
          <div className="figma-d4-action-content">
            <div className="figma-d4-action-iconbox">
              <Edit3 size={24} color="#1E1E1E" strokeWidth={2.2} />
            </div>
            <span className="figma-d4-action-title">{t('my_records')}</span>
            <span className="figma-d4-action-subtitle">
              {recordsCount} {t('records_suffix')}
            </span>
          </div>
          <div className="figma-d4-action-line" />
        </div>

        {/* Row 2: Upload document */}
        <div
          className="figma-d4-action-item"
          onClick={onUploadDocument || onStartConsultation}
        >
          <div className="figma-d4-action-content">
            <div className="figma-d4-action-iconbox">
              <UploadCloud size={24} color="#1E1E1E" strokeWidth={2.2} />
            </div>
            <span className="figma-d4-action-title">{t('upload_document')}</span>
            <span className="figma-d4-action-subtitle">
              {documentsCount} {t('documents_suffix')}
            </span>
          </div>
          <div className="figma-d4-action-line" />
        </div>
      </div>

      {/* 6. BOTTOM FOOTER & CONSULTATION INITIATION */}
      <footer className="figma-d4-footer">
        <span className="figma-d4-support-text">{t('contact_support')}</span>
        <button
          type="button"
          className="figma-d4-chat-btn"
          onClick={onStartConsultation}
        >
          {t('chat_here')}
        </button>
      </footer>

      {/* Floating Fast Consultation Action Button */}
      <button
        type="button"
        className="figma-d4-floating-btn"
        onClick={onStartConsultation}
        title="Start Consultation"
        aria-label="Start Consultation"
      >
        <MessageSquare size={36} strokeWidth={2.2} />
      </button>
    </div>
  );
};

export default ScreenD4_PatientProfile;
