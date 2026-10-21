import { Editor } from '@tiptap/core';

export interface TableStateDetails {
  isInsideTable: boolean;
  rowIndex: number;
  rowCount: number;
  colIndex: number;
  colCount: number;
  canMoveRowUp: boolean;
  canMoveRowDown: boolean;
  canMoveColLeft: boolean;
  canMoveColRight: boolean;
  canMerge: boolean;
  canSplit: boolean;
}

/**
 * Inspects the current editor selection to determine if it is inside a table
 * and calculates row/column indices and movement boundaries.
 */
export function getTableDetails(editor: Editor | null): TableStateDetails | null {
  if (!editor || !editor.state) return null;
  const { state } = editor;
  const { $from } = state.selection;

  let tablePos = -1;
  let tableDepth = -1;

  for (let d = $from.depth; d > 0; d--) {
    if ($from.node(d).type.name === 'table') {
      tableDepth = d;
      tablePos = $from.before(d);
      break;
    }
  }

  if (tableDepth === -1 || tablePos === -1) {
    return null;
  }

  const tableNode = $from.node(tableDepth);
  const rowNode = $from.node(tableDepth + 1);
  const rowIndex = $from.index(tableDepth);
  const colIndex = $from.index(tableDepth + 1);
  const rowCount = tableNode.childCount;
  const colCount = rowNode ? rowNode.childCount : 0;

  return {
    isInsideTable: true,
    rowIndex,
    rowCount,
    colIndex,
    colCount,
    canMoveRowUp: rowIndex > 0,
    canMoveRowDown: rowIndex < rowCount - 1,
    canMoveColLeft: colIndex > 0,
    canMoveColRight: colIndex < colCount - 1,
    canMerge: editor.can?.().mergeCells?.() ?? false,
    canSplit: editor.can?.().splitCell?.() ?? false,
  };
}

/**
 * Swaps the current table row with the row above or below it in a single atomic transaction.
 */
export function moveTableRow(editor: Editor | null, direction: 'up' | 'down'): boolean {
  if (!editor || !editor.view) return false;
  const { state, view } = editor;
  const { $from } = state.selection;

  let tableDepth = -1;
  let tablePos = -1;

  for (let d = $from.depth; d > 0; d--) {
    if ($from.node(d).type.name === 'table') {
      tableDepth = d;
      tablePos = $from.before(d);
      break;
    }
  }

  if (tableDepth === -1) return false;

  const tableNode = $from.node(tableDepth);
  const rowIndex = $from.index(tableDepth);
  const targetIndex = direction === 'up' ? rowIndex - 1 : rowIndex + 1;

  if (targetIndex < 0 || targetIndex >= tableNode.childCount) {
    return false;
  }

  const rows: any[] = [];
  for (let i = 0; i < tableNode.childCount; i++) {
    rows.push(tableNode.child(i));
  }

  // Swap rows
  const temp = rows[rowIndex];
  rows[rowIndex] = rows[targetIndex];
  rows[targetIndex] = temp;

  const newTable = tableNode.type.create(tableNode.attrs, rows);
  const tr = state.tr.replaceWith(tablePos, tablePos + tableNode.nodeSize, newTable);
  view.dispatch(tr);
  return true;
}

/**
 * Swaps the current table column with the column to its left or right across all rows.
 */
export function moveTableColumn(editor: Editor | null, direction: 'left' | 'right'): boolean {
  if (!editor || !editor.view) return false;
  const { state, view } = editor;
  const { $from } = state.selection;

  let tableDepth = -1;
  let tablePos = -1;

  for (let d = $from.depth; d > 0; d--) {
    if ($from.node(d).type.name === 'table') {
      tableDepth = d;
      tablePos = $from.before(d);
      break;
    }
  }

  if (tableDepth === -1) return false;

  const tableNode = $from.node(tableDepth);
  const colIndex = $from.index(tableDepth + 1);
  const targetIndex = direction === 'left' ? colIndex - 1 : colIndex + 1;

  const newRows: any[] = [];

  for (let r = 0; r < tableNode.childCount; r++) {
    const rowNode = tableNode.child(r);
    if (targetIndex < 0 || targetIndex >= rowNode.childCount) {
      return false;
    }

    const cells: any[] = [];
    for (let c = 0; c < rowNode.childCount; c++) {
      cells.push(rowNode.child(c));
    }

    // Swap cells in this row
    const temp = cells[colIndex];
    cells[colIndex] = cells[targetIndex];
    cells[targetIndex] = temp;

    newRows.push(rowNode.type.create(rowNode.attrs, cells));
  }

  const newTable = tableNode.type.create(tableNode.attrs, newRows);
  const tr = state.tr.replaceWith(tablePos, tablePos + tableNode.nodeSize, newTable);
  view.dispatch(tr);
  return true;
}
