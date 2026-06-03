"use client";
import { useState } from "react";
import { signIn } from "next-auth/react";

const HAS_ENTRA = !!(
  process.env.NEXT_PUBLIC_HAS_ENTRA === "true"
);

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleDevLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    await signIn("dev-login", { email, callbackUrl: "/" });
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-[#F0F2F5] flex items-center justify-center">
      <div className="bg-white rounded-lg border border-[#dde1e8] shadow-md overflow-hidden w-full max-w-sm">
        <div className="bg-[#003366] border-b-4 border-[#C9A52C] px-8 py-7 text-center">
          <div className="inline-flex items-center gap-3 mb-1">
            <div className="w-10 h-10 bg-[#C9A52C] rounded-lg flex items-center justify-center font-extrabold text-[#003366] text-base">
              MI
            </div>
            <span className="text-white font-semibold text-lg">
              Tax<span className="text-[#C9A52C]">Consulting</span> SA
            </span>
          </div>
          <p className="text-white/60 text-sm mt-2">Meeting Intelligence</p>
        </div>
        <div className="px-8 py-8">
          {HAS_ENTRA ? (
            <div className="text-center">
              <p className="text-[#6b7280] text-sm mb-6">
                Sign in with your Taxconsulting SA Microsoft account to access meeting notes.
              </p>
              <button
                type="button"
                onClick={() => signIn("microsoft-entra-id", { callbackUrl: "/" })}
                className="w-full bg-[#003366] hover:bg-[#0a4a8c] text-white font-semibold py-2.5 px-4 rounded-md text-sm transition-colors flex items-center justify-center gap-2"
              >
                <svg width="18" height="18" viewBox="0 0 21 21" fill="none">
                  <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                  <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                  <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                  <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
                </svg>
                Sign in with Microsoft
              </button>
            </div>
          ) : (
            <form onSubmit={handleDevLogin} className="flex flex-col gap-4">
              <p className="text-[#6b7280] text-sm text-center">
                Enter your work email to continue.
              </p>
              <div>
                <label htmlFor="email" className="block text-xs font-semibold text-[#374151] mb-1">
                  Work email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@taxconsulting.co.za"
                  className="w-full border border-[#dde1e8] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#003366] focus:border-transparent"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-[#003366] hover:bg-[#0a4a8c] disabled:opacity-60 text-white font-semibold py-2.5 px-4 rounded-md text-sm transition-colors"
              >
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
