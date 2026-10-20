import React, { useState } from 'react';
import { Plus, Search, GripVertical, Lock, X, Tag } from 'lucide-react';
import { insertFieldChip } from './extensions';

export interface TemplateField {
  key: string;
  label: string;
  type: string;
  required: boolean;
  importance?: 'essential' | 'optional';
  ask?: string;
  defer_ok?: boolean;
  sensitive?: boolean;
  values?: string[];
  computed?: any;
  format?: string;
  ai_suggested?: boolean;
  example?: string;
}

interface FieldsPanelProps {
  fields: TemplateField[];
  onAddField: (field: TemplateField) => void;
  editor: any;
  /** Example values used by Preview instead of [Label] placeholders */
  sampleValues?: Record<string, string>;
  onSampleChange?: (key: string, value: string) => void;
  onPreview?: () => void;
}

export const FieldsPanel: React.FC<FieldsPanelProps> = ({
  fields,
  onAddField,
  editor,
  sampleValues = {},
  onSampleChange,
  onPreview,
}) => {
  const [showSamples, setShowSamples] = useState(false);
  const sampleCount = Object.values(sampleValues).filter((v) => v && v.trim()).length;
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

  // New field form state
  const [newLabel, setNewLabel] = useState('');
  const [newKey, setNewKey] = useState('');
  const [newType, setNewType] = useState('text');
  const [newRequired, setNewRequired] = useState(true);
  const [newExample, setNewExample] = useState('');
  const [newSensitive, setNewSensitive] = useState(false);

  const filteredFields = fields.filter(
    (f) =>
      f.key.toLowerCase().includes(search.toLowerCase()) ||
      f.label.toLowerCase().includes(search.toLowerCase())
  );

  const handleFieldDragStart = (e: React.DragEvent, field: TemplateField) => {
    e.dataTransfer.setData('text/plain', `{{ ${field.key} }}`);
    e.dataTransfer.setData(
      'application/x-clubdocs-field',
      JSON.stringify({
        fieldName: field.key,
        label: field.label,
        fieldType: field.type,
        importance: field.required ? 'essential' : 'optional',
        required: field.required,
        sensitive: field.sensitive || false,
        ask: field.ask || `Please provide ${field.label}`,
      })
    );
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleInsert = (field: TemplateField) => {
    if (!editor) return;
    insertFieldChip(
      editor,
      field.key,
      field.label,
      field.type,
      field.ask || `Please provide ${field.label}`,
      field.required ? 'essential' : 'optional',
      field.required,
      field.sensitive || false
    );
  };

  const handleLabelChange = (val: string) => {
    setNewLabel(val);
    // Auto-derive key if user hasn't explicitly customized newKey
    const clean = val.toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    setNewKey(clean);
  };

  const handleCreateField = (e: React.FormEvent) => {
    e.preventDefault();
    const finalLabel = newLabel.trim();
    if (!finalLabel) return;

    let finalKey = newKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
    if (!finalKey) {
      finalKey = finalLabel.toLowerCase().replace(/[^a-z0-9_]/g, '_');
    }
    // Ensure key starts with a letter
    if (!/^[a-z]/.test(finalKey)) {
      finalKey = `field_${finalKey}`;
    }

    const newField: TemplateField = {
      key: finalKey,
      label: finalLabel,
      type: newType,
      required: newRequired,
      importance: newRequired ? 'essential' : 'optional',
      sensitive: newSensitive,
      ask: `Please enter ${finalLabel}`,
      example: newExample.trim() || undefined,
    };

    onAddField(newField);

    // If an example value was typed, store it in sample values
    if (newExample.trim() && onSampleChange) {
      onSampleChange(finalKey, newExample.trim());
    }

    // Also auto-insert chip if editor is focused
    if (editor) {
      handleInsert(newField);
    }

    setShowAddModal(false);
    setNewLabel('');
    setNewKey('');
    setNewType('text');
    setNewRequired(true);
    setNewExample('');
    setNewSensitive(false);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50/50">
      {/* Top Search & Add Bar */}
      <div className="p-3 border-b border-slate-200 bg-white space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Tag className="w-3.5 h-3.5 text-brand-600" />
            <span className="text-xs font-bold text-slate-800">
              Template Fields ({fields.length})
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1 px-2.5 py-1 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create Field</span>
          </button>
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search fields or identifiers…"
            className="w-full text-xs pl-8 pr-3 py-1.5 border border-slate-200 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      </div>

      {/* Sample data for Preview */}
      {onSampleChange && fields.length > 0 && (
        <div className="border-b border-slate-200 bg-white">
          <button
            type="button"
            onClick={() => setShowSamples(!showSamples)}
            aria-expanded={showSamples}
            className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
          >
            <span>Sample data for preview{sampleCount ? ` (${sampleCount})` : ''}</span>
            <span className="text-brand-600 font-medium">{showSamples ? 'Hide' : 'Fill in'}</span>
          </button>
          {showSamples && (
            <div className="px-3 pb-3 space-y-2 max-h-64 overflow-y-auto">
              <p className="text-[11px] text-slate-500 leading-tight">
                Type example values to see how a filled document looks. Used for Live Preview only.
              </p>
              {fields
                .filter((f) => f.type !== 'table')
                .map((f) => (
                  <label key={f.key} className="block">
                    <span className="block text-[11px] font-medium text-slate-600 mb-0.5">
                      {f.label} <span className="font-mono text-slate-400">({f.key})</span>
                    </span>
                    <input
                      className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500 bg-slate-50 focus:bg-white"
                      value={sampleValues[f.key] || ''}
                      onChange={(e) => onSampleChange(f.key, e.target.value)}
                      placeholder={f.example || `e.g. Sample ${f.label}`}
                    />
                  </label>
                ))}
              {onPreview && (
                <button
                  type="button"
                  onClick={onPreview}
                  className="w-full py-1.5 px-3 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-semibold transition mt-1"
                >
                  Preview with these values
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Field List / Empty State */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {fields.length === 0 ? (
          <div className="text-center py-10 px-4 rounded-xl border border-dashed border-slate-200 bg-white">
            <Tag className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="font-semibold text-slate-700 text-xs mb-1">No fields yet</p>
            <p className="text-[11px] text-slate-500 mb-3 leading-relaxed">
              Click <strong className="text-brand-600">Create Field</strong> or type <code className="bg-slate-100 px-1 py-0.5 rounded text-brand-700 font-mono">{'{{'}</code> in the document.
            </p>
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-brand-50 hover:bg-brand-100 text-brand-700 font-semibold rounded-lg text-xs transition"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create New Field</span>
            </button>
          </div>
        ) : filteredFields.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-xs">
            No fields match &ldquo;{search}&rdquo;.
          </div>
        ) : (
          filteredFields.map((field) => {
            const isReq = field.required || field.importance === 'essential';
            return (
              <div
                key={field.key}
                draggable
                onDragStart={(e) => handleFieldDragStart(e, field)}
                onClick={() => handleInsert(field)}
                className="group flex items-center justify-between p-2.5 bg-white border border-slate-200 hover:border-brand-300 rounded-xl shadow-xs hover:shadow transition cursor-pointer select-none"
                title="Click to insert or drag into document"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <div className="min-w-0">
                    <div className="font-semibold text-xs text-slate-800 truncate flex items-center gap-1">
                      <span>{field.label}</span>
                      {isReq && <span className="text-rose-500 font-bold text-xs" title="Required">*</span>}
                    </div>
                    <div className="text-[10px] font-mono text-slate-400 truncate">
                      {`{{ ${field.key} }}`}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {field.sensitive && (
                    <span className="p-0.5 rounded bg-amber-100 text-amber-800" title="Sensitive Field">
                      <Lock className="w-3 h-3" />
                    </span>
                  )}
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 uppercase">
                    {field.type}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add Field Modal / Form */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-in fade-in">
          <form
            onSubmit={handleCreateField}
            className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-sm w-full p-5 space-y-3.5 animate-in zoom-in-95"
          >
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="font-bold text-slate-900 text-sm">Create New Field</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Field Label <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={newLabel}
                onChange={(e) => handleLabelChange(e.target.value)}
                placeholder="e.g. Event Name, Chief Guest, Venue"
                className="w-full text-xs px-3 py-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
                required
                autoFocus
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Identifier (Key)
                </label>
                <input
                  type="text"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder="event_name"
                  className="w-full text-xs font-mono px-2.5 py-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none bg-slate-50"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Type
                </label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
                >
                  <option value="text">Text</option>
                  <option value="date">Date</option>
                  <option value="time">Time</option>
                  <option value="money">Money (INR)</option>
                  <option value="number">Number</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Example Value (for Preview)
              </label>
              <input
                type="text"
                value={newExample}
                onChange={(e) => setNewExample(e.target.value)}
                placeholder="e.g. Annual Photography Walk"
                className="w-full text-xs px-3 py-1.5 border border-slate-300 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none"
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={newRequired}
                  onChange={(e) => setNewRequired(e.target.checked)}
                  className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="text-xs text-slate-700 font-medium">Required field</span>
              </label>

              <label className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={newSensitive}
                  onChange={(e) => setNewSensitive(e.target.checked)}
                  className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                />
                <span className="text-xs text-slate-700 font-medium">Sensitive (Bank/PAN)</span>
              </label>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
              >
                Create and Insert
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
