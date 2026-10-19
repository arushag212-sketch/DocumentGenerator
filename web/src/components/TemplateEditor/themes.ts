/**
 * Design Themes, Font Catalog & Contrast Utilities for ClubDocs Studio.
 */

export interface ThemePreset {
  id: string;
  name: string;
  category: 'formal' | 'institute' | 'minimal' | 'modern' | 'vibrant';
  primary: string;
  secondary: string;
  accent: string;
  heading_color: string;
  text_color: string;
  page_bg: string;
  table_header_bg: string;
  table_header_text: string;
  border_color: string;
  divider_color: string;
  heading_font: string;
  body_font: string;
  line_height: number;
  border_style: 'none' | 'single' | 'double';
}

export const THEMES: ThemePreset[] = [
  {
    id: 'official_navy',
    name: 'Official Navy',
    category: 'formal',
    primary: '#1e3a8a',
    secondary: '#1d4ed8',
    accent: '#3b82f6',
    heading_color: '#1e3a8a',
    text_color: '#0f172a',
    page_bg: '#ffffff',
    table_header_bg: '#1e3a8a',
    table_header_text: '#ffffff',
    border_color: '#cbd5e1',
    divider_color: '#3b82f6',
    heading_font: 'Tinos',
    body_font: 'Tinos',
    line_height: 1.35,
    border_style: 'single',
  },
  {
    id: 'svnit_gold',
    name: 'SVNIT Blue & Gold',
    category: 'institute',
    primary: '#003366',
    secondary: '#0f2942',
    accent: '#d97706',
    heading_color: '#003366',
    text_color: '#0f172a',
    page_bg: '#ffffff',
    table_header_bg: '#003366',
    table_header_text: '#ffffff',
    border_color: '#d97706',
    divider_color: '#d97706',
    heading_font: 'Open Sans',
    body_font: 'Open Sans',
    line_height: 1.35,
    border_style: 'single',
  },
  {
    id: 'classic_bw',
    name: 'Classic Black & White',
    category: 'minimal',
    primary: '#0f172a',
    secondary: '#334155',
    accent: '#475569',
    heading_color: '#0f172a',
    text_color: '#0f172a',
    page_bg: '#ffffff',
    table_header_bg: '#f1f5f9',
    table_header_text: '#0f172a',
    border_color: '#94a3b8',
    divider_color: '#94a3b8',
    heading_font: 'Tinos',
    body_font: 'Tinos',
    line_height: 1.3,
    border_style: 'single',
  },
  {
    id: 'modern_green',
    name: 'Modern Green',
    category: 'modern',
    primary: '#065f46',
    secondary: '#047857',
    accent: '#10b981',
    heading_color: '#065f46',
    text_color: '#0f172a',
    page_bg: '#ffffff',
    table_header_bg: '#065f46',
    table_header_text: '#ffffff',
    border_color: '#a7f3d0',
    divider_color: '#10b981',
    heading_font: 'Roboto',
    body_font: 'Roboto',
    line_height: 1.35,
    border_style: 'single',
  },
  {
    id: 'warm_sunset',
    name: 'Warm Sunset',
    category: 'vibrant',
    primary: '#9a3412',
    secondary: '#c2410c',
    accent: '#ea580c',
    heading_color: '#9a3412',
    text_color: '#1c1917',
    page_bg: '#ffffff',
    table_header_bg: '#9a3412',
    table_header_text: '#ffffff',
    border_color: '#fed7aa',
    divider_color: '#ea580c',
    heading_font: 'Montserrat',
    body_font: 'Open Sans',
    line_height: 1.35,
    border_style: 'single',
  },
  {
    id: 'minimal_grey',
    name: 'Minimal Grey',
    category: 'minimal',
    primary: '#334155',
    secondary: '#475569',
    accent: '#94a3b8',
    heading_color: '#334155',
    text_color: '#1e293b',
    page_bg: '#ffffff',
    table_header_bg: '#e2e8f0',
    table_header_text: '#1e293b',
    border_color: '#cbd5e1',
    divider_color: '#94a3b8',
    heading_font: 'Roboto',
    body_font: 'Roboto',
    line_height: 1.35,
    border_style: 'single',
  },
];

