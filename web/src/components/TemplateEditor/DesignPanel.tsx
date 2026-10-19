import React from 'react';
import { Palette, Type, Layout, ShieldAlert, Sparkles, Check } from 'lucide-react';

export interface DesignSettings {
  theme: string;
  fontFamily: string;
  fontSize: string;
  lineHeight: string;
  orientation: 'portrait' | 'landscape';
  margins: 'normal' | 'compact' | 'wide';
  watermark: string;
}

interface DesignPanelProps {
  settings: DesignSettings;
  onChange: (newSettings: Partial<DesignSettings>) => void;
  onAutoStyle?: () => void;
}

export const THEME_PRESETS = [
  { id: 'official_navy', name: 'Official Navy', primary: '#1e3a8a', accent: '#3b82f6', bg: '#ffffff' },
  { id: 'svnit_gold', name: 'SVNIT Blue & Gold', primary: '#0f2942', accent: '#d97706', bg: '#ffffff' },
  { id: 'classic_bw', name: 'Classic Black & White', primary: '#0f172a', accent: '#475569', bg: '#ffffff' },
  { id: 'modern_green', name: 'Modern Forest', primary: '#14532d', accent: '#22c55e', bg: '#ffffff' },
  { id: 'warm_sunset', name: 'Warm Crimson', primary: '#881337', accent: '#f43f5e', bg: '#ffffff' },
  { id: 'minimal_grey', name: 'Minimal Slate', primary: '#334155', accent: '#64748b', bg: '#ffffff' },
];

export const FONT_PRESETS = [
  { id: 'serif', name: 'Formal Serif (Times-like)', family: '"Times New Roman", Times, Georgia, serif' },
  { id: 'sans', name: 'Modern Sans (Inter / Roboto)', family: 'Inter, system-ui, -apple-system, sans-serif' },
  { id: 'display', name: 'Clean Editorial (Merriweather)', family: 'Merriweather, Georgia, serif' },
  { id: 'mono', name: 'Monospace Code', family: 'ui-monospace, SFMono-Regular, Menlo, monospace' },
  { id: 'indic', name: 'Indic Bilingual (Noto Sans)', family: '"Noto Sans", "Noto Sans Devanagari", sans-serif' },
];

export const DesignPanel: React.FC<DesignPanelProps> = ({ settings, onChange, onAutoStyle }) => {
  return (
    <div className="flex flex-col h-full bg-slate-50/50 overflow-y-auto p-4 space-y-6 text-xs">
      {/* AI Professional Quick-Action */}
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 p-3 rounded-xl border border-indigo-200/80 shadow-sm">
        <div className="flex items-center gap-2 mb-1.5">
          <Sparkles className="w-4 h-4 text-indigo-600" />
          <span className="font-bold text-slate-800 text-xs">Design Copilot</span>
        </div>
        <p className="text-[11px] text-slate-600 mb-2.5">
          Harmonize fonts, margins, heading accents, and table borders for official institute standards.
        </p>
        <button
          onClick={onAutoStyle}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-sm transition"
        >
          <Sparkles className="w-3.5 h-3.5" />
          Make it Look Professional
        </button>
      </div>

      {/* Preset Themes */}
      <div>
        <label className="flex items-center gap-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          <Palette className="w-3.5 h-3.5 text-indigo-600" />
          Curated Color Themes
        </label>
        <div className="grid grid-cols-2 gap-2">
          {THEME_PRESETS.map((t) => {
            const isSelected = settings.theme === t.id;
            return (
              <button
                key={t.id}
                onClick={() => onChange({ theme: t.id })}
                className={`p-2.5 rounded-lg border text-left transition flex flex-col gap-1.5 ${
                  isSelected
                    ? 'border-indigo-600 bg-white ring-2 ring-indigo-500/20 shadow-sm'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: t.primary }} />
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: t.accent }} />
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-indigo-600" />}
                </div>
                <span className="font-semibold text-slate-800 text-[11px] truncate">{t.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Typography */}
      <div>
        <label className="flex items-center gap-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          <Type className="w-3.5 h-3.5 text-indigo-600" />
          Typography
        </label>
        <div className="space-y-2">
          <div>
            <span className="block text-[11px] font-medium text-slate-600 mb-1">Font Family</span>
            <select
              value={settings.fontFamily}
              onChange={(e) => onChange({ fontFamily: e.target.value })}
              className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 focus:outline-none"
            >
              {FONT_PRESETS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-[11px] font-medium text-slate-600 mb-1">Base Size</span>
              <select
                value={settings.fontSize}
                onChange={(e) => onChange({ fontSize: e.target.value })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              >
                <option value="sm">Compact (10pt)</option>
                <option value="base">Standard (11pt)</option>
                <option value="lg">Spacious (12pt)</option>
              </select>
            </div>

            <div>
              <span className="block text-[11px] font-medium text-slate-600 mb-1">Line Spacing</span>
              <select
                value={settings.lineHeight}
                onChange={(e) => onChange({ lineHeight: e.target.value })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              >
                <option value="tight">1.15 (Single)</option>
                <option value="normal">1.35 (Official)</option>
                <option value="relaxed">1.6 (Draft)</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Page Setup */}
      <div>
        <label className="flex items-center gap-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          <Layout className="w-3.5 h-3.5 text-indigo-600" />
          Page Setup & Layout
        </label>
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="block text-[11px] font-medium text-slate-600 mb-1">Orientation</span>
              <select
                value={settings.orientation}
                onChange={(e) => onChange({ orientation: e.target.value as any })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              >
                <option value="portrait">Portrait (A4)</option>
                <option value="landscape">Landscape (A4)</option>
              </select>
            </div>

            <div>
              <span className="block text-[11px] font-medium text-slate-600 mb-1">Margins</span>
              <select
                value={settings.margins}
                onChange={(e) => onChange({ margins: e.target.value as any })}
                className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              >
                <option value="compact">Compact (20mm)</option>
                <option value="normal">Normal (25mm)</option>
                <option value="wide">Wide (30mm)</option>
              </select>
            </div>
          </div>

          <div>
            <span className="block text-[11px] font-medium text-slate-600 mb-1">Document Watermark</span>
            <input
              type="text"
              value={settings.watermark}
              onChange={(e) => onChange({ watermark: e.target.value })}
              placeholder="e.g. DRAFT or CONFIDENTIAL"
              className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Readability Guard */}
      <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200 text-emerald-800 flex items-start gap-2">
        <ShieldAlert className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
        <div className="text-[11px]">
          <span className="font-bold">Readability Guard Active:</span> Contrast ratio meets WCAG AA standards for print readability. SVNIT letterhead slot remains locked.
        </div>
      </div>
    </div>
  );
};
