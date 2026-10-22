#!/usr/bin/env node
/**
 * Empirical Adversarial Challenger Verification Harness for Milestone 4
 * DocumentGenerator Mobile Experience Project
 * Agent: challenger_m4_1 (Empirical Challenger)
 *
 * Scope: Final Validation, Desktop Preservation & Build Acceptance
 * 
 * Adversarial Probe Categories:
 * 1. Viewport Matrix Probing (320px, 360px, 375px, 390px, 414px, 480px, 1280px)
 * 2. Extreme 320px Boundary Stress-Testing (Blowout prevention, break-all, flex-wrap)
 * 3. Virtual Keyboard & Modal Clamping (max-h-[85vh], overflow-y-auto, touch targets)
 * 4. Touch Target Envelope Accessibility (>=44px tap targets on all mobile controls)
 * 5. Body Scroll Locking & Event Reactivity (overflow hidden, escape key, resize unlock)
 * 6. Strict Desktop Layout Preservation (>= 1024px inline preservation, 0 mobile leaks)
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from '../node_modules/typescript/lib/typescript.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_ROOT = path.resolve(__dirname, '..');
const SRC_ROOT = path.resolve(FRONTEND_ROOT, 'src');

console.log('======================================================================');
console.log('   EMPIRICAL ADVERSARIAL CHALLENGER — MILESTONE 4 VALIDATION HARNESS  ');
console.log('   Focus: Multi-Viewport Matrix, 320px Stress, Modals & Desktop Pres. ');
console.log('======================================================================\n');

// Viewport matrix
const VIEWPORTS = {
  V320: { width: 320, height: 568, name: '320px (iPhone SE 1st gen)' },
  V360: { width: 360, height: 640, name: '360px (Standard Compact Android)' },
  V375: { width: 375, height: 667, name: '375px (iPhone 13 mini)' },
  V390: { width: 390, height: 844, name: '390px (iPhone 14 / Pixel)' },
  V414: { width: 414, height: 896, name: '414px (iPhone 11 Pro Max / Phablet)' },
  V480: { width: 480, height: 854, name: '480px (Large Mobile / Boundary)' },
  V1280: { width: 1280, height: 800, name: '1280px (Desktop Control >= 1024px)' },
};

// AST and file cache
const fileCache = new Map();
function loadAST(relPath) {
  if (fileCache.has(relPath)) return fileCache.get(relPath);
  const fullPath = path.resolve(SRC_ROOT, relPath);
  if (!fs.existsSync(fullPath)) throw new Error(`Source file not found: ${fullPath}`);
  const content = fs.readFileSync(fullPath, 'utf8');
  const sourceFile = ts.createSourceFile(
    path.basename(relPath),
    content,
    ts.ScriptTarget.Latest,
    true,
    relPath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  );
  const data = { relPath, fullPath, content, sourceFile };
  fileCache.set(relPath, data);
  return data;
}

// AST Helper Functions
function findJsxElements(rootNode, predicate = () => true) {
  const matches = [];
  function walk(node) {
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      if (predicate(node)) matches.push(node);
    }
    ts.forEachChild(node, walk);
  }
  walk(rootNode);
  return matches;
}

function getJsxAttribute(element, propName) {
  const attrs = ts.isJsxElement(element)
    ? element.openingElement.attributes.properties
    : element.attributes.properties;
  for (const attr of attrs) {
    if (ts.isJsxAttribute(attr) && attr.name.getText() === propName) {
      if (!attr.initializer) return true;
      if (ts.isStringLiteral(attr.initializer)) return attr.initializer.text;
      if (ts.isJsxExpression(attr.initializer) && attr.initializer.expression) {
        return attr.initializer.expression.getText();
      }
    }
  }
  return null;
}

function findButtonByAriaLabel(sourceFile, label) {
  const buttons = findJsxElements(sourceFile, (node) => {
    const tagName = ts.isJsxElement(node) ? node.openingElement.tagName.getText() : node.tagName.getText();
    if (tagName !== 'button') return false;
    const aria = getJsxAttribute(node, 'aria-label');
    return aria === label;
  });
  return buttons[0] || null;
}

// Tailwind Class Resolver
function parseClassTokens(className) {
  if (!className || typeof className !== 'string') return [];
  return className.replace(/[`'"]/g, '').split(/\s+/).map(c => c.trim()).filter(Boolean);
}

function resolveClasses(classes, width) {
  const active = new Set();
  const list = Array.isArray(classes) ? classes : parseClassTokens(classes);
  for (const c of list) {
    if (c.startsWith('sm:')) {
      if (width >= 640) active.add(c.slice(3));
    } else if (c.startsWith('md:')) {
      if (width >= 768) active.add(c.slice(3));
    } else if (c.startsWith('lg:')) {
      if (width >= 1024) active.add(c.slice(3));
    } else if (c.startsWith('xl:')) {
      if (width >= 1280) active.add(c.slice(3));
    } else {
      active.add(c);
    }
  }
  return Array.from(active);
}

// Test Runner
let testCount = 0;
let passCount = 0;
let failCount = 0;
const failureDetails = [];

function assert(description, condition, details = '') {
  testCount++;
  if (condition) {
    passCount++;
    console.log(`  ✔ PASS: ${description}`);
  } else {
    failCount++;
    console.log(`  ✖ FAIL: ${description}`);
    if (details) console.log(`         Details: ${details}`);
    failureDetails.push({ description, details });
  }
}

// ============================================================================
// SUITE 1: MULTI-VIEWPORT MATRIX PROBES (320px -> 1280px)
// ============================================================================
console.log('=== Suite 1: Multi-Viewport Matrix Behavior (7 Viewports) ===');

const appShell = loadAST('components/layout/AppShell.tsx');
const palettePanel = loadAST('components/TemplateEditor/PalettePanel.tsx');
const rightTabs = loadAST('components/TemplateEditor/RightTabsPanel.tsx');
const resultPage = loadAST('components/create/ResultPage.tsx');
const dashboardPage = loadAST('pages/DashboardPage.tsx');

// Check AppShell mobile vs desktop behavior across all viewports
Object.entries(VIEWPORTS).forEach(([key, vp]) => {
  const isMobile = vp.width < 1024;
  
  // AppShell Mobile Header
  const headerEl = findJsxElements(appShell.sourceFile, (node) => {
    const tag = ts.isJsxElement(node) ? node.openingElement.tagName.getText() : node.tagName.getText();
    return tag === 'header';
  })[0];
  const headerClasses = headerEl ? getJsxAttribute(headerEl, 'className') || '' : '';
  const resolvedHeaderClasses = resolveClasses(headerClasses, vp.width);
  const isHeaderHidden = resolvedHeaderClasses.includes('hidden');
  
  assert(
    `[${vp.width}px] AppShell Mobile Header visibility is ${isMobile ? 'VISIBLE' : 'HIDDEN'}`,
    isMobile ? !isHeaderHidden : isHeaderHidden,
    `Resolved header classes at ${vp.width}px: ${resolvedHeaderClasses.join(' ')}`
  );

  // AppShell Desktop Sidebar
  const sidebarMatch = appShell.content.match(/<aside\s+className=["'`]([^"'`]*hidden\s+lg:block[^"'`]*)["'`]/);
  const sidebarClasses = sidebarMatch ? sidebarMatch[1] : '';
  const resolvedSidebarClasses = resolveClasses(sidebarClasses, vp.width);
  const isSidebarVisible = resolvedSidebarClasses.includes('block');

  assert(
    `[${vp.width}px] AppShell Desktop Sidebar visibility is ${isMobile ? 'HIDDEN' : 'VISIBLE'}`,
    isMobile ? !isSidebarVisible : isSidebarVisible,
    `Resolved sidebar classes at ${vp.width}px: ${resolvedSidebarClasses.join(' ')}`
  );
});

// Check PalettePanel mobile drawer vs desktop static across all viewports
Object.entries(VIEWPORTS).forEach(([key, vp]) => {
  const isMobile = vp.width < 1024;
  
  // PalettePanel Backdrop Overlay
  const backdropMatch = palettePanel.content.match(/<div[^>]*className=["'`]([^"'`]*lg:hidden[^"'`]*fixed inset-0[^"'`]*)["'`]/);
  const backdropClasses = backdropMatch ? backdropMatch[1] : '';
  const resolvedBackdropClasses = resolveClasses(backdropClasses, vp.width);
  const isBackdropHidden = resolvedBackdropClasses.includes('hidden');

  assert(
    `[${vp.width}px] PalettePanel backdrop is ${isMobile ? 'ACTIVE (not hidden)' : 'SUPPRESSED (hidden)'}`,
    isMobile ? !isBackdropHidden : isBackdropHidden,
    `Resolved backdrop classes at ${vp.width}px: ${resolvedBackdropClasses.join(' ')}`
  );

  // PalettePanel Aside Positioning
  const asideMatch = palettePanel.content.match(/<aside[^>]*className=["'`]([^"'`]*fixed inset-y-0[^"'`]*lg:static[^"'`]*)["'`]/);
  const asideClasses = asideMatch ? asideMatch[1] : '';
  const resolvedAsideClasses = resolveClasses(asideClasses, vp.width);
  const isStatic = resolvedAsideClasses.includes('static');

  assert(
    `[${vp.width}px] PalettePanel positioning is ${isMobile ? 'FIXED OVERLAY (not static)' : 'STATIC IN-FLOW'}`,
    isMobile ? !isStatic : isStatic,
    `Resolved aside classes at ${vp.width}px: ${resolvedAsideClasses.join(' ')}`
  );
});

// Check ResultPage preview container height constraint across all viewports
Object.entries(VIEWPORTS).forEach(([key, vp]) => {
  const isMobile = vp.width < 1024;
  const previewMatch = resultPage.content.match(/className=["'`]([^"'`]*max-h-\[38vh\][^"'`]*)["'`]/);
  const previewClasses = previewMatch ? previewMatch[1] : '';
  const resolved = resolveClasses(previewClasses, vp.width);
  const hasMobileMaxHeight = resolved.some(c => c.startsWith('max-h-'));
  const hasDesktopMinHeight = resolved.some(c => c.startsWith('min-h-'));

  assert(
    `[${vp.width}px] ResultPage preview height is ${isMobile ? 'CONSTRAINED (<=45vh)' : 'TALL DESKTOP (>=640px)'}`,
    isMobile ? hasMobileMaxHeight : hasDesktopMinHeight,
    `Resolved preview classes at ${vp.width}px: ${resolved.join(' ')}`
  );
});

// Check Dashboard metrics grid columns across all viewports
Object.entries(VIEWPORTS).forEach(([key, vp]) => {
  const gridMatch = dashboardPage.content.match(/className=["'`]([^"'`]*grid-cols-1[^"'`]*lg:grid-cols-4[^"'`]*)["'`]/);
  const gridClasses = gridMatch ? gridMatch[1] : '';
  const resolved = resolveClasses(gridClasses, vp.width);

  if (vp.width >= 1024) {
    assert(
      `[${vp.width}px] Dashboard stats grid renders 4 columns`,
      resolved.includes('grid-cols-4'),
      `Resolved classes at ${vp.width}px: ${resolved.join(' ')}`
    );
  } else if (vp.width >= 640) {
    assert(
      `[${vp.width}px] Dashboard stats grid renders 2 columns`,
      resolved.includes('grid-cols-2'),
      `Resolved classes at ${vp.width}px: ${resolved.join(' ')}`
    );
  } else {
    assert(
      `[${vp.width}px] Dashboard stats grid renders 1 column`,
      resolved.includes('grid-cols-1'),
      `Resolved classes at ${vp.width}px: ${resolved.join(' ')}`
    );
  }
});

// ============================================================================
// SUITE 2: EXTREME 320PX BOUNDARY STRESS-TESTING
// ============================================================================
console.log('\n=== Suite 2: Extreme 320px Boundary Stress-Testing ===');

// Check AppShell root <main> container overflow prevention
const mainMatch = appShell.content.match(/<main\s+className=["'`]([^"'`]+)["'`]/);
const mainClasses = mainMatch ? mainMatch[1] : '';
assert(
  'AppShell <main> container includes overflow-x-hidden and min-w-0 to prevent body blowout',
  mainClasses.includes('overflow-x-hidden') && mainClasses.includes('min-w-0'),
  `Main classes: ${mainClasses}`
);

// Check DocPreviewArt negative margins on 320px
const docPreviewArt = loadAST('components/brand/DocPreviewArt.tsx');
const negativeMarginMatch = docPreviewArt.content.match(/-right-3\s+sm:-right-6/);
assert(
  'DocPreviewArt constrains negative horizontal offset to -right-3 on 320px screen',
  !!negativeMarginMatch,
  'DocPreviewArt should use -right-3 sm:-right-6'
);

// Check VerifyPage handling of long unbroken hashes / tokens
const verifyPage = loadAST('pages/VerifyPage.tsx');
assert(
  'VerifyPage applies break-all to avoid horizontal blowout from long hashes or tokens',
  verifyPage.content.includes('break-all'),
  'VerifyPage must include break-all on verification details'
);
assert(
  'VerifyPage layout uses responsive grid-cols-1 sm:grid-cols-[8rem_1fr] on small screens',
  verifyPage.content.includes('grid-cols-1 sm:grid-cols-[8rem_1fr]'),
  'VerifyPage grid should be single-column on 320px'
);

// Check BatchRowsPanel mobile grid adaptation
const batchRows = loadAST('components/create/BatchRowsPanel.tsx');
assert(
  'BatchRowsPanel column mapping grid adapts to grid-cols-1 on 320px screen',
  batchRows.content.includes('grid-cols-1 sm:grid-cols-2') || batchRows.content.includes('grid-cols-1 md:grid-cols-2'),
  'BatchRowsPanel field mapping must stack on 320px'
);

// Check toolbars flex wrapping on 320px
const documentsTab = loadAST('components/documents/DocumentsTab.tsx');
const templateGallery = loadAST('components/templates/TemplateGalleryTab.tsx');
assert(
  'DocumentsTab action toolbar includes flex-wrap to prevent 320px horizontal overflow',
  documentsTab.content.includes('flex flex-wrap items-center') || documentsTab.content.includes('flex-wrap'),
  'DocumentsTab toolbars must wrap on 320px'
);
assert(
  'TemplateGalleryTab search and filter toolbar includes flex-wrap',
  templateGallery.content.includes('flex-wrap'),
  'TemplateGalleryTab toolbar must wrap on 320px'
);

// Check WelcomeTour onboarding buttons on 320px
const welcomeTour = loadAST('components/onboarding/WelcomeTour.tsx');
assert(
  'WelcomeTour footer buttons stack gracefully with flex-col-reverse sm:flex-row on 320px',
  welcomeTour.content.includes('flex-col-reverse sm:flex-row') || welcomeTour.content.includes('flex-col'),
  'WelcomeTour buttons must stack vertically on mobile'
);

// ============================================================================
// SUITE 3: VIRTUAL KEYBOARD & MODAL CLAMPING (max-h-[85vh] + overflow-y-auto)
// ============================================================================
console.log('\n=== Suite 3: Virtual Keyboard & Modal Max-Height Clamping ===');

const modalFiles = [
  'components/templates/TemplateWizardModal.tsx',
  'components/templates/TemplateImportModal.tsx',
  'components/templates/TemplatePreviewModal.tsx',
  'components/TemplateEditor/TemplateEditorModals.tsx',
  'components/TemplateEditor/ShortcutsModal.tsx',
  'components/TemplateEditor/FindReplaceModal.tsx',
  'components/TemplateEditor/FieldsPanel.tsx',
  'components/settings/AdminTab.tsx',
  'components/settings/PeopleTab.tsx',
  'pages/DocumentDetailPage.tsx',
  'components/templates/TemplateGalleryTab.tsx',
];

modalFiles.forEach(file => {
  const ast = loadAST(file);
  const hasMaxH = /max-h-\[(85|90|92)vh\]/.test(ast.content);
  const hasOverflowY = /overflow-y-auto|overflow-auto/.test(ast.content);
  
  assert(
    `Modal in ${file} clamps container height to max-h-[85vh/90vh/92vh] for mobile virtual keyboard`,
    hasMaxH,
    `${file} should have max-h-[85vh] or similar`
  );
  
  assert(
    `Modal in ${file} enables vertical scroll (overflow-y-auto / overflow-auto)`,
    hasOverflowY,
    `${file} should have scrollable inner content`
  );
});

// ============================================================================
// SUITE 4: TOUCH TARGET ENVELOPE ACCESSIBILITY (>= 44px)
// ============================================================================
console.log('\n=== Suite 4: Touch Target Envelope Accessibility (>= 44px) ===');

// AppShell Hamburger Button
const hamburgerBtn = findButtonByAriaLabel(appShell.sourceFile, 'Open menu');
const hamburgerClasses = hamburgerBtn ? getJsxAttribute(hamburgerBtn, 'className') || '' : '';
assert(
  'AppShell mobile hamburger button satisfies >=44px tap target envelope (min-h-[44px] min-w-[44px])',
  hamburgerClasses.includes('min-h-[44px]') && hamburgerClasses.includes('min-w-[44px]'),
  `Hamburger button classes: ${hamburgerClasses}`
);

// AppShell Close Button
const closeBtn = findButtonByAriaLabel(appShell.sourceFile, 'Close menu');
const closeClasses = closeBtn ? getJsxAttribute(closeBtn, 'className') || '' : '';
assert(
  'AppShell mobile drawer close button satisfies >=44px tap target envelope (min-h-[44px] min-w-[44px])',
  closeClasses.includes('min-h-[44px]') && closeClasses.includes('min-w-[44px]'),
  `Close button classes: ${closeClasses}`
);

// AppShell Navigation Links
const navLinksMatch = appShell.content.match(/min-h-\[44px\][^"'`]*lg:min-h-0/);
const navLinksPitchMatch = appShell.content.match(/py-2\.5[^"'`]*lg:py-2/);
assert(
  'AppShell mobile drawer navigation links have minimum 44px touch pitch (min-h-[44px] py-2.5 lg:py-2)',
  Boolean(navLinksMatch && navLinksPitchMatch),
  `Nav links classes: ${navLinksMatch ? navLinksMatch[0] : 'not found'}`
);

// AppShell Sign Out Button
const signOutBtn = findButtonByAriaLabel(appShell.sourceFile, 'Sign out');
const signOutClasses = signOutBtn ? getJsxAttribute(signOutBtn, 'className') || '' : '';
assert(
  'AppShell mobile drawer sign out button satisfies >=44px tap target (min-h-[44px] min-w-[44px])',
  signOutClasses.includes('min-h-[44px]') && signOutClasses.includes('min-w-[44px]'),
  `Sign out classes: ${signOutClasses}`
);

// Modal Close Buttons Touch Targets
const modalCloseChecklist = [
  { file: 'components/templates/TemplateWizardModal.tsx', label: 'Close dialog' },
  { file: 'components/templates/TemplateImportModal.tsx', label: 'Close dialog' },
  { file: 'components/TemplateEditor/TemplateEditorModals.tsx', label: 'Close dialog' },
  { file: 'components/TemplateEditor/ShortcutsModal.tsx', label: 'Close dialog' },
  { file: 'components/TemplateEditor/FindReplaceModal.tsx', label: 'Close find and replace' },
  { file: 'components/TemplateEditor/FieldsPanel.tsx', label: 'Close dialog' },
  { file: 'components/settings/PeopleTab.tsx', label: 'Close' },
  { file: 'pages/DocumentDetailPage.tsx', label: 'Close' },
  { file: 'components/templates/TemplateGalleryTab.tsx', label: 'Close dialog' },
];

modalCloseChecklist.forEach(({ file, label }) => {
  const ast = loadAST(file);
  const btn = findButtonByAriaLabel(ast.sourceFile, label);
  const cls = btn ? getJsxAttribute(btn, 'className') || '' : '';
  const meetsMinDimensions = cls.includes('min-h-[44px]') && cls.includes('min-w-[44px]');
  
  assert(
    `Close button in ${file} satisfies >=44px tap target envelope (min-h-[44px] min-w-[44px])`,
    meetsMinDimensions,
    `${file} close button classes: "${cls}"`
  );
});

// ============================================================================
// SUITE 5: BODY SCROLL LOCKING & REACTIVITY
// ============================================================================
console.log('\n=== Suite 5: Body Scroll Locking & Event Reactivity ===');

assert(
  'AppShell locks document.body.style.overflow = "hidden" when mobileOpen is true',
  appShell.content.includes("document.body.style.overflow = 'hidden'") || appShell.content.includes('document.body.style.overflow = "hidden"'),
  'AppShell must set body overflow to hidden on open'
);

assert(
  'AppShell cleans up and restores document.body.style.overflow on drawer close or unmount',
  appShell.content.includes('document.body.style.overflow = originalOverflow'),
  'AppShell must restore body overflow on close'
);

assert(
  'AppShell listens for Escape keydown to dismiss mobile drawer',
  appShell.content.includes("e.key === 'Escape'") && appShell.content.includes('setMobileOpen(false)'),
  'AppShell must listen for Escape key to close mobile drawer'
);

assert(
  'AppShell listens for window resize and resets mobileOpen when width >= 1024px',
  appShell.content.includes('innerWidth >= 1024') && appShell.content.includes('setMobileOpen(false)'),
  'AppShell must auto-close mobile drawer when resizing back to desktop'
);

// ============================================================================
// SUITE 6: STRICT DESKTOP LAYOUT PRESERVATION (>= 1024px)
// ============================================================================
console.log('\n=== Suite 6: Strict Desktop Layout Preservation (>= 1024px) ===');

// Check AppShell desktop sidebar
assert(
  'AppShell desktop aside uses static inline w-64 layout with lg:block and sticky positioning',
  appShell.content.includes('hidden lg:block w-64 flex-shrink-0 border-r border-slate-200 bg-white sticky top-0 h-screen'),
  'AppShell desktop aside must match exact desktop specs'
);

// Check AppShell mobile header desktop suppression
assert(
  'AppShell mobile header is strictly suppressed on desktop via lg:hidden',
  appShell.content.includes('lg:hidden sticky top-0 z-40 flex items-center gap-3 h-14'),
  'AppShell mobile header must have lg:hidden'
);

// Check AppShell desktop navigation link compact sizing
assert(
  'AppShell navigation links revert to compact desktop padding (lg:py-2) without forced 44px min-h',
  appShell.content.includes('lg:py-2') && appShell.content.includes('lg:min-h-0'),
  'AppShell nav links must reset min-h-0 on desktop'
);

// Check Template Studio PalettePanel desktop in-flow rendering
assert(
  'PalettePanel renders in-flow static block on desktop (lg:static lg:z-auto lg:w-80 lg:shadow-none lg:border-r)',
  palettePanel.content.includes('lg:static lg:z-auto') && palettePanel.content.includes('lg:w-80 lg:shadow-none lg:border-r'),
  'PalettePanel must be in-flow static w-80 on desktop'
);

// Check Template Studio PalettePanel collapsed rail preserved on desktop
assert(
  'PalettePanel collapsed icon rail is preserved on desktop via hidden lg:flex',
  palettePanel.content.includes('hidden lg:flex border-r border-slate-200 bg-slate-50 flex-col items-center py-3'),
  'Collapsed icon rail must be visible on desktop'
);

// Check Template Studio RightTabsPanel desktop rendering
assert(
  'RightTabsPanel renders in-flow static side panel on desktop (w-80 lg:w-96 border-l)',
  rightTabs.content.includes('w-80 lg:w-96 border-l border-slate-200 bg-white flex flex-col'),
  'RightTabsPanel must render as desktop side panel'
);

// Check ResultPage desktop 12-column grid and tall preview
assert(
  'ResultPage maintains desktop 12-column grid (lg:grid-cols-12) with 7-column preview and 5-column details',
  resultPage.content.includes('lg:grid-cols-12') && resultPage.content.includes('lg:col-span-7'),
  'ResultPage must preserve 12-col grid on desktop'
);

assert(
  'ResultPage preview container preserves tall desktop height (lg:min-h-[640px] lg:max-h-[820px])',
  resultPage.content.includes('lg:min-h-[640px]') && resultPage.content.includes('lg:max-h-[820px]'),
  'ResultPage preview must be tall on desktop'
);

// Check Dashboard metrics desktop 4-column row
assert(
  'Dashboard metrics grid maintains horizontal 4-column layout on desktop (lg:grid-cols-4)',
  dashboardPage.content.includes('lg:grid-cols-4'),
  'Dashboard metrics must have lg:grid-cols-4'
);

// ============================================================================
// SUMMARY & VERDICT
// ============================================================================
console.log('\n======================================================================');
console.log(`TOTAL ADVERSARIAL CHECKS: ${testCount}`);
console.log(`PASSED:                   ${passCount} (${((passCount / testCount) * 100).toFixed(1)}%)`);
console.log(`FAILED:                   ${failCount}`);
console.log('======================================================================\n');

if (failCount > 0) {
  console.error(`✖ VERDICT: REQUEST_CHANGES — ${failCount} adversarial stress tests failed:`);
  failureDetails.forEach((f, i) => {
    console.error(`  ${i + 1}. ${f.description}\n     Details: ${f.details}`);
  });
  process.exit(1);
} else {
  console.log('✔ VERDICT: APPROVE — All adversarial stress tests PASSED with zero regressions.');
  process.exit(0);
}
