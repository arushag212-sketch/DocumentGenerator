import React from 'react';
import {
  AlignLeft,
  AlignCenter,
  AlignRight,
  Trash2,
  Maximize2,
  Layers,
  Wand2,
} from 'lucide-react';
import { ClubLogoOption } from './TemplateEditor';

interface ImageBlockPopoverProps {
  selectedBlock: any;
  onUpdate: (updates: any) => void;
  onClose: () => void;
  clubLogoOptions?: ClubLogoOption[];
  editor: any;
}

export const ImageBlockPopover: React.FC<ImageBlockPopoverProps> = ({
  selectedBlock,
  onUpdate,
  onClose,
  clubLogoOptions = [],
  editor,
}) => {
  if (!selectedBlock) return null;

  const { attrs = {}, position } = selectedBlock;
  const placement = attrs.placement || 'center';
  const textWrap = attrs.textWrap || 'inline';
  const currentWidth = attrs.width || 'auto';

  const handleDelete = () => {
    if (!editor || position === undefined) return;
    const node = editor.state.doc.nodeAt(position);
    if (node) {
      editor.view.dispatch(editor.state.tr.delete(position, position + node.nodeSize));
    }
    onClose();
  };

  return (
    <div className="fixed bottom-16 left-1/2 transform -translate-x-1/2 z-40 bg-white border border-slate-200 rounded-xl shadow-2xl p-3 w-96 text-xs space-y-2.5 animate-in fade-in select-none">
      <div className="flex items-center justify-between pb-1 border-b border-slate-100">
        <div>
          <span className="font-bold text-slate-800 flex items-center gap-1.5">
            <Wand2 className="w-3.5 h-3.5 text-brand-600" />
            Image & Logo Settings
          </span>
          <span className="text-[11px] text-slate-400 block">Drag image corner handle to resize with cursor</span>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold p-1">
          ✕
        </button>
      </div>

      {/* Placement & Alignment */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-600">Placement</span>
        <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg">
          <button
            onClick={() => onUpdate({ placement: 'left' })}
            className={`p-1 rounded ${placement === 'left' ? 'bg-white text-brand-600 shadow-xs' : 'text-slate-600'}`}
            title="Align Left"
          >
            <AlignLeft className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onUpdate({ placement: 'center' })}
            className={`p-1 rounded ${placement === 'center' ? 'bg-white text-brand-600 shadow-xs' : 'text-slate-600'}`}
            title="Align Center"
          >
            <AlignCenter className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onUpdate({ placement: 'right' })}
            className={`p-1 rounded ${placement === 'right' ? 'bg-white text-brand-600 shadow-xs' : 'text-slate-600'}`}
            title="Align Right"
          >
            <AlignRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Text Wrap Options */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-600 flex items-center gap-1">
          <Layers className="w-3 h-3 text-slate-400" />
          Text Wrap
        </span>
        <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg">
          <button
            onClick={() => onUpdate({ textWrap: 'inline' })}
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
              textWrap === 'inline' ? 'bg-white text-brand-600 shadow-xs font-bold' : 'text-slate-600'
            }`}
          >
            Inline
          </button>
          <button
            onClick={() => onUpdate({ textWrap: 'behind' })}
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
              textWrap === 'behind' ? 'bg-white text-brand-600 shadow-xs font-bold' : 'text-slate-600'
            }`}
            title="Behind text watermark/backdrop"
          >
            Behind
          </button>
          <button
            onClick={() => onUpdate({ textWrap: 'inFront' })}
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
              textWrap === 'inFront' ? 'bg-white text-brand-600 shadow-xs font-bold' : 'text-slate-600'
            }`}
            title="In front of text"
          >
            In Front
          </button>
        </div>
      </div>

      {/* Preset Widths */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-600 flex items-center gap-1">
          <Maximize2 className="w-3 h-3 text-slate-400" />
          Width
        </span>
        <div className="flex items-center gap-1">
          {['120px', '240px', '360px', '100%'].map((w) => (
            <button
              key={w}
              onClick={() => onUpdate({ width: w })}
              className={`px-2 py-0.5 rounded text-[11px] border transition ${
                currentWidth === w
                  ? 'border-brand-500 bg-brand-50 text-brand-700 font-bold'
                  : 'border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {w === '100%' ? 'Full' : w}
            </button>
          ))}
        </div>
      </div>

      {/* Choose from Club Asset Library */}
      {clubLogoOptions.length > 0 && (
        <div>
          <label className="block text-xs font-semibold text-slate-600 mb-1">
            Club Library Asset
          </label>
          <select
            value={attrs.assetId || attrs.clubLogoAssetId || ''}
            onChange={(e) => {
              const selectedId = e.target.value;
              const asset = clubLogoOptions.find((a) => a.id === selectedId);
              if (asset) {
                onUpdate({
                  src: asset.url,
                  assetId: asset.id,
                  clubLogoAssetId: asset.id,
                  alt: asset.name,
                });
              }
            }}
            className="w-full px-2 py-1 border border-slate-200 rounded text-xs bg-white"
          >
            <option value="">Select from uploaded assets...</option>
            {clubLogoOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.name} ({opt.kind || 'logo'})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-between pt-1 border-t border-slate-100">
        <button
          onClick={handleDelete}
          className="text-rose-600 hover:text-rose-700 flex items-center gap-1 text-xs font-semibold"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Remove Image
        </button>
        <button
          onClick={onClose}
          className="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-semibold text-xs"
        >
          Done
        </button>
      </div>
    </div>
  );
};