export interface FontOption {
  id: string;
  name: string;
  group: 'Formal Serif' | 'Modern Sans' | 'Friendly Display' | 'Monospace' | 'Indic Support';
  family: string;
}

export const FONT_OPTIONS: FontOption[] = [
  // Formal Serif
  { id: 'Tinos', name: 'Tinos (Times-compatible)', group: 'Formal Serif', family: 'Tinos, "Times New Roman", Times, serif' },
  { id: 'Merriweather', name: 'Merriweather', group: 'Formal Serif', family: 'Merriweather, Georgia, serif' },
  // Modern Sans
  { id: 'Roboto', name: 'Roboto', group: 'Modern Sans', family: 'Roboto, system-ui, sans-serif' },
  { id: 'Open Sans', name: 'Open Sans', group: 'Modern Sans', family: '"Open Sans", system-ui, sans-serif' },
  { id: 'Montserrat', name: 'Montserrat', group: 'Modern Sans', family: 'Montserrat, system-ui, sans-serif' },
  // Friendly Display
  { id: 'Playfair Display', name: 'Playfair Display', group: 'Friendly Display', family: '"Playfair Display", Georgia, serif' },
  // Monospace
  { id: 'Roboto Mono', name: 'Roboto Mono', group: 'Monospace', family: '"Roboto Mono", ui-monospace, monospace' },
  // Indic Support
  { id: 'Noto Sans Devanagari', name: 'Noto Sans Devanagari', group: 'Indic Support', family: '"Noto Sans Devanagari", "Noto Sans", sans-serif' },
  { id: 'Noto Sans Gujarati', name: 'Noto Sans Gujarati', group: 'Indic Support', family: '"Noto Sans Gujarati", "Noto Sans", sans-serif' },
];

/**
 * Calculate relative luminance of a hex color for WCAG 2.1 compliance.
 */
function getLuminance(hex: string): number {
  const clean = hex.replace('#', '');
  if (clean.length !== 6) return 1.0;
  const rgb = [
    parseInt(clean.slice(0, 2), 16) / 255,
    parseInt(clean.slice(2, 4), 16) / 255,
    parseInt(clean.slice(4, 6), 16) / 255,
  ].map((c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)));

  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
}

/**
 * Calculate WCAG contrast ratio between foreground and background.
 */
export function calculateContrastRatio(foregroundHex: string, backgroundHex: string): number {
  const lum1 = getLuminance(foregroundHex);
  const lum2 = getLuminance(backgroundHex);
  const brightest = Math.max(lum1, lum2);
  const darkest = Math.min(lum1, lum2);
  return (brightest + 0.05) / (darkest + 0.05);
}

/**
 * Check if a background color is ink-heavy for print (luminance < 0.4).
 */
export function isInkHeavy(backgroundHex: string): boolean {
  return getLuminance(backgroundHex) < 0.45;
}

export const DEFAULT_DESIGN_SETTINGS = {
  theme: 'official_navy',
  fontFamily: 'Tinos',
  headingFontFamily: 'Tinos',
  fontSize: 'base',
  lineHeight: 'normal',
  headingColor: '#1e3a8a',
  textColor: '#0f172a',
  tableHeaderBg: '#1e3a8a',
  tableHeaderTextColor: '#ffffff',
  borderColor: '#cbd5e1',
  dividerColor: '#3b82f6',
  pageBg: '#ffffff',
  orientation: 'portrait' as const,
  margins: 'normal' as const,
  pageBorder: 'single' as const,
  watermark: '',
  watermarkOpacity: 0.15,
};
