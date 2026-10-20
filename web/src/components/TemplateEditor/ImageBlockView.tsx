import { showEditorToast } from './editorToast';
import React, { useState, useRef, useCallback } from 'react';
import { NodeViewWrapper, NodeViewProps } from '@tiptap/react';
import { useAuth } from '../../context/AuthContext';
import {
  AlignLeft,
  AlignCenter,
  AlignRight,
  Trash2,
  Upload,
  ImageIcon,
  Shield,
} from 'lucide-react';

export const ImageBlockView: React.FC<NodeViewProps> = ({
  node,
  updateAttributes,
  deleteNode,
  selected,
}) => {
  const { activeClub } = useAuth();
  const {
    src: storedSrc,
    alt,
    caption,
    width,
    height,
    placement = 'center',
    imageType = 'image',
    placeholderText,
  } = node.attrs;
  // A club-logo block without a chosen image shows (and prints) the club's own logo;
  // a college-logo block shows the institute crest.
  const src =
    storedSrc ||
    (imageType === 'college-logo'
      ? '/assets/svnit_crest.png'
      : (imageType === 'club-logo' || imageType === 'logo') && activeClub
        ? `/api/v1/clubs/${activeClub.id}/public-logo`
        : '');

  const [isResizing, setIsResizing] = useState(false);
  const [liveDimensions, setLiveDimensions] = useState<{ width: number; height: number } | null>(null);
  const [isHovered, setIsHovered] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Parse numeric width/height for inline styling
  const getParsedWidth = useCallback(() => {
    if (liveDimensions) return `${liveDimensions.width}px`;
    if (!width || width === 'auto') return 'auto';
    if (String(width).endsWith('%')) return width;
    const num = parseInt(String(width), 10);
    return isNaN(num) ? 'auto' : `${num}px`;
  }, [width, liveDimensions]);

  const getParsedHeight = useCallback(() => {
    if (liveDimensions) return `${liveDimensions.height}px`;
    if (!height || height === 'auto') return 'auto';
    const num = parseInt(String(height), 10);
    return isNaN(num) ? 'auto' : `${num}px`;
  }, [height, liveDimensions]);

  // Handle cursor dragging resize
  const handleResizeStart = (e: React.MouseEvent, direction: 'corner' | 'right' | 'bottom') => {
    e.preventDefault();
    e.stopPropagation();

    const startX = e.clientX;
    const startY = e.clientY;

    const currentElem = imgRef.current;
    const startW = currentElem ? currentElem.offsetWidth : 240;
    const startH = currentElem ? currentElem.offsetHeight : 160;
    const aspectRatio = startW / (startH || 1);

    setIsResizing(true);
    setLiveDimensions({ width: startW, height: startH });

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaX = moveEvent.clientX - startX;
      const deltaY = moveEvent.clientY - startY;

      let newW = startW;
      let newH = startH;

      if (direction === 'corner') {
        newW = Math.max(60, Math.min(760, Math.round(startW + deltaX)));
        newH = Math.max(40, Math.round(newW / aspectRatio));
      } else if (direction === 'right') {
        newW = Math.max(60, Math.min(760, Math.round(startW + deltaX)));
      } else if (direction === 'bottom') {
        newH = Math.max(40, Math.round(startH + deltaY));
      }

      setLiveDimensions({ width: newW, height: newH });
    };

    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      setIsResizing(false);

      setLiveDimensions((latest) => {
        if (latest) {
          updateAttributes({
            width: `${latest.width}px`,
            height: latest.height,
          });
        }
        return null;
      });
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  // Local file upload handler for image placeholder
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      showEditorToast('Please select an image file (PNG, JPG, SVG, WebP).', 'error');
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      showEditorToast('Image exceeds the 2 MB limit.', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = (uploadEvt) => {
      const base64Url = uploadEvt.target?.result as string;
      if (base64Url) {
        updateAttributes({
          src: base64Url,
          alt: file.name.replace(/\.[^/.]+$/, ''),
        });
      }
    };
    reader.readAsDataURL(file);
  };

  const justifyClass =
    placement === 'left' ? 'justify-start' : placement === 'right' ? 'justify-end' : 'justify-center';

  return (
    <NodeViewWrapper
      className={`relative my-3 flex flex-col ${justifyClass} select-none group`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => !isResizing && setIsHovered(false)}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
      />

      <div
        className={`relative inline-block transition-all ${
          selected || isHovered || isResizing ? 'ring-2 ring-brand-500/80 ring-offset-2 rounded-lg' : ''
        }`}
        style={{
          width: getParsedWidth(),
          maxWidth: '100%',
          alignSelf: placement === 'left' ? 'flex-start' : placement === 'right' ? 'flex-end' : 'center',
        }}
      >
        {/* Floating Quick Action Toolbar */}
        {(selected || isHovered || isResizing) && (
          <div className="absolute -top-10 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1 bg-slate-900/95 backdrop-blur text-white px-2 py-1 rounded-lg shadow-xl border border-slate-700 text-xs animate-in fade-in duration-100 whitespace-nowrap">
            {/* Alignment buttons */}
            <div className="flex items-center gap-0.5 border-r border-slate-700 pr-1.5">
              <button
                type="button"
                onClick={() => updateAttributes({ placement: 'left' })}
                title="Align Left"
                className={`p-1 rounded hover:bg-slate-800 ${placement === 'left' ? 'text-brand-500 bg-slate-800' : 'text-slate-300'}`}
              >
                <AlignLeft className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => updateAttributes({ placement: 'center' })}
                title="Align Center"
                className={`p-1 rounded hover:bg-slate-800 ${placement === 'center' ? 'text-brand-500 bg-slate-800' : 'text-slate-300'}`}
              >
                <AlignCenter className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => updateAttributes({ placement: 'right' })}
                title="Align Right"
                className={`p-1 rounded hover:bg-slate-800 ${placement === 'right' ? 'text-brand-500 bg-slate-800' : 'text-slate-300'}`}
              >
                <AlignRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Quick Width Presets */}
            <div className="flex items-center gap-1 px-1 border-r border-slate-700 pr-1.5 text-xs">
              <button
                type="button"
                onClick={() => updateAttributes({ width: '120px', height: 100 })}
                className="px-1.5 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
              >
                120px
              </button>
              <button
                type="button"
                onClick={() => updateAttributes({ width: '240px', height: 180 })}
                className="px-1.5 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
              >
                240px
              </button>
              <button
                type="button"
                onClick={() => updateAttributes({ width: '360px', height: 260 })}
                className="px-1.5 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
              >
                360px
              </button>
              <button
                type="button"
                onClick={() => updateAttributes({ width: '100%', height: 'auto' })}
                className="px-1.5 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
              >
                Full
              </button>
            </div>

            {/* Upload/Replace button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              title="Replace Image"
              className="p-1 rounded hover:bg-slate-800 text-slate-300 hover:text-white flex items-center gap-1 text-xs"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Replace</span>
            </button>

            {/* Delete button */}
            <button
              type="button"
              onClick={deleteNode}
              title="Delete Image Block"
              className="p-1 rounded hover:bg-red-900/60 text-red-400 hover:text-red-200 transition"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Live resize dimensions badge */}
        {isResizing && liveDimensions && (
          <div className="absolute top-2 left-2 z-30 bg-slate-900/90 text-white font-mono text-[11px] px-2 py-0.5 rounded shadow">
            {liveDimensions.width} × {liveDimensions.height} px
          </div>
        )}

        {/* Image Display or Empty Placeholder */}
        {src ? (
          <img
            ref={imgRef}
            src={src}
            alt={alt || 'Template Image'}
            style={{
              width: getParsedWidth(),
              height: getParsedHeight(),
              objectFit: 'contain',
              display: 'block',
            }}
            className="rounded-md max-w-full"
            loading="lazy"
          />
        ) : (
          <div
            onClick={() => fileInputRef.current?.click()}
            className="w-full py-8 px-6 border-2 border-dashed border-brand-200 hover:border-brand-500 bg-brand-50/40 hover:bg-brand-50/70 rounded-xl cursor-pointer text-center transition flex flex-col items-center justify-center gap-2"
            style={{ minHeight: '140px', width: getParsedWidth() }}
          >
            <div className="w-10 h-10 rounded-full bg-white shadow-xs flex items-center justify-center text-brand-600">
              {imageType === 'club-logo' ? <Shield className="w-5 h-5" /> : <ImageIcon className="w-5 h-5" />}
            </div>
            <div>
              <p className="text-xs font-bold text-slate-800">
                {imageType === 'club-logo' ? 'Club Logo Placeholder' : 'Image Placeholder'}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                {placeholderText || 'Click to upload image or drop from left palette'}
              </p>
            </div>
            <button
              type="button"
              className="mt-1 px-3 py-1 bg-white border border-slate-300 hover:border-brand-500 text-brand-700 text-xs font-semibold rounded-lg shadow-2xs flex items-center gap-1.5 transition"
            >
              <Upload className="w-3 h-3" />
              <span>Choose File</span>
            </button>
          </div>
        )}

        {/* Interactive Cursor Resize Handles */}
        {(selected || isHovered || isResizing) && src && (
          <>
            {/* Bottom-right corner handle (cursor drag-to-resize width and height) */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'corner')}
              title="Drag cursor to resize image"
              className="absolute -bottom-1.5 -right-1.5 w-4 h-4 bg-brand-600 border-2 border-white rounded-full shadow-md cursor-nwse-resize z-20 hover:scale-125 transition-transform"
            />

            {/* Right edge handle (cursor drag-to-resize width) */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'right')}
              title="Drag cursor horizontally to adjust width"
              className="absolute top-1/2 -right-1.5 -translate-y-1/2 w-3 h-6 bg-brand-500 border border-white rounded-full shadow-xs cursor-ew-resize z-20 hover:scale-110 transition-transform"
            />

            {/* Bottom edge handle (cursor drag-to-resize height) */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'bottom')}
              title="Drag cursor vertically to adjust height"
              className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-6 h-3 bg-brand-500 border border-white rounded-full shadow-xs cursor-ns-resize z-20 hover:scale-110 transition-transform"
            />
          </>
        )}
      </div>

      {caption && (
        <figcaption className="text-center text-xs text-slate-500 italic mt-1 max-w-md self-center">
          {caption}
        </figcaption>
      )}
    </NodeViewWrapper>
  );
};
