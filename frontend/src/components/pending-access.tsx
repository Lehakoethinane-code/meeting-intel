"use client";
import { signOut } from "next-auth/react";
import { LogOut, Clock } from "lucide-react";

interface Props {
  userEmail: string;
}

/** Shown to users who have signed in with a valid @taxconsulting.co.za account
 *  but have not yet been registered by an administrator. */
export default function PendingAccess({ userEmail }: Props) {
  return (
    <div className="min-h-screen bg-[#f0f4ff] flex flex-col items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md overflow-hidden">
        <div className="bg-[#003366] border-b-4 border-[#C9A52C] px-8 py-6 text-center">
          <div className="w-12 h-12 bg-[#C9A52C] rounded-full flex items-center justify-center mx-auto mb-3">
            <Clock size={22} className="text-[#003366]" />
          </div>
          <h1 className="text-white font-bold text-[18px]">Access Pending</h1>
          <p className="text-white/60 text-[13px] mt-1">TaxConsulting SA — Meeting Intelligence</p>
        </div>

        <div className="px-8 py-6">
          <p className="text-[#374151] text-[14px] leading-relaxed mb-3">
            Your account <strong className="text-[#003366]">{userEmail}</strong> is not yet registered on the platform.
          </p>
          <p className="text-[#6b7280] text-[13px] leading-relaxed mb-6">
            Please contact your administrator to have your account activated. Once registered, you will be able to access and review meeting transcripts for meetings you are part of.
          </p>

          <div className="bg-[#f8fafc] border border-[#dde1e8] rounded-lg px-4 py-3 text-[12.5px] text-[#6b7280] mb-6">
            <strong className="text-[#374151]">Need help?</strong> Reach out to the IT and Devs team or your system administrator to request access.
          </div>

          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="w-full flex items-center justify-center gap-2 bg-[#003366] hover:bg-[#0a4a8c] text-white text-[13.5px] font-semibold px-4 py-2.5 rounded-md transition-colors"
          >
            <LogOut size={15} /> Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
