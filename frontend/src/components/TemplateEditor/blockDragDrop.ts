import { showEditorToast } from './editorToast';
import { Node as PMNode } from '@tiptap/pm/model';
import {
  createInfoTableNode,
  createRepeatingTableNode,
  createSignatureGridNode,
} from './tableExtensions';
import { createImageBlockNode } from './imageBlock';
import { api } from '../../api/client';

export function isLockedNode(node: any): boolean {
  if (!node) return false;
  const attrs = node.attrs || {};
  return Boolean(
    attrs.locked ||
      attrs.isLocked ||
      attrs.blockId === 'b_letterhead' ||
      attrs.imageType === 'letterhead' ||
      attrs.dataBlockType === 'letterhead'
  );
}

function getViewState(target: any): { view: any; state: any } | null {
  if (!target) return null;
  if (target.view && target.state) return { view: target.view, state: target.state };
  if (target.dispatch && target.state) return { view: target, state: target.state };
  return null;
}

export function moveTopLevelBlock(target: any, direction: 'up' | 'down'): boolean {
  const vs = getViewState(target);
  if (!vs) return false;
  const { view, state } = vs;
  const { doc, selection } = state;

  const topIndex = selection.$from.index(0);
  if (topIndex < 0 || topIndex >= doc.childCount) return false;

  const targetIndex = direction === 'up' ? topIndex - 1 : topIndex + 1;
  if (targetIndex < 0 || targetIndex >= doc.childCount) return false;

  const sourceNode = doc.child(topIndex);
  const targetNode = doc.child(targetIndex);

  if (isLockedNode(sourceNode) || isLockedNode(targetNode)) {
    return false;
  }

  return reorderTopLevelBlockToIndex(view, topIndex, targetIndex);
}

export function reorderTopLevelBlockToIndex(
  target: any,
  fromIndex: number,
  toIndex: number
): boolean {
  const vs = getViewState(target);
  if (!vs) return false;
  const { view, state } = vs;
  const doc = state.doc;

  if (fromIndex < 0 || fromIndex >= doc.childCount || toIndex < 0 || toIndex >= doc.childCount) {
    return false;
  }
  if (fromIndex === toIndex) return true;

  const sourceNode = doc.child(fromIndex);
  const targetNode = doc.child(toIndex);

  if (isLockedNode(sourceNode) || isLockedNode(targetNode)) {
    return false;
  }

  const children: any[] = [];
  for (let i = 0; i < doc.childCount; i++) {
    children.push(doc.child(i));
  }

  const [movedItem] = children.splice(fromIndex, 1);
  children.splice(toIndex, 0, movedItem);

  const tr = state.tr.replaceWith(0, doc.content.size, children);
  view.dispatch(tr);
  return true;
}

export function createDroppedBlockNode(schema: any, blockType: string, customPayload: any = {}) {
  const blockId = `b_${Math.random().toString(36).substring(2, 9)}`;

  switch (blockType) {
    case 'heading1':
      return schema.nodes.heading.create(
        { level: 1, blockId },
        schema.text(customPayload.text || 'Heading 1')
      );
    case 'heading2':
      return schema.nodes.heading.create(
        { level: 2, blockId },
        schema.text(customPayload.text || 'Heading 2')
      );
    case 'heading3':
      return schema.nodes.heading.create(
        { level: 3, blockId },
        schema.text(customPayload.text || 'Heading 3')
      );
    case 'paragraph':
      return schema.nodes.paragraph.create(
        { blockId },
        customPayload.text ? schema.text(customPayload.text) : undefined
      );
    case 'clause':
      return schema.nodes.paragraph.create(
        { blockId },
        schema.text(customPayload.text || 'Official clause text goes here.')
      );
    case 'divider':
      return schema.nodes.pageBreak.create({ blockId });
    case 'infoTable': {
      const raw = createInfoTableNode();
      return PMNode.fromJSON(schema, { ...raw, attrs: { ...raw.attrs, blockId } });
    }
    case 'repeatingTable': {
      const raw = createRepeatingTableNode();
      return PMNode.fromJSON(schema, { ...raw, attrs: { ...raw.attrs, blockId } });
    }
    case 'signatureGrid': {
      const raw = createSignatureGridNode(customPayload.columns || 2);
      return PMNode.fromJSON(schema, { ...raw, attrs: { ...raw.attrs, blockId } });
    }
    case 'collegeLogo': {
      const raw = createImageBlockNode({ imageType: 'college-logo', alt: 'College logo', width: '90px' });
      return PMNode.fromJSON(schema, { ...raw, attrs: { ...raw.attrs, blockId } });
    }
    case 'clubLogo':
    case 'imageBlock': {
      const raw = createImageBlockNode({
        imageType: customPayload.imageType || 'club-logo',
        src: customPayload.src || '',
        alt: customPayload.alt || 'Club logo',
        assetId: customPayload.assetId || null,
        width: customPayload.width || 'auto',
      });
      return PMNode.fromJSON(schema, { ...raw, attrs: { ...raw.attrs, blockId } });
    }
    default:
      return schema.nodes.paragraph.create({ blockId });
  }
}

