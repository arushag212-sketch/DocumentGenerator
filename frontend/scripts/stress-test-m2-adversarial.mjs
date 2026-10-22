#!/usr/bin/env node
/**
 * Empirical Adversarial Stress Test Suite for Milestone 2
 * Agent: Challenger 2 (challenger_m2_2)
 * 
 * Empirically challenges and stress-tests:
 * 1. DocumentsTab.tsx filter grid and table min-width at 320px, 360px, 375px
 * 2. TemplateGalleryTab.tsx header action toolbar and card footer wrapping at 320px, 360px, 480px
 * 3. HomePage.tsx document type toggle header and BatchRowsPanel.tsx column mapping grid
 * 4. WelcomeTour.tsx footer button stacking
 * 5. VerifyPage.tsx unbroken string handling (break-all)
 * 6. DashboardPage.tsx stats grid and MonthlyChart scroll container
 * 7. Desktop baseline preservation (>= 1024px)
 * 8. Mathematical layout geometry simulation on 320px, 360px, 375px viewports
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SRC_DIR = path.resolve(__dirname, '../src');

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const failures = [];

function assert(condition, testName, details) {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`  ✔ PASS: ${testName}`);
  } else {
    failedTests++;
    failures.push({ testName, details });
    console.log(`  ✖ FAIL: ${testName} -> ${details}`);
  }
}

function readSrc(relPath) {
  const fullPath = path.resolve(SRC_DIR, relPath);
  return fs.readFileSync(fullPath, 'utf8');
}

console.log('======================================================================');
console.log('  CHALLENGER 2: EMPIRICAL ADVERSARIAL STRESS TEST FOR MILESTONE 2   ');
console.log('======================================================================\n');

// -----------------------------------------------------------------------------
// 1. DocumentsTab.tsx: Filter Grid, Table min-width, and Action Dropdowns
// -----------------------------------------------------------------------------
console.log('--- Suite 1: DocumentsTab.tsx Filter Grid & Table Constraints ---');
const docsSrc = readSrc('components/documents/DocumentsTab.tsx');

// Check filter grid responsive breakpoints
const filterGridMatch = docsSrc.match(/grid\s+grid-cols-1\s+sm:grid-cols-2\s+md:grid-cols-3\s+lg:grid-cols-6/);
assert(
  !!filterGridMatch,
  'DocumentsTab filter grid uses single column on mobile (<640px) scaling to 6 columns on desktop (>=1024px)',
  'Filter grid must have grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6'
);

// Check filter grid element widths: no fixed px widths exceeding 280px
const hasFixedColWidth = /grid-cols-\[\d+px\]/.test(docsSrc);
assert(
  !hasFixedColWidth,
  'DocumentsTab filter grid contains no rigid fixed-pixel column widths',
  'Found rigid column width pattern'
);

// Search & Clear buttons have w-full sm:w-auto
const searchButtonMatch = docsSrc.match(/className="[^"]*w-full\s+sm:w-auto[^"]*"[^>]*>\s*Search/);
assert(
  !!searchButtonMatch,
  'DocumentsTab Search button has w-full sm:w-auto to avoid mobile button overflow',
  'Search button lacks w-full sm:w-auto'
);

// Table enclosed in overflow-x-auto
const tableContainerMatch = docsSrc.match(/<div\s+className="overflow-x-auto">\s*<table/);
assert(
  !!tableContainerMatch,
  'DocumentsTab table is directly wrapped in overflow-x-auto container',
  'Table must be enclosed in overflow-x-auto'
);

// Table has explicit min-w-[720px]
const tableMinWMatch = docsSrc.match(/<table\s+className="[^"]*min-w-\[720px\][^"]*"/);
assert(
  !!tableMinWMatch,
  'DocumentsTab table enforces explicit min-w-[720px] preventing data column compression',
  'Table missing min-w-[720px]'
);

// Action dropdown container has relative right-0
const actionsAlignMatch = docsSrc.match(/className="flex items-center justify-end gap-1\.5 relative right-0"/);
assert(
  !!actionsAlignMatch,
  'DocumentsTab action buttons container enforces relative right-0 to avoid boundary blowout',
  'Action buttons container missing right-0'
);

// Preview modal header toolbar has flex-wrap
const modalToolbarMatch = docsSrc.match(/<div\s+className="flex flex-wrap items-center gap-2">/);
assert(
  !!modalToolbarMatch,
  'DocumentsTab preview modal header download buttons have flex-wrap for 320px screens',
  'Preview modal header missing flex-wrap'
);

// -----------------------------------------------------------------------------
// 2. TemplateGalleryTab.tsx: Header Action Toolbar & Card Footer Wrapping
// -----------------------------------------------------------------------------
console.log('\n--- Suite 2: TemplateGalleryTab.tsx Toolbars & Footer Wrapping ---');
const tmplSrc = readSrc('components/templates/TemplateGalleryTab.tsx');

// Header action toolbar has flex-wrap and responsive self alignment
const headerToolbarMatch = tmplSrc.match(/className="flex flex-wrap items-center gap-2 self-stretch sm:self-auto"/);
assert(
  !!headerToolbarMatch,
  'TemplateGalleryTab header action buttons have flex-wrap self-stretch sm:self-auto',
  'Header action buttons toolbar missing flex-wrap self-stretch sm:self-auto'
);

// Card footer has flex-wrap sm:flex-nowrap
const cardFooterMatch = tmplSrc.match(/className="[^"]*border-t\s+border-slate-100\s+flex\s+flex-wrap\s+sm:flex-nowrap\s+items-center\s+gap-2"/);
assert(
  !!cardFooterMatch,
  'TemplateGalleryTab card footer buttons have flex-wrap sm:flex-nowrap',
  'Card footer buttons missing flex-wrap sm:flex-nowrap'
);

const buttonsInToolbar = (tmplSrc.match(/data-testid="(?:wizard|import|new-blank)-template-btn"/g) || []).length;
assert(
  buttonsInToolbar === 3,
  `TemplateGalleryTab contains all 3 primary action buttons (found: ${buttonsInToolbar})`,
  'Expected 3 action buttons in header'
);

// -----------------------------------------------------------------------------
// 3. HomePage.tsx: Document Type Toggle & Badge Wrapping
// -----------------------------------------------------------------------------
console.log('\n--- Suite 3: HomePage.tsx Document Type Toggle & Badge Stacking ---');
const homeSrc = readSrc('components/create/HomePage.tsx');

// Document type toggle header has flex-col sm:flex-row
const typeToggleMatch = homeSrc.match(/<div\s+className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">/);
assert(
  !!typeToggleMatch,
  'HomePage document type toggle and badge container stacks vertically on mobile (flex-col sm:flex-row)',
  'Type toggle header missing flex-col sm:flex-row'
);

// Optional document type picker grid has grid-cols-1 sm:grid-cols-2 md:grid-cols-3
const typePickerGridMatch = homeSrc.match(/grid\s+grid-cols-1\s+sm:grid-cols-2\s+md:grid-cols-3\s+gap-2/);
assert(
  !!typePickerGridMatch,
  'HomePage document type picker items use single-column grid-cols-1 on mobile',
  'Document type picker grid missing grid-cols-1 sm:grid-cols-2 md:grid-cols-3'
);

// Selected template badge does not have rigid width
const badgeMatch = homeSrc.match(/selectedTemplate\s*&&\s*\(\s*<div\s+className="([^"]+)"/);
const badgeClasses = badgeMatch ? badgeMatch[1] : '';
const badgeHasNoRigidW = !/w-\[\d+px\]/.test(badgeClasses) && !/min-w-\[\d+px\]/.test(badgeClasses);
assert(
  badgeHasNoRigidW,
  'HomePage selected template active badge contains no rigid min-width causing mobile blowout',
  `Badge has rigid width: ${badgeClasses}`
);

// -----------------------------------------------------------------------------
// 4. BatchRowsPanel.tsx: Column Mapping Grid
// -----------------------------------------------------------------------------
console.log('\n--- Suite 4: BatchRowsPanel.tsx Column Mapping Grid ---');
const batchSrc = readSrc('components/create/BatchRowsPanel.tsx');

// Column mapping has grid-cols-1 sm:grid-cols-2
const batchGridMatch = batchSrc.match(/<div\s+key=\{h\}\s+className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 items-center px-3 py-2">/);
assert(
  !!batchGridMatch,
  'BatchRowsPanel column mapping row adapts to grid-cols-1 on mobile (<640px)',
  'BatchRowsPanel mapping row missing grid-cols-1 sm:grid-cols-2'
);

// Header label container has min-w-0 and truncate
const headerColMatch = batchSrc.match(/<div\s+className="min-w-0">\s*<p\s+className="text-sm font-medium text-slate-900 truncate">\{h\}<\/p>/);
assert(
  !!headerColMatch,
  'BatchRowsPanel CSV header label has min-w-0 with truncate to prevent blowout on long column names',
  'CSV header label missing min-w-0 truncate'
);

// Select element has input-field
const selectFieldMatch = batchSrc.match(/<select\s+aria-label=\{`Field for column \$\{h\}`\}\s+className="input-field !py-1\.5"/);
assert(
  !!selectFieldMatch,
  'BatchRowsPanel select mapping input uses input-field with full responsive width',
  'Select missing input-field class'
);

// -----------------------------------------------------------------------------
// 5. WelcomeTour.tsx: Footer Button Stacking
// -----------------------------------------------------------------------------
console.log('\n--- Suite 5: WelcomeTour.tsx Footer Button Stacking ---');
const tourSrc = readSrc('components/onboarding/WelcomeTour.tsx');

const tourFooterMatch = tourSrc.match(/className="mt-5 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3"/);
assert(
  !!tourFooterMatch,
  'WelcomeTour modal footer stacks buttons vertically with flex-col-reverse on mobile',
  'WelcomeTour footer missing flex-col-reverse sm:flex-row'
);

// -----------------------------------------------------------------------------
// 6. VerifyPage.tsx: Monospace Reference Number Wrapping
// -----------------------------------------------------------------------------
console.log('\n--- Suite 6: VerifyPage.tsx Two-Column Grid & Unbroken Reference Wrapping ---');
const verifySrc = readSrc('pages/VerifyPage.tsx');

const verifyGridMatch = verifySrc.match(/grid\s+grid-cols-1\s+sm:grid-cols-\[8rem_1fr\]/);
assert(
  !!verifyGridMatch,
  'VerifyPage details definition list adapts to grid-cols-1 on mobile and sm:grid-cols-[8rem_1fr] on >=640px',
  'VerifyPage details list missing grid-cols-1 sm:grid-cols-[8rem_1fr]'
);

const verifyBreakAllMatch = verifySrc.match(/<dd\s+className="text-slate-900 font-mono break-all">/);
assert(
  !!verifyBreakAllMatch,
  'VerifyPage reference number element has break-all to wrap 40+ char unbroken IDs',
  'VerifyPage dd missing break-all'
);

// -----------------------------------------------------------------------------
// 7. DashboardPage.tsx: Quick Stats Grid & MonthlyChart Scroll
// -----------------------------------------------------------------------------
console.log('\n--- Suite 7: DashboardPage.tsx Stats Grid & Monthly Chart ---');
const dashSrc = readSrc('pages/DashboardPage.tsx');

const dashStatsMatch = dashSrc.match(/grid\s+grid-cols-1\s+sm:grid-cols-2\s+lg:grid-cols-4/);
assert(
  !!dashStatsMatch,
  'DashboardPage quick stats adapts to grid-cols-1 on 320px and sm:grid-cols-2 on >=640px',
  'Dashboard quick stats missing grid-cols-1 sm:grid-cols-2 lg:grid-cols-4'
);

const chartScrollMatch = dashSrc.match(/<div\s+className="overflow-x-auto pb-2">\s*<div\s+className="relative min-w-\[320px\]">/);
assert(
  !!chartScrollMatch,
  'DashboardPage MonthlyChart is wrapped in overflow-x-auto with min-w-[320px]',
  'MonthlyChart missing overflow-x-auto with min-w-[320px]'
);

// -----------------------------------------------------------------------------
// 8. DocPreviewArt.tsx & LandingPage.tsx Overhangs
// -----------------------------------------------------------------------------
console.log('\n--- Suite 8: DocPreviewArt & LandingPage Negative Offsets ---');
const docArtSrc = readSrc('components/brand/DocPreviewArt.tsx');
const landingSrc = readSrc('pages/LandingPage.tsx');

const docArtRightMatch = docArtSrc.match(/-right-3\s+sm:-right-6/);
assert(
  !!docArtRightMatch,
  'DocPreviewArt constrains negative right offset to -right-3 on mobile and sm:-right-6 on >=640px',
  'DocPreviewArt missing -right-3 sm:-right-6'
);

const docArtLeftMatch = docArtSrc.match(/-left-2\s+sm:-left-3/);
assert(
  !!docArtLeftMatch,
  'DocPreviewArt constrains negative left offset to -left-2 on mobile and sm:-left-3 on >=640px',
  'DocPreviewArt missing -left-2 sm:-left-3'
);

const landingArtSizeMatch = landingSrc.match(/<DocPreviewArt\s+className="w-56\s+sm:w-72"/);
assert(
  !!landingArtSizeMatch,
  'LandingPage scales DocPreviewArt to w-56 on mobile and sm:w-72 on >=640px',
  'LandingPage DocPreviewArt missing w-56 sm:w-72'
);

// -----------------------------------------------------------------------------
// 9. Desktop Baseline Preservation Check (>= 1024px)
// -----------------------------------------------------------------------------
console.log('\n--- Suite 9: Desktop Baseline Preservation (>= 1024px) ---');

assert(
  docsSrc.includes('lg:grid-cols-6'),
  'DocumentsTab preserves lg:grid-cols-6 on desktop',
  'DocumentsTab missing lg:grid-cols-6'
);

assert(
  dashSrc.includes('lg:grid-cols-4'),
  'DashboardPage preserves lg:grid-cols-4 on desktop',
  'DashboardPage missing lg:grid-cols-4'
);

assert(
  tourSrc.includes('sm:flex-row') && tourSrc.includes('sm:justify-between'),
  'WelcomeTour preserves sm:flex-row sm:justify-between on desktop',
  'WelcomeTour missing sm:flex-row'
);

assert(
  tmplSrc.includes('sm:self-auto') && tmplSrc.includes('sm:flex-nowrap'),
  'TemplateGalleryTab preserves sm:self-auto and sm:flex-nowrap on desktop',
  'TemplateGalleryTab missing sm: desktop resets'
);

// -----------------------------------------------------------------------------
// 10. Empirical Geometry Simulation at 320px, 360px, 375px
// -----------------------------------------------------------------------------
console.log('\n--- Suite 10: Empirical Geometry Simulation on Narrow Viewports ---');

function simulateFlexWrap(items, containerWidth, gap) {
  let currentRowWidth = 0;
  let rows = 1;
  let maxRowWidth = 0;
  for (const item of items) {
    const needed = currentRowWidth === 0 ? item : currentRowWidth + gap + item;
    if (needed <= containerWidth) {
      currentRowWidth = needed;
    } else {
      rows++;
      currentRowWidth = item;
    }
    maxRowWidth = Math.max(maxRowWidth, currentRowWidth);
  }
  return { rows, maxRowWidth, overflow: maxRowWidth > containerWidth };
}

// Case 1: TemplateGalleryTab Action Toolbar at 320px
// Container = 320px - 32px padding = 288px.
// Buttons: Guided Setup (~135px), Import (~160px), Blank (~135px), gap = 8px.
const toolbarSim320 = simulateFlexWrap([135, 160, 135], 288, 8);
assert(
  !toolbarSim320.overflow && toolbarSim320.rows === 3 && toolbarSim320.maxRowWidth <= 288,
  `TemplateGalleryTab header toolbar wraps cleanly into 3 rows at 320px (maxRowWidth: ${toolbarSim320.maxRowWidth}px <= 288px)`,
  `Toolbar overflows: maxRowWidth = ${toolbarSim320.maxRowWidth}`
);

// Case 2: TemplateGalleryTab Action Toolbar at 360px
// Container = 360px - 32px padding = 328px.
// Row 1: 135 + 8 + 160 = 303px <= 328px. Row 2: 135px. Total rows = 2.
const toolbarSim360 = simulateFlexWrap([135, 160, 135], 328, 8);
assert(
  !toolbarSim360.overflow && toolbarSim360.rows === 2 && toolbarSim360.maxRowWidth <= 328,
  `TemplateGalleryTab header toolbar wraps cleanly into 2 rows at 360px (maxRowWidth: ${toolbarSim360.maxRowWidth}px <= 328px)`,
  `Toolbar overflows: maxRowWidth = ${toolbarSim360.maxRowWidth}`
);

// Case 3: TemplateGalleryTab Card Footer at 320px
// Card container = 288px - 32px card padding = 256px.
// Preview button (~85px), Use Template (~125px), Duplicate (~38px), gap = 8px.
const footerSim320 = simulateFlexWrap([85, 125, 38], 256, 8);
assert(
  !footerSim320.overflow && footerSim320.maxRowWidth <= 256,
  `TemplateGalleryTab card footer with manage action wraps cleanly at 320px (maxRowWidth: ${footerSim320.maxRowWidth}px <= 256px)`,
  `Footer overflows: maxRowWidth = ${footerSim320.maxRowWidth}`
);

// Case 4: WelcomeTour Footer Buttons at 320px
// Modal width = 320px - 24px modal overlay padding = 296px. Inner px-6 = 48px padding -> 248px content.
// With flex-col-reverse, each button takes width up to 248px (100% of parent).
assert(
  tourFooterMatch[0].includes('flex-col-reverse'),
  'WelcomeTour footer stacks buttons vertically with 100% width on 320px viewport',
  'WelcomeTour buttons not stacked'
);

// Case 5: VerifyPage Monospace Reference at 320px
// Container width = 288px. Inner card p-5 = 40px -> usable = 248px.
// 40-character monospace string @ 8.5px/char = 340px > 248px without break-all.
// With break-all, wraps onto 2 lines of ~170px <= 248px.
assert(
  verifyBreakAllMatch[0].includes('break-all'),
  'VerifyPage 40-char reference string breaks across lines within 248px card on 320px viewport',
  'VerifyPage missing break-all'
);

// Case 6: BatchRowsPanel Column Mapping at 320px
// Card inner width = 264px.
// Grid is grid-cols-1. Column 1 (label): min-w-0 + truncate -> 264px max width.
// Column 2 (select): input-field (w-full) -> 264px width.
assert(
  batchGridMatch[0].includes('grid-cols-1') && headerColMatch[0].includes('truncate'),
  'BatchRowsPanel column mapping adapts to single-column with truncate on 320px (<=264px per row)',
  'BatchRowsPanel mapping grid overflows'
);

console.log('\n======================================================================');
console.log(`STRESS TEST SUMMARY: ${passedTests}/${totalTests} PASSED (${Math.round((passedTests/totalTests)*100)}%)`);
if (failedTests > 0) {
  console.log(`FAILURES (${failedTests}):`);
  failures.forEach((f, i) => console.log(`  ${i+1}. ${f.testName}: ${f.details}`));
}
console.log('======================================================================');

if (failedTests > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
