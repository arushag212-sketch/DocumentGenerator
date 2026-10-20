import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { User } from '../../types';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            hd?: string;
            ux_mode?: 'popup' | 'redirect';
            auto_select?: boolean;
            use_fedcm_for_prompt?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              type?: 'standard' | 'icon';
              theme?: 'outline' | 'filled_blue' | 'filled_black';
              size?: 'large' | 'medium' | 'small';
              text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
              shape?: 'rectangular' | 'pill' | 'circle' | 'square';
              logo_alignment?: 'left' | 'center';
              width?: number;
              locale?: string;
            }
          ) => void;
          prompt?: (momentListener?: (notification: any) => void) => void;
        };
      };
    };
  }
}

interface GoogleSignInButtonProps {
  inviteCode?: string;
  onSuccess: (user: User) => void;
  onError: (message: string) => void;
}

let gsiScriptPromise: Promise<void> | null = null;
let hasWarnedMissingClientId = false;

function loadGoogleScript(): Promise<void> {
  if (typeof window !== 'undefined' && window.google?.accounts?.id) {
    return Promise.resolve();
  }
  if (gsiScriptPromise) return gsiScriptPromise;

  gsiScriptPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
    if (existing) {
      if (window.google?.accounts?.id) {
        resolve();
        return;
      }
      existing.addEventListener('load', () => resolve());
      existing.addEventListener('error', (e) => reject(e));
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = (e) => reject(e);
    document.head.appendChild(script);
  });

  return gsiScriptPromise;
}

export const GoogleSignInButton: React.FC<GoogleSignInButtonProps> = ({
  inviteCode,
  onSuccess,
  onError,
}) => {
  const { loginWithGoogle } = useAuth();
  const buttonContainerRef = useRef<HTMLDivElement>(null);
  const [scriptReady, setScriptReady] = useState(false);

  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

  if (!clientId) {
    if (!hasWarnedMissingClientId) {
      console.warn('VITE_GOOGLE_CLIENT_ID is not configured. Google Sign-In is disabled.');
      hasWarnedMissingClientId = true;
    }
    return null;
  }

  useEffect(() => {
    let cancelled = false;
    loadGoogleScript()
      .then(() => {
        if (!cancelled) setScriptReady(true);
      })
      .catch(() => {
        if (!cancelled) onError('Failed to load Google Sign-In script. Please check your network.');
      });

    return () => {
      cancelled = true;
    };
  }, [onError]);

  useEffect(() => {
    if (!scriptReady || !buttonContainerRef.current || !window.google?.accounts?.id) {
      return;
    }

    const container = buttonContainerRef.current;
    container.innerHTML = '';

    const handleCallback = async (response: { credential: string }) => {
      if (!response.credential) {
        onError('No authentication credential received from Google.');
        return;
      }
      try {
        const user = await loginWithGoogle(response.credential, inviteCode || undefined);
        onSuccess(user);
      } catch (err: any) {
        onError(err.message || 'Google sign-in failed');
      }
    };

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleCallback,
      hd: 'svnit.ac.in',
      ux_mode: 'popup',
      auto_select: false,
      use_fedcm_for_prompt: true,
    });

    const parentWidth = container.parentElement?.clientWidth || 360;
    const buttonWidth = Math.min(Math.max(parentWidth, 240), 400);

    window.google.accounts.id.renderButton(container, {
      theme: 'outline',
      size: 'large',
      text: 'signin_with',
      shape: 'pill',
      width: buttonWidth,
    });
  }, [scriptReady, clientId, inviteCode, loginWithGoogle, onSuccess, onError]);

  return (
    <div className="w-full flex justify-center py-1">
      <div ref={buttonContainerRef} className="min-h-[44px] flex items-center justify-center w-full" />
    </div>
  );
};
