import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, ArrowLeft, Mail } from 'lucide-react';

export const PrivacyPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        {/* Header / Back Link */}
        <div className="mb-6 flex items-center justify-between">
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to sign in
          </Link>
          <div className="flex items-center gap-2">
            <img src="/assets/svnit_crest.png" alt="SVNIT Crest" className="h-6 w-6 object-contain" />
            <span className="text-xs font-semibold text-slate-700">SVNIT ClubDocs</span>
          </div>
        </div>

        {/* Card */}
        <div className="surface-card p-6 sm:p-10 shadow-sm">
          <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-200">
            <div className="p-2.5 bg-brand-50 text-brand-700 rounded-lg">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Privacy Policy</h1>
              <p className="text-xs text-slate-500 mt-0.5">SVNIT ClubDocs · Document Generator for Student Clubs</p>
            </div>
          </div>

          <div className="space-y-6 text-sm text-slate-700 leading-relaxed">
            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">1. About ClubDocs</h2>
              <p>
                ClubDocs is a smart document generation, templating, and approval workflow platform designed specifically for student clubs and chapters at the Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">2. Information Received via Google Sign-In</h2>
              <p>
                When you sign in with your SVNIT Google account (<code className="text-xs bg-slate-100 px-1 py-0.5 rounded">@svnit.ac.in</code>), we receive only:
              </p>
              <ul className="list-disc pl-5 mt-2 space-y-1">
                <li>Your full name</li>
                <li>Your institutional email address</li>
                <li>Your profile picture URL</li>
              </ul>
              <p className="mt-2">
                We use this information strictly to authenticate your identity, create your user account, and display your name on club documents and signatures. We do not access your Google Drive, contacts, calendar, or any other personal Google data.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">3. Club Data and AI Features</h2>
              <p>
                We securely store club information, event templates, generated documents, and review logs. When using AI-assisted features (such as generating document drafts, agendas, or sponsorship proposals), document text is sent to Google Gemini to draft content. No personal credentials or private keys are ever shared.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">4. Data Sharing and Protection</h2>
              <p>
                We do not sell, rent, monetize, or share your personal information with third parties or external commercial entities. Access to club documents is restricted to authorized members of your respective club according to role-based access control.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">5. Account Deletion and Data Retention</h2>
              <p>
                You have the right to request deletion of your account and personal information at any time. To request account deletion, contact your club administrator or the platform administrator at the address below.
              </p>
            </section>

            <section className="pt-4 border-t border-slate-200">
              <h2 className="text-base font-semibold text-slate-900 mb-2">6. Contact Information</h2>
              <p className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-slate-400" />
                <span>Contact Email:</span>
                <a href="mailto:arushag212@gmail.com" className="text-brand-700 hover:underline font-medium">
                  arushag212@gmail.com
                </a>
              </p>
            </section>
          </div>
        </div>

        <div className="mt-6 text-center text-xs text-slate-400">
          © {new Date().getFullYear()} SVNIT ClubDocs · Sardar Vallabhbhai National Institute of Technology, Surat
        </div>
      </div>
    </div>
  );
};
