import React, { useState, useEffect, forwardRef } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export interface PasswordInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ElementType;
  label?: string;
  labelClassName?: string;
  helper?: React.ReactNode;
  containerClassName?: string;
  resetKey?: any;
}

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  (
    {
      icon: Icon,
      label,
      labelClassName = 'block text-xs font-medium text-slate-700 mb-1',
      helper,
      containerClassName = '',
      className = '',
      id,
      resetKey,
      type: _ignoredType,
      ...props
    },
    ref
  ) => {
    const [visible, setVisible] = useState(false);

    useEffect(() => {
      setVisible(false);
    }, [resetKey]);

    const isInputField = className.includes('input-field');
    const inputClasses = isInputField
      ? `${className} ${Icon ? 'pl-9' : 'pl-3'} pr-10`
      : `w-full ${Icon ? 'pl-9' : 'pl-3'} pr-10 py-2 text-sm border border-slate-300 rounded-lg bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-700/30 focus:border-brand-700 ${className}`;

    const content = (
      <div className="relative">
        {Icon && (
          <Icon className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
        )}
        <input
          {...props}
          ref={ref}
          id={id}
          type={visible ? 'text' : 'password'}
          className={inputClasses}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          onMouseDown={(e) => e.preventDefault()}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-700/50 rounded transition-colors"
        >
          {visible ? (
            <EyeOff className="w-4 h-4" aria-hidden="true" />
          ) : (
            <Eye className="w-4 h-4" aria-hidden="true" />
          )}
        </button>
      </div>
    );

    if (!label && !helper && !containerClassName) {
      return content;
    }

    return (
      <div className={containerClassName}>
        {label && (
          <label htmlFor={id} className={labelClassName}>
            {label}
          </label>
        )}
        {content}
        {helper && <p className="text-xs text-slate-400 mt-1">{helper}</p>}
      </div>
    );
  }
);

PasswordInput.displayName = 'PasswordInput';
