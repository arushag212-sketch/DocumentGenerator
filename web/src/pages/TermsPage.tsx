import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, ArrowLeft, Mail } from 'lucide-react';

export const TermsPage: React.FC = () => {
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
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Terms of Service</h1>
              <p className="text-xs text-slate-500 mt-0.5">SVNIT ClubDocs Acceptable Use Policy</p>
            </div>
          </div>

          <div className="space-y-6 text-sm text-slate-700 leading-relaxed">
            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">1. Eligibility and Accounts</h2>
              <p>
                ClubDocs is exclusively available to active students, faculty mentors, and staff of the Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat. Access requires a valid SVNIT institutional email account (<code className="text-xs bg-slate-100 px-1 py-0.5 rounded">@svnit.ac.in</code> or authorized sub-domains).
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">2. Acceptable Use</h2>
              <p>
                You agree to use ClubDocs solely for legitimate club administration, event organization, letterhead communications, and document approvals associated with recognized SVNIT student clubs, societies, and chapters.
              </p>
              <ul className="list-disc pl-5 mt-2 space-y-1">
                <li>You may not generate false, fraudulent, or unauthorized institute documents.</li>
                <li>You may not forge signatures or misuse institute letterheads or administrative seals.</li>
                <li>You may not attempt to gain unauthorized access to other clubs or sensitive administrative records.</li>
              </ul>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">3. Accuracy and Document Verification</h2>
              <p>
                Clubs and their authorized officers are responsible for ensuring the factual accuracy of financial proposals, participant lists, certificates, and approval requests generated through the platform. Digital verification codes on generated documents serve to confirm authenticity.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">4. AI Features & Responsible Use</h2>
              <p>
                ClubDocs provides AI-assisted content drafting powered by Google Gemini. Users are responsible for reviewing and validating all AI-generated drafts prior to official submission or distribution.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-slate-900 mb-2">5. Service Availability & Modifications</h2>
              <p>
                ClubDocs is continuously developed to support student club workflows. The platform administration reserves the right to suspend or terminate access for accounts that violate SVNIT policies or these terms.
              </p>
            </section>

            <section className="pt-4 border-t border-slate-200">
              <h2 className="text-base font-semibold text-slate-900 mb-2">6. Inquiries</h2>
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
