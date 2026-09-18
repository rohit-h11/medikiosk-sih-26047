import React from 'react';

export const AbdmLogo: React.FC<{ size?: number; className?: string }> = ({ size = 80, className = '' }) => {
  return (
    <div
      className={className}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}
    >
      <svg width={size} height={size} viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Outer Circular Rings */}
        <circle cx="50" cy="50" r="46" stroke="#EA580C" strokeWidth="2" strokeDasharray="3 3" />
        <circle cx="50" cy="50" r="42" stroke="#16A34A" strokeWidth="1.5" />
        
        {/* Signal Waves */}
        <path d="M 22 50 A 28 28 0 0 1 78 50" stroke="#000000" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        <path d="M 28 50 A 22 22 0 0 1 72 50" stroke="#000000" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        <path d="M 34 50 A 16 16 0 0 1 66 50" stroke="#000000" strokeWidth="2.5" strokeLinecap="round" fill="none" />

        {/* Lotus Petals */}
        <path d="M 50 25 C 44 38 42 46 50 54 C 58 46 56 38 50 25 Z" fill="#16A34A" />
        <path d="M 38 32 C 38 42 42 48 50 54 C 44 48 40 42 38 32 Z" fill="#15803D" />
        <path d="M 62 32 C 62 42 58 48 50 54 C 56 48 60 42 62 32 Z" fill="#15803D" />

        {/* Meditating Figure Base */}
        <circle cx="50" cy="46" r="3.5" fill="#EA580C" />
        <path d="M 43 56 C 43 51 57 51 57 56 Z" fill="#EA580C" />

        {/* Text Arc Emulation */}
        <text x="50" y="68" textAnchor="middle" fontSize="5.5" fontWeight="800" fill="#EA580C" fontFamily="sans-serif">
          Ayushman Bharat
        </text>
        <text x="50" y="75" textAnchor="middle" fontSize="6" fontWeight="900" fill="#000000" fontFamily="sans-serif">
          Digital Mission
        </text>
        <text x="50" y="81" textAnchor="middle" fontSize="4" fontWeight="600" fill="#16A34A" fontFamily="sans-serif">
          Building Digital Health Ecosystem
        </text>
      </svg>
    </div>
  );
};
