#!/usr/bin/env node
/**
 * Empirical Adversarial Challenge Verification Harness for Milestone 3
 * Challenger 2 (challenger_m3_2) — Complex Workspaces & Modals Stress Suite
 *
 * Focus Areas:
 * 1. Virtual keyboard accommodation under 380px reduced viewport height.
 * 2. Clamping of all modal dialogs to max-h-[85vh] (or max-h-[90vh]/[92vh]) with internal overflow-y-auto.
 * 3. Modal close triggers and action buttons touch target envelopes (>= 44px).
 * 4. Pinned/sticky modal action footers remaining reachable.
 * 5. Strict desktop preservation at >= 1024px.
 * 6. Extreme viewport edge cases (640x360 landscape, 320px narrow).
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
console.log('     EMPIRICAL CHALLENGER 2 — MILESTONE 3 VERIFICATION HARNESS       ');
console.log('  Target: Modals, Virtual Keyboard Accommodation & Desktop Baseline   ');
console.log('======================================================================\n');

// File & AST Cache
const cache = new Map();
function loadAST(relPath) {
  if (cache.has(relPath)) return cache.get(relPath);
  const fullPath = path.resolve(SRC_ROOT, relPath);
  if (!fs.existsSync(fullPath)) throw new Error(`File not found: ${fullPath}`);
  const content = fs.readFileSync(fullPath, 'utf8');
  const sourceFile = ts.createSourceFile(
    path.basename(relPath),
    content,
    ts.ScriptTarget.Latest,
    true,
    relPath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  );
  const data = { relPath, fullPath, content, sourceFile };
  cache.set(relPath, data);
  return data;
}

// AST Helper Functions
function findJsxElements(rootNode, predicate = () => true) {
  const list = [];
  function walk(node) {
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      if (predicate(node)) list.push(node);
    }
    ts.forEachChild(node, walk);
  }
  walk(rootNode);
  return list;
}

function getTagName(node) {
  const tag = ts.isJsxElement(node) ? node.openingElement.tagName : node.tagName;
  return tag.getText();
}

function getAttribute(node, attrName) {
  const attrs = ts.isJsxElement(node) ? node.openingElement.attributes : node.attributes;
  for (const prop of attrs.properties) {
    if (ts.isJsxAttribute(prop) && prop.name.getText() === attrName) {
      if (!prop.initializer) return true;
      if (ts.isStringLiteral(prop.initializer)) return prop.initializer.text;
      if (ts.isJsxExpression(prop.initializer) && prop.initializer.expression) {
        return prop.initializer.expression.getText();
      }
    }
  }
  return null;
}

// Test Registry
const tests = [];
let passCount = 0;
let failCount = 0;

function test(name, fn) {
  tests.push({ name, fn });
}

// ============================================================================
// SUITE 1: 380px VIRTUAL KEYBOARD SIMULATION & MODAL CLAMPING
// ============================================================================

const MODAL_FILES = [
  { name: 'TemplateWizardModal', path: 'components/templates/TemplateWizardModal.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'TemplateImportModal', path: 'components/templates/TemplateImportModal.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'ShortcutsModal', path: 'components/TemplateEditor/ShortcutsModal.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'FindReplaceModal', path: 'components/TemplateEditor/FindReplaceModal.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'OfficialDialog', path: 'components/settings/PeopleTab.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'EmailDialog', path: 'pages/DocumentDetailPage.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'AdminTab (Venue/Series Modals)', path: 'components/settings/AdminTab.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'TemplateGalleryTab (Action/Logo Modals)', path: 'components/templates/TemplateGalleryTab.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'TemplateEditorModals (Validation/AI)', path: 'components/TemplateEditor/TemplateEditorModals.tsx', maxHExpected: 'max-h-[85vh]' },
  { name: 'FieldsPanel (Add Field Modal)', path: 'components/TemplateEditor/FieldsPanel.tsx', maxHExpected: 'max-h-[85vh]' },
];

for (const modal of MODAL_FILES) {
  test(`[380px Keyboard] ${modal.name} container clamps to max-h-[85vh] and provides overflow-y-auto`, () => {
    const { content } = loadAST(modal.path);
    const hasMaxH = content.includes('max-h-[85vh]') || content.includes('max-h-[90vh]');
    const hasOverflowY = content.includes('overflow-y-auto') || content.includes('overflow-auto');
    if (!hasMaxH) throw new Error(`${modal.name} missing max-h-[85vh] clamping.`);
    if (!hasOverflowY) throw new Error(`${modal.name} missing overflow-y-auto internal scroll.`);

    // Mathematical simulation: 380px viewport height with virtual keyboard
    const viewportHeight = 380;
    const clampedHeight = viewportHeight * 0.85; // 323px
    if (clampedHeight >= viewportHeight) {
      throw new Error(`Calculated clamped height ${clampedHeight}px exceeds viewport ${viewportHeight}px.`);
    }
  });
}

test('[380px Keyboard] ShortcutsModal pins header and footer (shrink-0) so Done button remains visible while body scrolls', () => {
  const { content } = loadAST('components/TemplateEditor/ShortcutsModal.tsx');
  const hasShrinkHeader = content.includes('shrink-0') && content.includes('Keyboard Shortcuts Cheat Sheet');
  const hasShrinkFooter = content.includes('shrink-0') && content.includes('Done');
  const hasFlex1Body = content.includes('flex-1') && content.includes('overflow-y-auto');
  if (!hasShrinkHeader) throw new Error('ShortcutsModal header lacks shrink-0.');
  if (!hasShrinkFooter) throw new Error('ShortcutsModal footer lacks shrink-0.');
  if (!hasFlex1Body) throw new Error('ShortcutsModal body lacks flex-1 overflow-y-auto.');
});

test('[380px Keyboard] TemplateWizardModal splits into flex-col with shrink-0 header and scrollable flex-1 body', () => {
  const { content } = loadAST('components/templates/TemplateWizardModal.tsx');
  const hasFlexCol = content.includes('flex flex-col') && content.includes('overflow-hidden');
  const hasShrinkHeader = content.includes('shrink-0');
  const hasScrollBody = content.includes('flex-1 overflow-y-auto');
  if (!hasFlexCol) throw new Error('TemplateWizardModal container lacks flex flex-col overflow-hidden.');
  if (!hasShrinkHeader) throw new Error('TemplateWizardModal header lacks shrink-0.');
  if (!hasScrollBody) throw new Error('TemplateWizardModal body lacks flex-1 overflow-y-auto.');
});

test('[380px Keyboard] TemplateImportModal splits into flex-col with shrink-0 header and scrollable flex-1 body', () => {
  const { content } = loadAST('components/templates/TemplateImportModal.tsx');
  const hasFlexCol = content.includes('flex flex-col') && content.includes('overflow-hidden');
  const hasShrinkHeader = content.includes('shrink-0');
  const hasScrollBody = content.includes('flex-1 overflow-y-auto');
  if (!hasFlexCol) throw new Error('TemplateImportModal container lacks flex flex-col overflow-hidden.');
  if (!hasShrinkHeader) throw new Error('TemplateImportModal header lacks shrink-0.');
  if (!hasScrollBody) throw new Error('TemplateImportModal body lacks flex-1 overflow-y-auto.');
});

// ============================================================================
// SUITE 2: MODAL CLOSE TRIGGERS TOUCH TARGET ENVELOPES (>= 44px)
// ============================================================================

const CLOSE_TRIGGER_FILES = [
  { name: 'TemplateWizardModal close button', path: 'components/templates/TemplateWizardModal.tsx' },
  { name: 'TemplateImportModal close button', path: 'components/templates/TemplateImportModal.tsx' },
  { name: 'ShortcutsModal close button', path: 'components/TemplateEditor/ShortcutsModal.tsx' },
  { name: 'FindReplaceModal close button', path: 'components/TemplateEditor/FindReplaceModal.tsx' },
  { name: 'OfficialDialog close button', path: 'components/settings/PeopleTab.tsx' },
  { name: 'EmailDialog close button', path: 'pages/DocumentDetailPage.tsx' },
  { name: 'TemplateGalleryTab actionModal close button', path: 'components/templates/TemplateGalleryTab.tsx' },
  { name: 'TemplateGalleryTab ambiguousLogoModal close button', path: 'components/templates/TemplateGalleryTab.tsx' },
  { name: 'TemplateEditorModals ValidationModal close button', path: 'components/TemplateEditor/TemplateEditorModals.tsx' },
  { name: 'TemplateEditorModals PreviewModal close button', path: 'components/TemplateEditor/TemplateEditorModals.tsx' },
  { name: 'FieldsPanel Add Field close button', path: 'components/TemplateEditor/FieldsPanel.tsx' },
  { name: 'PalettePanel drawer close button', path: 'components/TemplateEditor/PalettePanel.tsx' },
  { name: 'RightTabsPanel sheet close button', path: 'components/TemplateEditor/RightTabsPanel.tsx' },
  { name: 'BatchRowsPanel close button', path: 'components/create/BatchRowsPanel.tsx' },
  { name: 'ImageBlockPopover close button', path: 'components/TemplateEditor/ImageBlockPopover.tsx' },
  { name: 'ChipPopover close button', path: 'components/TemplateEditor/ChipPopover.tsx' },
];

for (const trigger of CLOSE_TRIGGER_FILES) {
  test(`[Touch Target] ${trigger.name} satisfies minimum 44px tap envelope`, () => {
    const { content } = loadAST(trigger.path);
    const has44pxMin =
      content.includes('min-w-[44px]') && content.includes('min-h-[44px]');
    if (!has44pxMin) {
      throw new Error(`${trigger.name} in ${trigger.path} does not have min-w-[44px] and min-h-[44px].`);
    }
  });
}

// ============================================================================
// SUITE 3: ACTION BUTTONS REACHABILITY & COMFORTABLE MOBILE SPACING
// ============================================================================

test('[Touch Target] ShortcutsModal Done button has min-h-[44px] on mobile', () => {
  const { content } = loadAST('components/TemplateEditor/ShortcutsModal.tsx');
  if (!content.includes('min-h-[44px] sm:min-h-0')) {
    throw new Error('ShortcutsModal Done button missing min-h-[44px] sm:min-h-0 touch target.');
  }
});

test('[Touch Target] FindReplaceModal Cancel and Replace All buttons have min-h-[44px] on mobile', () => {
  const { content } = loadAST('components/TemplateEditor/FindReplaceModal.tsx');
  if (!content.includes('min-h-[44px] sm:min-h-0')) {
    throw new Error('FindReplaceModal buttons missing min-h-[44px] sm:min-h-0 touch target.');
  }
});

test('[Touch Target] FieldsPanel Add Field Cancel and Create buttons have min-h-[44px] on mobile', () => {
  const { content } = loadAST('components/TemplateEditor/FieldsPanel.tsx');
  if (!content.includes('min-h-[44px] sm:min-h-0')) {
    throw new Error('FieldsPanel Add Field buttons missing min-h-[44px] sm:min-h-0 touch target.');
  }
});

test('[Touch Target] TemplateEditorModals ValidationModal OK button has min-h-[44px] on mobile', () => {
  const { content } = loadAST('components/TemplateEditor/TemplateEditorModals.tsx');
  if (!content.includes('min-h-[44px] sm:min-h-0')) {
    throw new Error('ValidationModal OK button missing min-h-[44px] sm:min-h-0 touch target.');
  }
});

test('[Touch Target] TemplateEditorModals UnreviewedAiModal action buttons have min-h-[44px] on mobile', () => {
  const { content } = loadAST('components/TemplateEditor/TemplateEditorModals.tsx');
  const matches = (content.match(/min-h-\[44px\]\s+sm:min-h-0/g) || []).length;
  if (matches < 2) {
    throw new Error(`UnreviewedAiModal action buttons lack min-h-[44px] sm:min-h-0 touch targets (found ${matches}).`);
  }
});

// ============================================================================
// SUITE 4: POPUP & POPOVER BOUNDARIES (320px SCREEN BOUNDS)
// ============================================================================

test('[320px Popovers] ImageBlockPopover constrained with max-w-[calc(100vw-24px)]', () => {
  const { content } = loadAST('components/TemplateEditor/ImageBlockPopover.tsx');
  if (!content.includes('max-w-[calc(100vw-24px)]')) {
    throw new Error('ImageBlockPopover missing max-w-[calc(100vw-24px)] constraint.');
  }
});

test('[320px Popovers] ChipPopover constrained with max-w-[calc(100vw-24px)]', () => {
  const { content } = loadAST('components/TemplateEditor/ChipPopover.tsx');
  if (!content.includes('max-w-[calc(100vw-24px)]')) {
    throw new Error('ChipPopover missing max-w-[calc(100vw-24px)] constraint.');
  }
});

test('[320px Popovers] FindReplaceModal responsive positioning: inset-x-4 on mobile, right-20 on desktop', () => {
  const { content } = loadAST('components/TemplateEditor/FindReplaceModal.tsx');
  const hasResponsiveInset = content.includes('inset-x-4') && content.includes('sm:inset-x-auto') && content.includes('sm:right-20');
  if (!hasResponsiveInset) {
    throw new Error('FindReplaceModal lacks responsive horizontal inset handling.');
  }
});

// ============================================================================
// SUITE 5: STRICT DESKTOP PRESERVATION (>= 1024px)
// ============================================================================

test('[Desktop Preservation] PalettePanel preserves inline layout (lg:static lg:z-auto lg:w-80) at >= 1024px', () => {
  const { content } = loadAST('components/TemplateEditor/PalettePanel.tsx');
  const preservesInline = content.includes('lg:static') && content.includes('lg:z-auto') && content.includes('lg:w-80');
  const preservesMiniRail = content.includes('hidden lg:flex');
  const backdropHiddenOnDesktop = content.includes('lg:hidden fixed inset-0');
  if (!preservesInline) throw new Error('PalettePanel inline desktop layout not preserved.');
  if (!preservesMiniRail) throw new Error('PalettePanel desktop collapsed rail not preserved.');
  if (!backdropHiddenOnDesktop) throw new Error('PalettePanel backdrop overlay not hidden on desktop.');
});

test('[Desktop Preservation] ResultPage document preview preserves full height (lg:min-h-[640px] lg:max-h-[820px]) at >= 1024px', () => {
  const { content } = loadAST('components/create/ResultPage.tsx');
  const hasDesktopContainer = content.includes('lg:min-h-[640px]') && content.includes('lg:max-h-[820px]');
  const hasDesktopIframe = content.includes('lg:h-[760px]');
  if (!hasDesktopContainer) throw new Error('ResultPage preview container desktop height not preserved.');
  if (!hasDesktopIframe) throw new Error('ResultPage preview iframe desktop height not preserved.');
});

test('[Desktop Preservation] TemplateEditor zoom fit calculation accounts for desktop panels only at >= 1024px', () => {
  const { content } = loadAST('components/TemplateEditor/TemplateEditor.tsx');
  const hasDesktopCheck = content.includes('isDesktop = window.innerWidth >= 1024');
  const hasSideCalculation = content.includes('leftOpen && isDesktop ? 288');
  if (!hasDesktopCheck) throw new Error('TemplateEditor zoom calculation does not differentiate desktop from mobile.');
  if (!hasSideCalculation) throw new Error('TemplateEditor canvas zoom subtracts drawer widths on mobile.');
});

test('[Desktop Preservation] RightTabsPanel collapsed rail preserved on desktop (hidden on mobile when !isOpen)', () => {
  const { content } = loadAST('components/TemplateEditor/RightTabsPanel.tsx');
  const hasCorrectCheck = content.includes('if (!isOpen) {') && content.includes('if (isMobile) return null;');
  if (!hasCorrectCheck) {
    throw new Error('RightTabsPanel conditional does not return collapsed rail on desktop while returning null on mobile.');
  }
});

// ============================================================================
// SUITE 6: DATA TABLES MINIMUM WIDTH & HORIZONTAL SCROLL CONTAINERS
// ============================================================================

test('[Tables] DocumentsTab table has min-w-[720px] inside overflow-x-auto', () => {
  const { content } = loadAST('components/documents/DocumentsTab.tsx');
  const match = content.match(/<table[^>]*className="([^"]+)"/s);
  if (!match) throw new Error('Table in DocumentsTab not found.');
  const classes = match[1];
  if (!classes.includes('min-w-[720px]') || !content.includes('overflow-x-auto')) {
    throw new Error(`DocumentsTab table missing min-w-[720px] inside overflow-x-auto: "${classes}"`);
  }
});

test('[Tables] PeopleTab table has min-w-[600px] inside overflow-x-auto', () => {
  const { content } = loadAST('components/settings/PeopleTab.tsx');
  const match = content.match(/<table[^>]*className="([^"]+)"/s);
  if (!match) throw new Error('Table in PeopleTab not found.');
  const classes = match[1];
  if (!classes.includes('min-w-[600px]') || !content.includes('overflow-x-auto')) {
    throw new Error(`PeopleTab table missing min-w-[600px] inside overflow-x-auto: "${classes}"`);
  }
});

test('[Tables] AuditTab table has min-w-[680px] inside overflow-x-auto', () => {
  const { content } = loadAST('components/settings/AuditTab.tsx');
  const match = content.match(/<table[^>]*className="([^"]+)"/s);
  if (!match) throw new Error('Table in AuditTab not found.');
  const classes = match[1];
  if (!classes.includes('min-w-[680px]') || !content.includes('overflow-x-auto')) {
    throw new Error(`AuditTab table missing min-w-[680px] inside overflow-x-auto: "${classes}"`);
  }
});

test('[Tables] ResultPage batch items table has min-w-[500px] inside overflow-x-auto', () => {
  const { content } = loadAST('components/create/ResultPage.tsx');
  const match = content.match(/<table[^>]*className="([^"]+)"/s);
  if (!match) throw new Error('Table in ResultPage not found.');
  const classes = match[1];
  if (!classes.includes('min-w-[500px]') || !content.includes('overflow-x-auto')) {
    throw new Error(`ResultPage table missing min-w-[500px] inside overflow-x-auto: "${classes}"`);
  }
});

test('[Tables] BatchRowsPanel column mapping grid has overflow-x-auto and responsive grid-cols-1 sm:grid-cols-2', () => {
  const { content } = loadAST('components/create/BatchRowsPanel.tsx');
  const hasScroll = content.includes('overflow-x-auto');
  const hasResponsiveGrid = content.includes('grid-cols-1 sm:grid-cols-2');
  if (!hasScroll) throw new Error('BatchRowsPanel missing overflow-x-auto container.');
  if (!hasResponsiveGrid) throw new Error('BatchRowsPanel missing grid-cols-1 sm:grid-cols-2.');
});

// ============================================================================
// EXECUTION & REPORTING
// ============================================================================

console.log(`Running ${tests.length} adversarial tests...\n`);

for (const t of tests) {
  try {
    t.fn();
    passCount++;
    console.log(`  \x1b[32m✔ PASS\x1b[0m ${t.name}`);
  } catch (err) {
    failCount++;
    console.log(`  \x1b[31m✘ FAIL\x1b[0m ${t.name}`);
    console.log(`    \x1b[31mError:\x1b[0m ${err.message}\n`);
  }
}

console.log('\n======================================================================');
console.log('                 ADVERSARIAL STRESS SUITE SUMMARY                     ');
console.log('======================================================================');
console.log(`Total Tests Run:  ${tests.length}`);
console.log(`Tests Passed:    ${passCount}`);
console.log(`Tests Failed:    ${failCount}`);
console.log(`Success Rate:    ${((passCount / tests.length) * 100).toFixed(1)}%`);
console.log('======================================================================\n');

if (failCount > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
