import React from 'react';

interface A4PageProps {
  children: React.ReactNode;
  zoom?: number;
  watermarkText?: string;
  orientation?: 'portrait' | 'landscape';
  margins?: 'normal' | 'compact' | 'wide';
}

export const A4Page: React.FC<A4PageProps> = ({
  children,
  zoom = 1,
  watermarkText,
  orientation = 'portrait',
  margins = 'normal',
}) => {
  // Standard A4 dimensions in CSS pixels at 96 DPI:
  // Portrait: 794px x 1123px (~210mm x 297mm)
  // Landscape: 1123px x 794px
  const isLandscape = orientation === 'landscape';
  const widthPx = isLandscape ? 1123 : 794;
  const minHeightPx = isLandscape ? 794 : 1123;

  const marginMap = {
    compact: 'px-8 py-8',
    normal: 'px-14 py-12',
    wide: 'px-20 py-16',
  };

  return (
    <div
      className="flex justify-center my-6 transition-transform origin-top duration-150"
      style={{
        transform: zoom !== 1 ? `scale(${zoom})` : undefined,
      }}
    >
      <div
        className={`relative bg-white text-slate-900 shadow-2xl rounded-sm border border-slate-200/80 ${marginMap[margins]} transition-all`}
        style={{
          width: `${widthPx}px`,
          minHeight: `${minHeightPx}px`,
        }}
      >
        {/* Subtle Watermark */}
        {watermarkText && (
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden select-none z-0"
            aria-hidden="true"
          >
            <span
              className="text-slate-900/[0.04] font-black uppercase text-7xl tracking-widest -rotate-45 transform"
              style={{ fontSize: '7rem' }}
            >
              {watermarkText}
            </span>
          </div>
        )}

        {/* Page Content Container */}
        <div className="relative z-10 w-full min-h-full">{children}</div>
      </div>
    </div>
  );
};
