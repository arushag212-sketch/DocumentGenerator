import React from 'react';
import { Palette, Type, Layout, ShieldAlert, Check, AlertTriangle, Droplets, Wand2 } from 'lucide-react';
import { THEMES, FONT_OPTIONS, calculateContrastRatio, isInkHeavy } from './themes';

export interface DesignSettings {
  theme: string;
  fontFamily: string;
  headingFontFamily: string;
  fontSize: string;
  lineHeight: string;
  headingColor: string;
  textColor: string;
  tableHeaderBg: string;
  tableHeaderTextColor: string;
  borderColor: string;
  dividerColor: string;
  pageBg: string;
  orientation: 'portrait' | 'landscape';
  margins: 'normal' | 'compact' | 'wide';
  pageBorder: 'none' | 'single' | 'double';
  /** 'certificate' uses display typography (large title/name) and spreads content down the page. */
  layout?: 'document' | 'certificate';
  watermark: string;
  watermarkOpacity: number;
}

interface DesignPanelProps {
  settings: DesignSettings;
  onChange: (newSettings: Partial<DesignSettings>) => void;
  onAutoStyle?: () => void;
}

export const DesignPanel: React.FC<DesignPanelProps> = ({ settings, onChange, onAutoStyle }) => {
  const contrastRatio = calculateContrastRatio(settings.textColor || '#0f172a', settings.pageBg || '#ffffff');
  const isLowContrast = contrastRatio < 4.5;
  const inkHeavy = isInkHeavy(settings.pageBg || '#ffffff');

  const handleThemeSelect = (themeId: string) => {
    const t = THEMES.find((item) => item.id === themeId);
    if (!t) return;
    onChange({
      theme: t.id,
      headingColor: t.heading_color,
      textColor: t.text_color,
      tableHeaderBg: t.table_header_bg,
      tableHeaderTextColor: t.table_header_text,
      borderColor: t.border_color,
      dividerColor: t.divider_color,
      fontFamily: t.body_font,
      headingFontFamily: t.heading_font,
      pageBorder: t.border_style,
      pageBg: t.page_bg,
    });
  };

  return (
    <div className="flex flex-col h-full bg-slate-50/50 overflow-y-auto p-4 space-y-5 text-xs">
      {/* AI Professional Quick-Action */}
      <div className="bg-brand-50 p-3 rounded-xl border border-brand-200/80">
        <div className="flex items-center gap-2 mb-1.5">
          <Wand2 className="w-4 h-4 text-brand-600" />
          <span className="font-bold text-slate-800 text-xs">Design Studio Copilot</span>
        </div>
        <p className="text-xs text-slate-600 mb-2.5">
          Harmonize fonts, margins, heading accents, and table borders for official institute standards.
        </p>
        <button
          onClick={onAutoStyle}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-lg shadow-sm transition"
        >
          <Wand2 className="w-3.5 h-3.5" />
          Make it Look Professional
        </button>
      </div>

      {/* Preset Themes */}
      <div>
        <label className="flex items-center gap-1.5 text-xs font-bold text-slate-700 mb-2">
          <Palette className="w-3.5 h-3.5 text-brand-600" />
          Curated Document Themes
        </label>
        <div className="grid grid-cols-2 gap-2">
          {THEMES.map((t) => {
            const isSelected = settings.theme === t.id;
            return (
              <button
                key={t.id}
                onClick={() => handleThemeSelect(t.id)}
                className={`p-2.5 rounded-lg border text-left transition flex flex-col gap-1.5 ${
                  isSelected
                    ? 'border-brand-600 bg-white ring-2 ring-brand-500/20 shadow-sm'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3.5 h-3.5 rounded-full border border-slate-300" style={{ backgroundColor: t.primary }} />
                    <div className="w-2.5 h-2.5 rounded-full border border-slate-300" style={{ backgroundColor: t.accent }} />
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-brand-600" />}
                </div>
                <span className="font-semibold text-slate-800 text-xs truncate">{t.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Typography */}
      <div>
        <label className="flex items-center gap-1.5 text-xs font-bold text-slate-700 mb-2">
          <Type className="w-3.5 h-3.5 text-brand-600" />
          Typography & Fonts
        </label>
        <div className="space-y-2.5">
          <div>
            <span className="block text-xs font-medium text-slate-600 mb-1">Body Font</span>
            <select
              value={settings.fontFamily}
              onChange={(e) => onChange({ fontFamily: e.target.value })}
              className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
            >
              {FONT_OPTIONS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} ({f.group})
                </option>
              ))}
            </select>
          </div>

          <div>
            <span className="block text-xs font-medium text-slate-600 mb-1">Heading Font</span>
            <select
              value={settings.headingFontFamily || settings.fontFamily}
              onChange={(e) => onChange({ headingFontFamily: e.target.value })}
              className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
            >
              {FONT_OPTIONS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} ({f.group})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-xs font-medium text-slate-600 mb-1">Base Size</span>
              <select
                value={settings.fontSize}
                onChange={(e) => onChange({ fontSize: e.target.value })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
              >
                <option value="sm">10pt (Compact)</option>
                <option value="base">11pt (Standard)</option>
                <option value="lg">12pt (Spacious)</option>
              </select>
            </div>

            <div>
              <span className="block text-xs font-medium text-slate-600 mb-1">Line Spacing</span>
              <select
                value={settings.lineHeight}
                onChange={(e) => onChange({ lineHeight: e.target.value })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
              >
                <option value="tight">1.15 (Single)</option>
                <option value="normal">1.35 (Official)</option>
                <option value="relaxed">1.60 (Draft)</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Colors & Palette Customization */}
      <div>
        <label className="flex items-center gap-1.5 text-xs font-bold text-slate-700 mb-2">
          <Droplets className="w-3.5 h-3.5 text-brand-600" />
          Color Palette
        </label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="block text-[11px] text-slate-500 mb-1">Headings Color</span>
            <div className="flex items-center gap-1.5 bg-white border border-slate-300 rounded-lg p-1.5">
              <input
                type="color"
                value={settings.headingColor || '#1e3a8a'}
                onChange={(e) => onChange({ headingColor: e.target.value })}
                className="w-5 h-5 rounded cursor-pointer border-0 p-0"
              />
              <span className="text-[11px] text-slate-600 font-mono">{settings.headingColor || '#1e3a8a'}</span>
            </div>
          </div>

          <div>
            <span className="block text-[11px] text-slate-500 mb-1">Text Color</span>
            <div className="flex items-center gap-1.5 bg-white border border-slate-300 rounded-lg p-1.5">
              <input
                type="color"
                value={settings.textColor || '#0f172a'}
                onChange={(e) => onChange({ textColor: e.target.value })}
                className="w-5 h-5 rounded cursor-pointer border-0 p-0"
              />
              <span className="text-[11px] text-slate-600 font-mono">{settings.textColor || '#0f172a'}</span>
            </div>
          </div>

          <div>
            <span className="block text-[11px] text-slate-500 mb-1">Table Header Bg</span>
            <div className="flex items-center gap-1.5 bg-white border border-slate-300 rounded-lg p-1.5">
              <input
                type="color"
                value={settings.tableHeaderBg || '#1e3a8a'}
                onChange={(e) => onChange({ tableHeaderBg: e.target.value })}
                className="w-5 h-5 rounded cursor-pointer border-0 p-0"
              />
              <span className="text-[11px] text-slate-600 font-mono">{settings.tableHeaderBg || '#1e3a8a'}</span>
            </div>
          </div>

          <div>
            <span className="block text-[11px] text-slate-500 mb-1">Page Background</span>
            <div className="flex items-center gap-1.5 bg-white border border-slate-300 rounded-lg p-1.5">
              <input
                type="color"
                value={settings.pageBg || '#ffffff'}
                onChange={(e) => onChange({ pageBg: e.target.value })}
                className="w-5 h-5 rounded cursor-pointer border-0 p-0"
              />
              <span className="text-[11px] text-slate-600 font-mono">{settings.pageBg || '#ffffff'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Contrast & Ink Guard */}
      <div className={`p-3 rounded-lg border text-xs space-y-1.5 ${
        isLowContrast || inkHeavy ? 'bg-amber-50 border-amber-200 text-amber-900' : 'bg-emerald-50 border-emerald-200 text-emerald-900'
      }`}>
        <div className="flex items-center justify-between font-bold">
          <div className="flex items-center gap-1.5">
            {isLowContrast || inkHeavy ? (
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            ) : (
              <ShieldAlert className="w-4 h-4 text-emerald-600 shrink-0" />
            )}
            <span>WCAG Contrast: {contrastRatio.toFixed(1)}:1</span>
          </div>
          <span className={`px-1.5 py-0.5 rounded text-[11px] font-bold ${
            isLowContrast ? 'bg-amber-200 text-amber-900' : 'bg-emerald-200 text-emerald-900'
          }`}>
            {isLowContrast ? 'Low Contrast' : 'AA Pass'}
          </span>
        </div>
        {isLowContrast && (
          <p className="text-[11px] text-amber-800">
            Warning: Text contrast is below 4.5:1. Document text may be difficult to read when printed.
          </p>
        )}
        {inkHeavy && (
          <p className="text-[11px] text-amber-800 font-medium">
            Caution: Dark background will consume significant ink and toner. Light backgrounds are recommended.
          </p>
        )}
        {!isLowContrast && !inkHeavy && (
          <p className="text-[11px] text-emerald-700">
            Optimal print contrast. SVNIT letterhead slot remains locked and protected.
          </p>
        )}
      </div>

      {/* Page Setup & Layout */}
      <div>
        <label className="flex items-center gap-1.5 text-xs font-bold text-slate-700 mb-2">
          <Layout className="w-3.5 h-3.5 text-brand-600" />
          Page Setup & Layout
        </label>
        <div className="space-y-2.5">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-xs font-medium text-slate-600 mb-1">Orientation</span>
              <select
                value={settings.orientation}
                onChange={(e) => onChange({ orientation: e.target.value as any })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
              >
                <option value="portrait">Portrait (A4)</option>
                <option value="landscape">Landscape (A4)</option>
              </select>
            </div>

            <div>
              <span className="block text-xs font-medium text-slate-600 mb-1">Margins</span>
              <select
                value={settings.margins}
                onChange={(e) => onChange({ margins: e.target.value as any })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
              >
                <option value="compact">Compact (15mm)</option>
                <option value="normal">Normal (25mm)</option>
                <option value="wide">Wide (32mm)</option>
              </select>
            </div>
          </div>

          <div>
            <span className="block text-xs font-medium text-slate-600 mb-1">Layout</span>
            <div className="grid grid-cols-2 gap-1.5" role="radiogroup" aria-label="Page layout">
              {(['document', 'certificate'] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  role="radio"
                  aria-checked={(settings.layout || 'document') === l}
                  onClick={() =>
                    onChange(
                      l === 'certificate'
                        ? { layout: l, orientation: 'landscape', pageBorder: 'double', margins: 'wide' }
                        : { layout: l }
                    )
                  }
                  className={`px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition ${
                    (settings.layout || 'document') === l
                      ? 'border-brand-600 bg-brand-50 text-brand-700'
                      : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {l === 'document' ? 'Document / Letter' : 'Certificate / Award'}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-xs font-medium text-slate-600 mb-1">Page Border</span>
              <select
                value={settings.pageBorder || 'none'}
                onChange={(e) => onChange({ pageBorder: e.target.value as any })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
              >
                <option value="none">None</option>
                <option value="single">Single Line</option>
                <option value="double">Double Border (Certificate)</option>
              </select>
            </div>

            <div>
              <span className="block text-xs font-medium text-slate-600 mb-1">Watermark Opacity</span>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0.05"
                  max="0.4"
                  step="0.05"
                  value={settings.watermarkOpacity ?? 0.15}
                  onChange={(e) => onChange({ watermarkOpacity: parseFloat(e.target.value) })}
                  className="w-full accent-brand-600 cursor-pointer"
                />
                <span className="text-[11px] text-slate-500 w-8 text-right font-mono">
                  {Math.round((settings.watermarkOpacity ?? 0.15) * 100)}%
                </span>
              </div>
            </div>
          </div>

          <div>
            <span className="block text-xs font-medium text-slate-600 mb-1">Document Watermark</span>
            <input
              type="text"
              value={settings.watermark || ''}
              onChange={(e) => onChange({ watermark: e.target.value })}
              placeholder="e.g. DRAFT, CONFIDENTIAL, or SAMPLE"
              className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
            >
            </input>
          </div>
        </div>
      </div>
    </div>
  );
};
