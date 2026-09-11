import React, { useState } from 'react';
import { Shield, Sparkles, Building2, UserCheck, ArrowRight, Lock, Mail, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authAPI } from '../api';

const DEMO_PERSONAS = [
  {
    role: 'Lead Procurement Officer',
    name: 'Priya Sharma',
    email: 'admin@procureiq.internal',
    password: 'admin123',
    department: 'Supply Chain',
    desc: 'Full Procurement authority, RFQ panel management & PO release',
    badge: 'Super Admin / Lead'
  },
  {
    role: 'Plant Head',
    name: 'Rajesh Verma',
    email: 'planthead@procureiq.internal',
    password: 'plant123',
    department: 'Operations',
    desc: 'Approver for Rule 1: Operations CapEx > $100,000',
    badge: 'Rule 1 Approver'
  },
  {
    role: 'VP Operations',
    name: 'Kavita Reddy',
    email: 'vpops@procureiq.internal',
    password: 'vp123',
    department: 'Operations',
    desc: 'Approver for Rule 2: Critical Urgency & Bulk Quantity > 500',
    badge: 'Rule 2 Approver'
  },
  {
    role: 'Finance Director',
    name: 'Arjun Patel',
    email: 'finance@procureiq.internal',
    password: 'finance123',
    department: 'Finance',
    desc: 'Approver for Rule 3: High Value Purchase > $50,000',
    badge: 'Rule 3 Approver'
  },
  {
    role: 'Department Manager',
    name: 'Rohan Mehta',
    email: 'deptmgr@procureiq.internal',
    password: 'dept123',
    department: 'Engineering',
    desc: 'Approver for Rule 4: Standard Departmental PRs',
    badge: 'Rule 4 Approver'
  }
];

export default function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState('admin@procureiq.internal');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e, customEmail, customPassword) => {
    if (e) e.preventDefault();
    const loginEmail = customEmail || email;
    const loginPassword = customPassword || password;

    setError('');
    setLoading(true);

    try {
      const data = await authAPI.login(loginEmail, loginPassword);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      onLoginSuccess(data.user, data.access_token);
    } catch (err) {
      console.error('Login error:', err);
      setError(err.response?.data?.detail || 'Invalid email or password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickPersona = (persona) => {
    setEmail(persona.email);
    setPassword(persona.password);
    handleLogin(null, persona.email, persona.password);
  };

  return (
    <div className="min-h-screen w-full bg-[#f5f4f0] flex flex-col justify-center items-center px-4 py-10 relative">
      {/* Main Container */}
      <div className="w-full max-w-5xl z-10 space-y-8">
        {/* Header Branding */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold uppercase tracking-wider">
            <span>NetSuite-Integrated Procurement ERP</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-slate-900 flex items-center justify-center gap-2">
            ProcureIQ <span className="text-blue-600">Core</span>
          </h1>
          <p className="text-slate-500 text-xs md:text-sm max-w-xl mx-auto">
            Autonomous Procurement Optimization Engine: Streamlining PR-to-PO lifecycle, 
            Tiered Vendor Scoring, Multi-Rule Dynamic Approvals &amp; 3-Way Match Verification.
          </p>
        </div>

        {/* 2-Column Section: Left is Form, Right is Quick Personas */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Direct Login */}
          <div className="lg:col-span-5 enterprise-card p-6 md:p-7 space-y-5 bg-[#fbfbfa] border border-[#e8e6df] shadow-xl">
            <div className="border-b border-[#e8e6df] pb-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Lock className="w-4 h-4 text-blue-600" /> Sign In
              </h2>
              <p className="text-slate-500 text-xs mt-0.5">Authenticate with your corporate credentials</p>
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2 animate-fade-in">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-3.5">
              <div className="space-y-1">
                <label className="block text-xs font-medium text-slate-700">Corporate Email</label>
                <div className="relative">
                  <Mail className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="name@procureiq.internal"
                    className="w-full bg-white border border-[#dcd9ce] rounded-lg pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 transition-colors shadow-sm"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-medium text-slate-700">Password</label>
                <div className="relative">
                  <Lock className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                    className="w-full bg-white border border-[#dcd9ce] rounded-lg pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 transition-colors shadow-sm"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full py-2.5 text-xs justify-center"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <span>Access ERP Workspace</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>

            <div className="pt-3 border-t border-[#e8e6df] text-[11px] text-slate-500 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> NetSuite Sandbox Synced
              </span>
              <span className="font-mono text-[10px]">v1.0.0</span>
            </div>
          </div>

          {/* Right Column: Quick Demo Persona Switcher */}
          <div className="lg:col-span-7 enterprise-card p-6 space-y-4 bg-[#fbfbfa] border border-[#e8e6df] shadow-xl">
            <div className="flex items-center justify-between border-b border-[#e8e6df] pb-3">
              <div>
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                  <UserCheck className="w-4 h-4 text-indigo-600" /> Quick Demo Personas
                </h2>
                <p className="text-slate-500 text-xs mt-0.5">
                  1-Click instant sign in to test role-specific approval rules &amp; workflows
                </p>
              </div>
              <span className="px-2 py-0.5 rounded bg-[#f3f2ec] text-slate-700 border border-[#e8e6df] text-[10px] font-semibold">
                5 Roles
              </span>
            </div>

            <div className="space-y-2">
              {DEMO_PERSONAS.map((persona) => (
                <button
                  key={persona.email}
                  type="button"
                  onClick={() => handleQuickPersona(persona)}
                  disabled={loading}
                  className="w-full text-left p-3 rounded-lg bg-[#f5f4f0] border border-[#e8e6df] hover:border-[#d8d5ca] hover:bg-[#eeebe3] transition-colors group flex items-center justify-between cursor-pointer disabled:opacity-50 shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-[#e8e6df] text-slate-700 font-bold text-xs flex items-center justify-center">
                      {persona.name.split(' ').map(n => n[0]).join('')}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-slate-900 text-xs font-semibold group-hover:text-blue-600 transition-colors">
                          {persona.name}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#fbfbfa] text-slate-700 border border-[#e8e6df] font-medium">
                          {persona.role}
                        </span>
                      </div>
                      <p className="text-slate-500 text-[11px] mt-0.5 line-clamp-1">{persona.desc}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="hidden sm:inline-block text-[10px] text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity font-medium">
                      Select
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-800 transition-colors" />
                  </div>
                </button>
              ))}
            </div>

            <div className="p-3 rounded-lg bg-[#f5f4f0] border border-[#e8e6df] flex items-center justify-between text-[11px] text-slate-600">
              <span className="flex items-center gap-1.5 text-slate-700">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Multi-tier approval hierarchy pre-configured in SQLite database
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
