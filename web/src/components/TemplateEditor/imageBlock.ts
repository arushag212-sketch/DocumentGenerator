import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer } from '@tiptap/react';
import { ImageBlockView } from './ImageBlockView';

export interface ImageBlockAttributes {
  imageType: 'image' | 'club-logo' | 'logo' | string;
  src: string;
  alt: string;
  caption: string;
  placeholderText: string;
  clubLogoAssetId: string | null;
  logoAssetId: string | null;
  assetId: string | null;
  placement: 'left' | 'center' | 'right' | string;
  width: string | number;
  height: number;
  fit: 'contain' | 'cover' | string;
  textWrap: 'inline' | 'behind' | 'inFront' | string;
}

export const ImageBlock = Node.create({
  name: 'imageBlock',
  group: 'block',
  atom: true,
  isolating: true,
  selectable: true,
  draggable: true,

  addNodeView() {
    return ReactNodeViewRenderer(ImageBlockView);
  },

  addAttributes() {
    return {
      imageType: {
        default: 'image',
        parseHTML: (element: any) => element.getAttribute('data-image-type') || 'image',
        renderHTML: (attributes: any) => ({ 'data-image-type': attributes.imageType || 'image' }),
      },
      src: {
        default: '',
        parseHTML: (element: any) => {
          const img = element.querySelector?.('img');
          return element.getAttribute('data-image-src') || img?.getAttribute('src') || '';
        },
        renderHTML: (attributes: any) => (attributes.src ? { 'data-image-src': attributes.src } : {}),
      },
      alt: {
        default: 'Image placeholder',
        parseHTML: (element: any) =>
          element.getAttribute('data-image-alt') ||
          element.querySelector?.('img')?.getAttribute('alt') ||
          'Image placeholder',
        renderHTML: (attributes: any) => ({ 'data-image-alt': attributes.alt || 'Image placeholder' }),
      },
      caption: {
        default: '',
        parseHTML: (element: any) =>
          element.getAttribute('data-caption') || element.querySelector?.('figcaption')?.textContent || '',
        renderHTML: (attributes: any) => (attributes.caption ? { 'data-caption': attributes.caption } : {}),
      },
      placeholderText: {
        default: 'Select an image to place here',
        parseHTML: (element: any) =>
          element.getAttribute('data-placeholder-text') || 'Select an image to place here',
        renderHTML: (attributes: any) => ({
          'data-placeholder-text': attributes.placeholderText || 'Select an image to place here',
        }),
      },
      clubLogoAssetId: {
        default: null,
        parseHTML: (element: any) =>
          element.getAttribute('data-club-logo-id') || element.getAttribute('data-logo-asset-id') || null,
        renderHTML: (attributes: any) =>
          attributes.clubLogoAssetId ? { 'data-club-logo-id': attributes.clubLogoAssetId } : {},
      },
      logoAssetId: {
        default: null,
        parseHTML: (element: any) =>
          element.getAttribute('data-logo-asset-id') || element.getAttribute('data-club-logo-id') || null,
        renderHTML: (attributes: any) =>
          attributes.logoAssetId ? { 'data-logo-asset-id': attributes.logoAssetId } : {},
      },
      assetId: {
        default: null,
        parseHTML: (element: any) => element.getAttribute('data-asset-id') || null,
        renderHTML: (attributes: any) => (attributes.assetId ? { 'data-asset-id': attributes.assetId } : {}),
      },
      placement: {
        default: 'center',
        parseHTML: (element: any) => element.getAttribute('data-placement') || 'center',
        renderHTML: (attributes: any) => ({ 'data-placement': attributes.placement || 'center' }),
      },
      width: {
        default: 'auto',
        parseHTML: (element: any) => element.getAttribute('data-width') || 'auto',
        renderHTML: (attributes: any) => ({ 'data-width': attributes.width || 'auto' }),
      },
      height: {
        default: 180,
        parseHTML: (element: any) => Number(element.getAttribute('data-height')) || 180,
        renderHTML: (attributes: any) => ({ 'data-height': attributes.height || 180 }),
      },
      fit: {
        default: 'contain',
        parseHTML: (element: any) => element.getAttribute('data-fit') || 'contain',
        renderHTML: (attributes: any) => ({ 'data-fit': attributes.fit || 'contain' }),
      },
      textWrap: {
        default: 'inline',
        parseHTML: (element: any) => element.getAttribute('data-text-wrap') || 'inline',
        renderHTML: (attributes: any) => ({ 'data-text-wrap': attributes.textWrap || 'inline' }),
      },
    };
  },

  parseHTML() {
    return [
      { tag: 'figure[data-image-block]' },
      { tag: 'div[data-image-block]' },
      {
        tag: 'img[data-image-block]',
        getAttrs: (element: any) => ({
          src: element.getAttribute('src') || '',
          alt: element.getAttribute('alt') || 'Image placeholder',
          imageType: element.getAttribute('data-image-type') || 'image',
        }),
      },
    ];
  },

  renderHTML({ HTMLAttributes }: any) {
    const attrs = HTMLAttributes || {};
    const {
      imageType,
      src,
      alt,
      caption,
      placeholderText,
      clubLogoAssetId,
      logoAssetId,
      assetId,
      placement,
      width,
      height,
      fit,
      textWrap,
      class: _className,
      ...rest
    } = attrs;
    const normalizedType = imageType || 'image';
    const selectedAssetId = clubLogoAssetId || logoAssetId || assetId || '';
    const rootAttrs = mergeAttributes(rest, {
      'data-image-block': 'true',
      'data-image-type': normalizedType,
      'data-image-src': src || '',
      'data-image-alt': alt || 'Image placeholder',
      'data-caption': caption || '',
      'data-placeholder-text': placeholderText || 'Select an image to place here',
      ...(clubLogoAssetId ? { 'data-club-logo-id': clubLogoAssetId } : {}),
      ...(logoAssetId ? { 'data-logo-asset-id': logoAssetId } : {}),
      ...(assetId ? { 'data-asset-id': assetId } : {}),
      'data-placement': placement || 'center',
      'data-width': width || 'auto',
      'data-height': height || 180,
      'data-fit': fit || 'contain',
      'data-text-wrap': textWrap || 'inline',
      class: `image-block image-block--${normalizedType} image-block--${placement || 'center'} image-block--wrap-${textWrap || 'inline'}${selectedAssetId ? ' image-block--resolved' : ' image-block--placeholder'}`,
    });

    if (src) {
      return [
        'figure',
        rootAttrs,
        [
          'img',
          {
            src,
            alt: alt || 'Template image',
            class: 'image-block__img',
            style: `max-height: ${height || 180}px; width: ${width || 'auto'}; object-fit: ${fit || 'contain'};`,
          },
        ],
        ...(caption ? [['figcaption', { class: 'image-block__caption' }, caption]] : []),
      ];
    }

    return [
      'figure',
      rootAttrs,
      [
        'div',
        { class: 'image-block__placeholder', 'data-image-placeholder': 'true' },
        [
          'span',
          { class: 'image-block__placeholder-icon', 'aria-hidden': 'true' },
          normalizedType === 'club-logo' || normalizedType === 'logo' ? '◎' : '▧',
        ],
        [
          'strong',
          {},
          normalizedType === 'club-logo' || normalizedType === 'logo' ? 'Club logo placeholder' : 'Image placeholder',
        ],
        ['span', { class: 'image-block__placeholder-copy' }, placeholderText || 'Select an image to place here'],
      ],
      ...(caption ? [['figcaption', { class: 'image-block__caption' }, caption]] : []),
    ];
  },
});

