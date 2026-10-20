import React, { useState } from 'react';
import { Plus, Search, GripVertical, Lock, X } from 'lucide-react';
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
}

interface FieldsPanelProps {
  fields: TemplateField[];
  onAddField: (field: TemplateField) => void;
  editor: any;
}

export const FieldsPanel: React.FC<FieldsPanelProps> = ({ fields, onAddField, editor }) => {
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newType, setNewType] = useState('text');
  const [newImportance, setNewImportance] = useState<'essential' | 'optional'>('essential');
  const [newSensitive, setNewSensitive] = useState(false);
  const [newAsk, setNewAsk] = useState('');

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
        importance: field.importance || (field.required ? 'essential' : 'optional'),
        required: field.importance === 'essential' || field.required,
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
      field.importance || (field.required ? 'essential' : 'optional'),
      field.required,
      field.sensitive || false
    );
  };

  const handleCreateField = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim()) return;

    // Validate identifier format: ^[a-z][a-z0-9_]{0,39}$
    const cleanKey = newKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
    const label = newLabel.trim() || cleanKey;

    const newField: TemplateField = {
      key: cleanKey,
      label,
      type: newType,
      required: newImportance === 'essential',
      importance: newImportance,
      sensitive: newSensitive,
      ask: newAsk.trim() || `Please enter ${label}`,
    };

    onAddField(newField);
    setShowAddModal(false);
    setNewKey('');
    setNewLabel('');
    setNewAsk('');
    setNewSensitive(false);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50/50">
      {/* Top Search & Add Bar */}
      <div className="p-3 border-b border-slate-200 bg-white space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-800">
            Template Fields ({fields.length})
          </span>
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1 px-2.5 py-1 bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 rounded text-xs font-semibold transition"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Field
          </button>
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search fields…"
            className="w-full text-xs pl-8 pr-3 py-1.5 border border-slate-200 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      </div>

      {/* Field List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filteredFields.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-xs">
            No fields match your search.
          </div>
        ) : (
          filteredFields.map((field) => {
            const isEssential = field.importance === 'essential' || field.required;
            return (
              <div
                key={field.key}
                draggable
                onDragStart={(e) => handleFieldDragStart(e, field)}
                onClick={() => handleInsert(field)}
                className="group flex items-center justify-between p-2.5 bg-white border border-slate-200 hover:border-brand-300 rounded-lg shadow-sm hover:shadow transition cursor-pointer select-none"
                title="Click to insert or drag onto page"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
                  <div className="min-w-0">
                    <div className="font-semibold text-xs text-slate-800 truncate">
                      {field.label}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 truncate">
                      {field.key}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {field.sensitive && (
                    <span className="p-0.5 rounded bg-amber-100 text-amber-800" title="Sensitive Field">
                      <Lock className="w-3 h-3" />
                    </span>
                  )}
                  <span
                    className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full border ${
                      isEssential
                        ? 'bg-rose-50 text-rose-700 border-rose-200'
                        : 'bg-slate-100 text-slate-600 border-slate-200'
                    }`}
                  >
                    {isEssential ? 'Essential' : 'Optional'}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add Field Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <form
            onSubmit={handleCreateField}
            className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-sm w-full p-5 space-y-4 animate-in fade-in zoom-in-95"
          >
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="font-bold text-slate-800 text-sm">Add New Template Field</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Field Identifier (Key)
              </label>
              <input
                type="text"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="e.g. event_name"
                className="w-full text-xs font-mono px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-brand-500 focus:outline-none"
                required
              />
              <span className="text-[11px] text-slate-400">Lowercase letters, numbers, and underscores.</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Display Label
              </label>
              <input
                type="text"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                placeholder="e.g. Event Name"
                className="w-full text-xs px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-brand-500 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Field Type
                </label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-brand-500 focus:outline-none"
                >
                  <option value="text">Text</option>
                  <option value="date">Date</option>
                  <option value="time">Time</option>
                  <option value="money">Money (INR)</option>
                  <option value="number">Number</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Importance
                </label>
                <select
                  value={newImportance}
                  onChange={(e) => setNewImportance(e.target.value as any)}
                  className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-brand-500 focus:outline-none"
                >
                  <option value="essential">Essential</option>
                  <option value="optional">Optional</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="sensitiveField"
                checked={newSensitive}
                onChange={(e) => setNewSensitive(e.target.checked)}
                className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <label htmlFor="sensitiveField" className="text-xs text-slate-700 font-medium cursor-pointer">
                Sensitive Field (Bank, PAN, GST)
              </label>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded text-xs font-semibold transition"
              >
                Create Field
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
