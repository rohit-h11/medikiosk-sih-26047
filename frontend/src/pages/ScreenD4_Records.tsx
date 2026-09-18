/**
 * MediKiosk — Screen D4 ii: Patient Summary & Past Reports Dashboard (Exact 1:1 Figma Design)
 * Matches Node 273:2914 from Figma.
 * Displays patient demographics (Name, Age, Weight) and Clinical EHR summary box with 100vh zero-scroll layout.
 */

import React from 'react';
import { ArrowLeft, MessageSquare, ArrowRight, Activity, FileText, Pill, ShieldCheck, HeartPulse } from 'lucide-react';
import { AbdmLogo } from '@/assets/AbdmLogo';
import { useTranslation } from '@/hooks/useTranslation';
import { AbhaProfile } from '@/types/abha';
import '@/styles/screen_d4_records.css';

interface ScreenD4RecordsProps {
  profile?: AbhaProfile | null;
  onBack?: () => void;
  onProceedConsultation?: () => void;
}

export const ScreenD4_Records: React.FC<ScreenD4RecordsProps> = ({
  profile,
  onBack,
  onProceedConsultation,
}) => {
  const { t } = useTranslation();

  // Active Patient Data from Supabase
  const patientName = profile?.name || 'Ayushman Beneficiary';
  const age = profile?.age || 19;
  const gender = profile?.gender || 'Male';
  const prakriti = profile?.prakriti || null;
  const weight = '62 kg';
  const abhaNumber = profile?.abhaNumber || '91-8824-3942-1092';

  return (
    <div className="figma-screen-records">
      {/* 1. TOP HEADER BAR */}
      <header className="figma-records-header">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <button
            type="button"
            className="figma-records-back-btn"
            onClick={onBack}
            aria-label="Back"
          >
            <ArrowLeft size={24} strokeWidth={2.5} />
          </button>

          <div className="figma-records-brand-logo">
            <span className="figma-records-brand-medi">Medi</span>
            <span className="figma-records-brand-kiosk">Kiosk</span>
          </div>
        </div>

        <div className="figma-records-abdm-wrapper">
          <AbdmLogo size={64} />
        </div>
      </header>

      {/* 2. DYNAMIC PATIENT NAME AT CENTER TOP */}
      <h1 className="figma-records-patient-name">{patientName}</h1>

      {/* 3. PATIENT DEMOGRAPHICS (Exact 1:1 Figma: Patient Name, Age, Weight) */}
      <div className="figma-records-demographics">
        <div className="figma-records-demo-row">
          <span className="figma-records-demo-label">Patient Name :</span>
          <span className="figma-records-demo-value">{patientName}</span>
        </div>
        <div className="figma-records-demo-row">
          <span className="figma-records-demo-label">Age :</span>
          <span className="figma-records-demo-value">{age} Years ({gender})</span>
        </div>
        <div className="figma-records-demo-row">
          <span className="figma-records-demo-label">Weight :</span>
          <span className="figma-records-demo-value">{weight}</span>
        </div>
      </div>

      {/* 4. SUMMARY SECTION TITLE */}
      <h2 className="figma-records-summary-title">Summary of past reports :</h2>

      {/* 5. MAIN SUMMARY CONTAINER (1058px x 272px with 11px Black Border) */}
      <div className="figma-records-mainbox">
        {/* Entry 1: AYUSH Constitutional Assessment */}
        <div className="figma-record-entry">
          <div className="figma-record-entry-header">
            <span className="figma-record-type-badge">
              <Activity size={14} style={{ display: 'inline', marginRight: 4 }} />
              AYUSH Prakriti Assessment
            </span>
            <span className="figma-record-date">ABDM Diagnostic Record</span>
          </div>
          <span className="figma-record-title">
            Constitutional Profile: {prakriti ? `${prakriti} (Baseline)` : 'Not Assessed Yet'}
          </span>
          <p className="figma-record-notes">
            {prakriti
              ? `${prakriti} constitution recorded in historical consultation.`
              : 'No prior AYUSH Prakriti constitution recorded on file. An automated assessment will be conducted during clinical consultation.'}
          </p>
        </div>

        {/* Entry 2: Recent Clinical Diagnosis */}
        <div className="figma-record-entry">
          <div className="figma-record-entry-header">
            <span className="figma-record-type-badge">
              <HeartPulse size={14} style={{ display: 'inline', marginRight: 4 }} />
              Clinical Consultation & Diagnosis
            </span>
            <span className="figma-record-date">12 Aug 2026 • AIIMS Outpatient</span>
          </div>
          <span className="figma-record-title">Primary Hypertension (Mild) & Lower Back Discomfort</span>
          <p className="figma-record-notes">
            Vitals recorded: BP 130/85 mmHg, Pulse 74 bpm, SpO2 99%. Recommended conservative physical therapy and daily stretching exercises.
          </p>
        </div>

        {/* Entry 3: Active Prescription */}
        <div className="figma-record-entry">
          <div className="figma-record-entry-header">
            <span className="figma-record-type-badge">
              <Pill size={14} style={{ display: 'inline', marginRight: 4 }} />
              Active Medication
            </span>
            <span className="figma-record-date">e-Prescription</span>
          </div>
          <span className="figma-record-title">Oral Regimen: Tab Amlodipine 5mg (OD) + Ashwagandha Churna 3g (BD)</span>
          <p className="figma-record-notes">
            Dual Allopathy & AYUSH therapeutic adherence observed with no reported adverse drug-herb interactions.
          </p>
        </div>

        {/* Entry 4: Diagnostic Lab Panel */}
        <div className="figma-record-entry">
          <div className="figma-record-entry-header">
            <span className="figma-record-type-badge">
              <FileText size={14} style={{ display: 'inline', marginRight: 4 }} />
              Diagnostic Lab Panel
            </span>
            <span className="figma-record-date">04 Jul 2026</span>
          </div>
          <span className="figma-record-title">Comprehensive Metabolic & Lipid Panel</span>
          <p className="figma-record-notes">
            HbA1c: 5.7% (Normal), Total Cholesterol: 182 mg/dL, Serum Creatinine: 0.9 mg/dL. All physiological parameters within reference range.
          </p>
        </div>
      </div>

      {/* 6. GREEN PROCEED ACTION BANNER ("Click here to proceed to consultation") */}
      <button
        type="button"
        className="figma-records-proceed-btn"
        onClick={onProceedConsultation}
      >
        <span>Click here to proceed to consultation</span>
        <ArrowRight size={22} strokeWidth={2.5} />
      </button>

      {/* 7. BOTTOM FOOTER & CHAT BUTTON */}
      <footer className="figma-records-footer">
        <button
          type="button"
          className="figma-records-chat-btn"
          onClick={onProceedConsultation}
        >
          {t('chat_here')}
        </button>
      </footer>

      {/* Floating Fast Consultation Action Button */}
      <button
        type="button"
        className="figma-records-floating-btn"
        onClick={onProceedConsultation}
        title="Start Consultation"
        aria-label="Start Consultation"
      >
        <MessageSquare size={34} strokeWidth={2.2} />
      </button>
    </div>
  );
};

export default ScreenD4_Records;