export function createImageBlockNode(attributes: Partial<ImageBlockAttributes> = {}) {
  const selectedAssetId = attributes.clubLogoAssetId || attributes.logoAssetId || attributes.assetId || null;
  const imageType = attributes.imageType || 'image';
  return {
    type: 'imageBlock',
    attrs: {
      imageType,
      src: attributes.src || '',
      alt: attributes.alt || (imageType === 'club-logo' || imageType === 'logo' ? 'Club logo' : 'Template image'),
      caption: attributes.caption || '',
      placeholderText:
        attributes.placeholderText ||
        (imageType === 'club-logo' || imageType === 'logo'
          ? 'Choose a club logo from the asset library'
          : 'Select an image to place here'),
      clubLogoAssetId:
        attributes.clubLogoAssetId || (imageType === 'club-logo' || imageType === 'logo' ? selectedAssetId : null),
      logoAssetId:
        attributes.logoAssetId || (imageType === 'club-logo' || imageType === 'logo' ? selectedAssetId : null),
      assetId: attributes.assetId || selectedAssetId,
      placement: attributes.placement || 'center',
      width: attributes.width || 'auto',
      height: attributes.height || 180,
      fit: attributes.fit || 'contain',
      textWrap: attributes.textWrap || 'inline',
    },
  };
}
