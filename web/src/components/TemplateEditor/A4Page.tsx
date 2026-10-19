import React from 'react';

interface A4PageProps {
  children: React.ReactNode;
  zoom?: number;
  watermarkText?: string;
  watermarkOpacity?: number;
  orientation?: 'portrait' | 'landscape';
  margins?: 'normal' | 'compact' | 'wide';
  pageBg?: string;
  pageBorder?: 'none' | 'single' | 'double';
  headingColor?: string;
  textColor?: string;
  fontFamily?: string;
  headingFontFamily?: string;
  tableHeaderBg?: string;
  tableHeaderTextColor?: string;
}

export const A4Page: React.FC<A4PageProps> = ({
  children,
  zoom = 1,
  watermarkText,
  watermarkOpacity = 0.15,
  orientation = 'portrait',
  margins = 'normal',
  pageBg = '#ffffff',
  pageBorder = 'none',
  headingColor = '#1e3a8a',
  textColor = '#0f172a',
  fontFamily = 'Tinos',
  headingFontFamily = 'Tinos',
  tableHeaderBg = '#1e3a8a',
  tableHeaderTextColor = '#ffffff',
}) => {
  const isLandscape = orientation === 'landscape';
  const widthPx = isLandscape ? 1123 : 794;
  const minHeightPx = isLandscape ? 794 : 1123;

  const marginMap = {
    compact: 'px-8 py-8',
    normal: 'px-14 py-12',
    wide: 'px-20 py-16',
  };

  const borderStyles: React.CSSProperties =
    pageBorder === 'double'
      ? { border: '4px double #94a3b8' }
      : pageBorder === 'single'
      ? { border: '1px solid #cbd5e1' }
      : { border: '1px solid rgba(226, 232, 240, 0.8)' };

  const customProperties = {
    '--cd-heading-color': headingColor,
    '--cd-text-color': textColor,
    '--cd-body-font': fontFamily,
    '--cd-heading-font': headingFontFamily,
    '--cd-table-header-bg': tableHeaderBg,
    '--cd-table-header-text': tableHeaderTextColor,
    backgroundColor: pageBg,
    color: textColor,
    fontFamily: `${fontFamily}, system-ui, sans-serif`,
    ...borderStyles,
  } as React.CSSProperties;

  return (
    <div
      className="flex justify-center my-6 transition-transform origin-top duration-150"
      style={{
        transform: zoom !== 1 ? `scale(${zoom})` : undefined,
      }}
    >
      <div
        className={`relative shadow-2xl rounded-sm ${marginMap[margins]} transition-all`}
        style={{
          width: `${widthPx}px`,
          minHeight: `${minHeightPx}px`,
          ...customProperties,
        }}
      >
        {/* Document Watermark */}
        {watermarkText && watermarkText.trim() && (
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden select-none z-0"
            aria-hidden="true"
          >
            <span
              className="font-black uppercase text-7xl tracking-widest -rotate-45 transform text-slate-800"
              style={{
                fontSize: '6.5rem',
                opacity: watermarkOpacity,
              }}
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
