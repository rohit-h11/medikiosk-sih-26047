import React, { useState, useEffect } from 'react';
import { Upload, Camera, Loader2, CheckCircle, AlertTriangle, FileImage } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

export const MobileUploadPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session');
  
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const getApiBase = () => '/api/v1';

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      
      const objectUrl = URL.createObjectURL(selectedFile);
      setPreview(objectUrl);
      setStatus('idle');
    }
  };

  const handleUpload = async () => {
    if (!file || !sessionId) return;

    setStatus('uploading');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const API_BASE = getApiBase();
      const res = await fetch(`${API_BASE}/mobile-upload/session/${sessionId}/file`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        const detailStr = typeof errorData.detail === 'string' 
            ? errorData.detail 
            : JSON.stringify(errorData.detail || 'Upload failed');
        throw new Error(detailStr);
      }

      setStatus('success');
    } catch (err: any) {
      console.error('Upload error:', err);
      setStatus('error');
      setErrorMessage(err.message || 'Failed to connect to server');
    }
  };

  if (!sessionId) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <AlertTriangle color="#ef4444" size={48} style={{ marginBottom: '16px' }} />
          <h2 style={styles.title}>Invalid Link</h2>
          <p style={styles.text}>This link is missing a session ID. Please scan the QR code from the MediKiosk screen again.</p>
        </div>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <CheckCircle color="#10b981" size={64} style={{ marginBottom: '24px' }} />
          <h2 style={styles.title}>Upload Complete!</h2>
          <p style={styles.text}>Your document has been sent successfully. Please look at the MediKiosk screen to see the results.</p>
          <p style={styles.subtext}>You can now close this tab.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.headerTitle}>Upload Document</h1>
        <p style={styles.headerText}>MediKiosk Secure Upload</p>
      </div>

      <div style={styles.content}>
        {!preview ? (
          <div style={styles.uploadArea}>
            {/* Single Upload Option (Figma Design) */}
            <label style={styles.optionBtn}>
              <Upload size={28} color="#2563eb" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '18px', fontWeight: '600', color: '#0f172a' }}>Upload from this device</span>
                <span style={{ fontSize: '14px', color: '#64748b', fontWeight: 'normal' }}>Select a document or take a photo</span>
              </div>
              <input 
                type="file" 
                accept="image/*,application/pdf" 
                onChange={handleFileSelect} 
                style={{ display: 'none' }} 
              />
            </label>
          </div>
        ) : (
          <div style={styles.previewArea}>
            <img src={preview} alt="Selected document" style={styles.previewImage} />
            
            <div style={styles.actionButtons}>
              <button 
                onClick={() => { setFile(null); setPreview(null); setStatus('idle'); }} 
                style={styles.retakeBtn}
                disabled={status === 'uploading'}
              >
                Retake
              </button>
              
              <button 
                onClick={handleUpload} 
                style={styles.uploadBtn}
                disabled={status === 'uploading'}
              >
                {status === 'uploading' ? (
                  <>
                    <Loader2 className="animate-spin" size={20} />
                    Processing...
                  </>
                ) : (
                  <>
                    <Upload size={20} />
                    Upload
                  </>
                )}
              </button>
            </div>

            {status === 'error' && (
              <div style={styles.errorBox}>
                <AlertTriangle size={16} style={{ marginRight: '8px' }} />
                <span>{errorMessage}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    fontFamily: 'Inter, system-ui, sans-serif',
    backgroundColor: '#f8fafc',
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    padding: '20px',
  },
  header: {
    textAlign: 'center' as const,
    marginTop: '40px',
    marginBottom: '32px',
  },
  headerTitle: {
    fontSize: '24px',
    fontWeight: '700',
    color: '#0f172a',
    margin: '0 0 8px 0',
  },
  headerText: {
    fontSize: '14px',
    color: '#64748b',
    margin: 0,
  },
  content: {
    width: '100%',
    maxWidth: '400px',
    backgroundColor: '#ffffff',
    borderRadius: '16px',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    padding: '24px',
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: '16px',
    padding: '40px 24px',
    textAlign: 'center' as const,
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    width: '100%',
    maxWidth: '400px',
    marginTop: '60px',
  },
  title: {
    fontSize: '20px',
    fontWeight: '600',
    color: '#0f172a',
    margin: '0 0 12px 0',
  },
  text: {
    fontSize: '15px',
    color: '#475569',
    lineHeight: '1.5',
    margin: '0 0 8px 0',
  },
  subtext: {
    fontSize: '13px',
    color: '#94a3b8',
    margin: 0,
  },
  uploadArea: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '16px',
  },
  uploadOptions: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '16px',
  },
  optionBtn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    backgroundColor: '#f1f5f9',
    border: '2px dashed #cbd5e1',
    borderRadius: '12px',
    padding: '24px',
    color: '#334155',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  previewArea: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '20px',
  },
  previewImage: {
    width: '100%',
    height: 'auto',
    maxHeight: '400px',
    objectFit: 'contain' as const,
    borderRadius: '8px',
    backgroundColor: '#f1f5f9',
  },
  actionButtons: {
    display: 'flex',
    gap: '12px',
  },
  retakeBtn: {
    flex: 1,
    padding: '14px',
    backgroundColor: '#f1f5f9',
    border: 'none',
    borderRadius: '8px',
    color: '#475569',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
  },
  uploadBtn: {
    flex: 2,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    padding: '14px',
    backgroundColor: '#2563eb',
    border: 'none',
    borderRadius: '8px',
    color: '#ffffff',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
  },
  errorBox: {
    display: 'flex',
    alignItems: 'center',
    padding: '12px',
    backgroundColor: '#fef2f2',
    color: '#b91c1c',
    borderRadius: '8px',
    fontSize: '14px',
  }
};