export function handleEditorDrop(
  view: any,
  event: DragEvent,
  clubId?: string
): boolean {
  if (!event.dataTransfer) return false;

  const dropCoords = view.posAtCoords({ left: event.clientX, top: event.clientY });
  if (!dropCoords) return false;

  // 1. Reordering existing top-level block
  if (event.dataTransfer.types.includes('application/x-clubdocs-block-drag')) {
    event.preventDefault();
    try {
      const raw = event.dataTransfer.getData('application/x-clubdocs-block-drag');
      const data = JSON.parse(raw);
      const targetIndex = view.state.doc.resolve(dropCoords.pos).index(0);
      reorderTopLevelBlockToIndex(view, data.index, targetIndex);
      return true;
    } catch {
      return false;
    }
  }

  // 2. Dropping a field chip from Fields Panel onto canvas or into table cell
  if (event.dataTransfer.types.includes('application/x-clubdocs-field')) {
    event.preventDefault();
    try {
      const raw = event.dataTransfer.getData('application/x-clubdocs-field');
      const fieldData = JSON.parse(raw);
      const chipNode = view.state.schema.nodes.fieldChip.create(fieldData);

      const $pos = view.state.doc.resolve(dropCoords.pos);
      // If dropping inside a text block (e.g. paragraph or table cell), insert inline
      if ($pos.parent.isTextblock) {
        view.dispatch(view.state.tr.insert(dropCoords.pos, chipNode));
      } else {
        // Insert wrapped in a paragraph
        const blockId = `b_${Math.random().toString(36).substring(2, 9)}`;
        const pNode = view.state.schema.nodes.paragraph.create({ blockId }, chipNode);
        view.dispatch(view.state.tr.insert(dropCoords.pos, pNode));
      }
      return true;
    } catch {
      return false;
    }
  }

function findSafeBlockInsertPos(doc: any, pos: number): number {
  if (doc.childCount === 0) return 0;
  const $pos = doc.resolve(Math.min(pos, doc.content.size));
  const topIndex = Math.min($pos.index(0), doc.childCount - 1);
  let insertPos = 0;
  for (let i = 0; i < topIndex; i++) {
    insertPos += doc.child(i).nodeSize;
  }
  if (pos > insertPos && topIndex < doc.childCount) {
    insertPos += doc.child(topIndex).nodeSize;
  }
  return Math.min(insertPos, doc.content.size);
}

  // 3. Dropping a club asset (logo) from palette
  if (event.dataTransfer.types.includes('application/x-clubdocs-asset')) {
    event.preventDefault();
    try {
      const raw = event.dataTransfer.getData('application/x-clubdocs-asset');
      const asset = JSON.parse(raw);
      const node = createDroppedBlockNode(view.state.schema, 'imageBlock', {
        src: asset.url,
        assetId: asset.assetId,
        alt: asset.filename || 'Club logo',
        imageType: asset.kind || 'club-logo',
      });
      const insertPos = findSafeBlockInsertPos(view.state.doc, dropCoords.pos);
      view.dispatch(view.state.tr.insert(insertPos, node));
      return true;
    } catch {
      return false;
    }
  }

  // 4. Dropping a block/preset from the left palette
  if (event.dataTransfer.types.includes('application/x-clubdocs-block')) {
    event.preventDefault();
    try {
      const raw = event.dataTransfer.getData('application/x-clubdocs-block');
      const data = JSON.parse(raw);
      const node = createDroppedBlockNode(view.state.schema, data.type, data);
      const insertPos = findSafeBlockInsertPos(view.state.doc, dropCoords.pos);
      view.dispatch(view.state.tr.insert(insertPos, node));
      return true;
    } catch (err) {
      console.error('DROP BLOCK ERROR:', err);
      return false;
    }
  }

  // 5. Dropping a local image file from the computer (2 MB limit, normalized)
  if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
    const file = event.dataTransfer.files[0];
    if (file.type.startsWith('image/')) {
      event.preventDefault();
      if (file.size > 2 * 1024 * 1024) {
        showEditorToast('Image exceeds the 2 MB limit.', 'error');
        return true;
      }

      const reader = new FileReader();
      reader.onload = (readerEvent) => {
        const dataUrl = readerEvent.target?.result as string;
        if (!dataUrl) return;

        const node = createDroppedBlockNode(view.state.schema, 'imageBlock', {
          src: dataUrl,
          alt: file.name,
          imageType: 'image',
          width: '240px',
        });
        const insertPos = findSafeBlockInsertPos(view.state.doc, dropCoords.pos);
        view.dispatch(view.state.tr.insert(insertPos, node));

        // If clubId is available, upload in background to get canonical server asset
        if (clubId) {
          api.clubs.uploadLogo(clubId, file).catch(() => {
            // Local preview dataURL remains valid even if offline
          });
        }
      };
      reader.readAsDataURL(file);
      return true;
    }
  }

  return false;
}
