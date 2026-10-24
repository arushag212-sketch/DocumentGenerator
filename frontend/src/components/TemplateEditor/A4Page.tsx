import React, { useEffect, useRef, useState } from 'react';

interface A4PageProps {
  children: React.ReactNode;
  zoom?: number;
  watermarkText?: string;
  watermarkOpacity?: number;
  orientation?: 'portrait' | 'landscape';
  margins?: 'normal' | 'compact' | 'wide';
  pageBg?: string;
  pageBorder?: 'none' | 'single' | 'double';
  borderColor?: string;
  layout?: 'document' | 'certificate';
  headingColor?: string;
  textColor?: string;
  fontFamily?: string;
  headingFontFamily?: string;
  tableHeaderBg?: string;
  tableHeaderTextColor?: string;
  /** Printed letterhead, shown as on the page (not editable here) */
  header?: React.ReactNode;
  /** Printed footer line */
  footer?: React.ReactNode;
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
  borderColor = '#94a3b8',
  layout = 'document',
  headingColor = '#1e3a8a',
  textColor = '#0f172a',
  fontFamily = 'Tinos',
  headingFontFamily = 'Tinos',
  tableHeaderBg = '#1e3a8a',
  tableHeaderTextColor = '#ffffff',
  header,
  footer,
}) => {
  const sheetRef = useRef<HTMLDivElement>(null);
  const [sheetHeight, setSheetHeight] = useState<number | null>(null);

  // transform: scale() does not shrink layout size, so reserve exactly the scaled
  // box; otherwise a zoomed-out page still forces a full-width horizontal scrollbar.
  useEffect(() => {
    const el = sheetRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => setSheetHeight(el.offsetHeight));
    ro.observe(el);
    setSheetHeight(el.offsetHeight);
    return () => ro.disconnect();
  }, []);

  const isLandscape = orientation === 'landscape';
  const widthPx = isLandscape ? 1123 : 794;
  const minHeightPx = isLandscape ? 794 : 1123;

  const marginMap = {
    compact: 'px-8 py-8',
    normal: 'px-14 py-12',
    wide: 'px-20 py-16',
  };

  // The sheet edge stays a hairline; the printed page border is drawn as an inset
  // frame in the chosen colour, matching how the DOCX/PDF renders it.
  const borderStyles: React.CSSProperties = { border: '1px solid rgba(226, 232, 240, 0.8)' };
  const frameStyle: React.CSSProperties | null =
    pageBorder === 'double'
      ? { border: `7px double ${borderColor}`, inset: 18 }
      : pageBorder === 'single'
      ? { border: `2px solid ${borderColor}`, inset: 22 }
      : null;

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
      className="my-6 mx-auto"
      style={{
        width: `${widthPx * zoom}px`,
        height: sheetHeight ? `${sheetHeight * zoom}px` : undefined,
      }}
    >
      <div
        ref={sheetRef}
        className={`keep-light relative shadow-2xl rounded-sm ${marginMap[margins]} transition-[width,padding] duration-150 ${
          layout === 'certificate' ? 'cd-certificate' : ''
        }`}
        style={{
          width: `${widthPx}px`,
          minHeight: `${minHeightPx}px`,
          transform: zoom !== 1 ? `scale(${zoom})` : undefined,
          transformOrigin: 'top left',
          ...customProperties,
        }}
      >
        {frameStyle && (
          <div className="pointer-events-none absolute rounded-[2px] z-0" style={frameStyle} aria-hidden="true" />
        )}

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

        {header && <div className="relative z-10 -mt-4 mb-5 select-none">{header}</div>}

        {/* Page Content Container */}
        <div className={`relative z-10 w-full min-h-full ${footer ? 'pb-10' : ''}`}>{children}</div>

        {footer && (
          <div className="pointer-events-none absolute left-0 right-0 bottom-5 z-10 px-14 text-center select-none">{footer}</div>
        )}
      </div>
    </div>
  );
};
