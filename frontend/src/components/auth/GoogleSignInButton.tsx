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
            error_callback?: (error: any) => void;
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
          disableAutoSelect: () => void;
        };
      };
    };
  }
}

interface GoogleSignInButtonProps {
  inviteCode?: string;
  onSuccess: (user: User) => void;
  onError: (message: string, isDomainError?: boolean) => void;
}

let gsiScriptPromise: Promise<void> | null = null;
let hasWarnedMissingClientId = false;
let isGsiInitialized = false;
let globalGsiCallback: ((response: { credential: string }) => void) | null = null;
let globalGsiErrorCallback: ((error: any) => void) | null = null;

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

  // The parent re-renders on every keystroke; keep the latest props in a ref so the
  // Google button is initialised once instead of being torn down and redrawn each time.
  const latest = useRef({ inviteCode, onSuccess, onError, loginWithGoogle });
  latest.current = { inviteCode, onSuccess, onError, loginWithGoogle };

  useEffect(() => {
    if (!clientId) {
      if (!hasWarnedMissingClientId) {
        console.warn('VITE_GOOGLE_CLIENT_ID is not configured. Google Sign-In is disabled.');
        hasWarnedMissingClientId = true;
      }
      return;
    }
    let cancelled = false;
    loadGoogleScript()
      .then(() => {
        if (!cancelled) setScriptReady(true);
      })
      .catch(() => {
        if (!cancelled) latest.current.onError('Failed to load Google Sign-In script. Please check your network.', false);
      });

    return () => {
      cancelled = true;
    };
  }, [clientId]);

  useEffect(() => {
    if (!clientId || !scriptReady || !buttonContainerRef.current || !window.google?.accounts?.id) {
      return;
    }

    // Google draws the button asynchronously, so a re-run (e.g. React StrictMode) could add a second
    // one. Draw into a fresh slot each time and drop it on cleanup.
    const container = buttonContainerRef.current;
    const slot = document.createElement('div');
    container.replaceChildren(slot);

    const handleCallback = async (response: { credential: string }) => {
      const { inviteCode: code, onSuccess: ok, onError: fail, loginWithGoogle: signIn } = latest.current;
      if (!response?.credential) {
        fail('Google sign-in was cancelled or blocked. Please try again with your SVNIT account.', false);
        return;
      }
      try {
        const user = await signIn(response.credential, code || undefined);
        ok(user);
      } catch (err: any) {
        const isDomain =
          err?.status === 403 &&
          (err?.detail?.code === 'EMAIL_DOMAIN_NOT_ALLOWED' ||
            (err?.message || '').toLowerCase().includes('official svnit email') ||
            (err?.message || '').toLowerCase().includes('email') ||
            (err?.message || '').toLowerCase().includes('svnit'));
        fail(err.message || 'Google sign-in failed', Boolean(isDomain));
      }
    };

    const handleErrorCallback = (error: any) => {
      console.warn('Google Sign-In error:', error);
      const { onError: fail } = latest.current;
      fail('Google sign-in was cancelled or blocked. Please try again with your SVNIT account.', false);
    };

    globalGsiCallback = handleCallback;
    globalGsiErrorCallback = handleErrorCallback;

    if (!isGsiInitialized) {
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => {
          if (globalGsiCallback) {
            globalGsiCallback(response);
          }
        },
        error_callback: (error) => {
          if (globalGsiErrorCallback) {
            globalGsiErrorCallback(error);
          }
        },
        hd: 'svnit.ac.in',
        ux_mode: 'popup',
        auto_select: false,
        use_fedcm_for_prompt: true,
      });
      isGsiInitialized = true;
    }

    const parentWidth = container.parentElement?.clientWidth || 360;
    const buttonWidth = Math.min(Math.max(parentWidth, 240), 400);

    window.google.accounts.id.renderButton(slot, {
      theme: 'outline',
      size: 'large',
      text: 'signin_with',
      shape: 'pill',
      width: buttonWidth,
    });
    return () => slot.remove();
  }, [scriptReady, clientId]);

  if (!clientId) return null;

  return (
    <div className="w-full flex justify-center py-1">
      <div ref={buttonContainerRef} className="min-h-[44px] flex items-center justify-center w-full" />
    </div>
  );
};
