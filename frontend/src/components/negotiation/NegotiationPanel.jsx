import React, { useState } from 'react';
import {
  Bot,
  User,
  Shield,
  Clock,
  DollarSign,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RotateCcw,
  Send,
  Sparkles,
  ArrowRight,
  TrendingDown,
  Layers,
  MessageSquare,
  ChevronRight,
  Info
} from 'lucide-react';
import { negotiationsAPI, vendorPortalAPI } from '../../api';

export default function NegotiationPanel({
  session,
  events = [],
  userRole = 'Lead Procurement Officer',
  onActionComplete,
  onRefresh
}) {
  const [actionLoading, setActionLoading] = useState(false);
  const [comment, setComment] = useState('');
  const [manualPrice, setManualPrice] = useState('');
  const [showCounterModal, setShowCounterModal] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const isVendorUser = userRole === 'Vendor';
  const sessionId = session?.id || session?.session_id;

  // Format Status Badge
  const renderStatusBadge = (status) => {
    switch (status?.toUpperCase()) {
      case 'ACCEPTED':
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> ACCEPTED
          </span>
        );
      case 'NEGOTIATING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
            <Bot className="w-3.5 h-3.5 text-blue-600" /> NEGOTIATING
          </span>
        );
      case 'PENDING_APPROVAL':
      case 'PENDING_GOV_APPROVAL':
      case 'ESCALATED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> PENDING GOV APPROVAL
          </span>
        );
      case 'PENDING_VENDOR_APPROVAL':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-purple-50 text-purple-800 border border-purple-200">
            <Clock className="w-3.5 h-3.5 text-purple-600" /> PENDING VENDOR APPROVAL
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3.5 h-3.5 text-rose-600" /> REJECTED
          </span>
        );
      case 'INITIATED':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            <Clock className="w-3.5 h-3.5 text-slate-500" /> INITIATED
          </span>
        );
    }
  };

  // Speaker formatting and avatars
  const getSpeakerConfig = (speakerRole) => {
    const s = (speakerRole || '').toUpperCase();
    if (s.includes('GOV') && (s.includes('AGENT') || s === 'GOVERNMENT')) {
      return {
        label: 'Government Procurement Agent',
        subtext: 'Bilateral Algorithmic Policy Buyer',
        type: 'GOV_AGENT',
        avatarBg: 'bg-blue-600 text-white',
        bubbleBg: 'bg-blue-50/70 border-blue-200 text-slate-900',
        badgeBg: 'bg-blue-100 text-blue-800 border-blue-200',
        icon: Bot,
        align: 'left'
      };
    } else if (s.includes('VENDOR') && (s.includes('AGENT') || s === 'VENDOR')) {
      return {
        label: 'Vendor Sales Agent',
        subtext: 'Commercial AI Negotiator',
        type: 'VENDOR_AGENT',
        avatarBg: 'bg-purple-600 text-white',
        bubbleBg: 'bg-purple-50/70 border-purple-200 text-slate-900',
        badgeBg: 'bg-purple-100 text-purple-800 border-purple-200',
        icon: Bot,
        align: 'right'
      };
    } else if (s.includes('HUMAN') && s.includes('GOV')) {
      return {
        label: 'Human Government Officer',
        subtext: 'Executive Authority Intervention',
        type: 'HUMAN_GOV',
        avatarBg: 'bg-amber-600 text-white',
        bubbleBg: 'bg-amber-50/80 border-amber-200 text-slate-900',
        badgeBg: 'bg-amber-100 text-amber-900 border-amber-300',
        icon: User,
        align: 'left'
      };
    } else if (s.includes('HUMAN') && s.includes('VENDOR')) {
      return {
        label: 'Human Vendor Representative',
        subtext: 'Commercial Director Intervention',
        type: 'HUMAN_VENDOR',
        avatarBg: 'bg-emerald-600 text-white',
        bubbleBg: 'bg-emerald-50/80 border-emerald-200 text-slate-900',
        badgeBg: 'bg-emerald-100 text-emerald-900 border-emerald-300',
        icon: User,
        align: 'right'
      };
    } else {
      return {
        label: 'LokProcure Protocol',
        subtext: 'Deterministic State Engine',
        type: 'SYSTEM',
        avatarBg: 'bg-slate-700 text-white',
        bubbleBg: 'bg-[#f5f4f0] border-[#e8e6df] text-slate-800',
        badgeBg: 'bg-slate-200 text-slate-800 border-slate-300',
        icon: Shield,
        align: 'center'
      };
    }
  };

  // Government human escalation actions
  const handleGovAction = async (decision) => {
    if (!sessionId) return;
    setActionLoading(true);
    setError('');
    setSuccessMsg('');
    try {
      const resp = await negotiationsAPI.actionEscalation(
        sessionId,
        decision,
        comment || (decision === 'APPROVE' ? 'Executive exception approved' : 'Proposal rejected by procurement authority')
      );
      setSuccessMsg(`Escalation decision recorded: ${decision}`);
      
      // If approved, trigger auto-resume
      if (decision === 'APPROVE') {
        try {
          await negotiationsAPI.resumeNegotiation(sessionId);
          setSuccessMsg('Escalation approved and negotiation successfully resumed!');
        } catch (resumeErr) {
          console.warn('Resume triggered with warning:', resumeErr);
        }
      }

      if (onActionComplete) onActionComplete(resp);
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Gov escalation action error:', err);
      setError(err?.response?.data?.detail || 'Failed to execute escalation action');
    } finally {
      setActionLoading(false);
      setComment('');
      setShowCounterModal(false);
    }
  };

  // Vendor human escalation actions
  const handleVendorAction = async (decision) => {
    if (!sessionId) return;
    setActionLoading(true);
    setError('');
    setSuccessMsg('');
    try {
      // In bilateral protocol, vendor records their acceptance/rejection
      const resp = await negotiationsAPI.actionEscalation(
        sessionId,
        decision,
        comment || (decision === 'APPROVE' ? 'Commercial offer confirmed by vendor' : 'Vendor declined terms')
      );
      setSuccessMsg(`Vendor decision recorded: ${decision}`);

      if (onActionComplete) onActionComplete(resp);
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Vendor escalation action error:', err);
      setError(err?.response?.data?.detail || 'Failed to submit vendor action');
    } finally {
      setActionLoading(false);
      setComment('');
      setShowCounterModal(false);
    }
  };

  const isEscalatedState = ['ESCALATED', 'PENDING_APPROVAL', 'PENDING_GOV_APPROVAL'].includes(
    session?.status?.toUpperCase()
  );
  const isVendorPendingState = session?.status?.toUpperCase() === 'PENDING_VENDOR_APPROVAL';

  return (
    <div className="enterprise-card p-5 space-y-5 animate-fade-in bg-[#fbfbfa]">
      {/* Top Banner: Session Info & Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#e8e6df] pb-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] uppercase font-mono tracking-wider px-2 py-0.5 rounded bg-[#f3f2ec] text-slate-700 border border-[#e8e6df] font-semibold">
              Session #{sessionId || '---'}
            </span>
            <span className="text-xs font-semibold text-slate-700">
              Round: <strong className="font-mono text-slate-900">{session?.current_round ?? events?.length ? Math.max(...events.map(e => e.round || 0)) : 0}</strong>
            </span>
            {renderStatusBadge(session?.status)}
          </div>

          <h3 className="text-base font-bold text-slate-900 mt-1">
            {session?.pr_title || 'Autonomous Procurement Negotiation'}
          </h3>
          <p className="text-xs text-slate-500">
            Counterparty: <strong className="text-slate-800">{session?.vendor_name || 'Qualified Vendor'}</strong>
          </p>
        </div>

        {/* Current Settlement Terms (PUBLIC ONLY) */}
        <div className="flex items-center gap-3 bg-[#f5f4f0] border border-[#e8e6df] px-3.5 py-2 rounded-lg">
          <div className="text-right">
            <span className="text-[10px] uppercase font-mono text-slate-500 block leading-tight">
              Current Offer
            </span>
            <span className="text-sm font-bold font-mono text-slate-900">
              ${Number(session?.current_price || events[events.length - 1]?.price || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="w-px h-6 bg-[#d8d5ca]" />
          <div className="text-right">
            <span className="text-[10px] uppercase font-mono text-slate-500 block leading-tight">
              Delivery SLA
            </span>
            <span className="text-sm font-bold font-mono text-slate-900">
              {session?.current_delivery_days || events[events.length - 1]?.delivery_days || '--'} days
            </span>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}
      {successMsg && (
        <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Public Negotiation Event Transcript */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-slate-500 uppercase font-mono tracking-wider flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-blue-600" />
            Audit Transcript ({events.length} Events)
          </span>
          <span className="text-[10px] font-mono text-slate-400">
            Public Bilateral Protocol Feed
          </span>
        </div>

        {events.length === 0 ? (
          <div className="p-8 text-center bg-[#f5f4f0] rounded-lg border border-[#e8e6df] text-xs text-slate-500">
            No negotiation messages logged yet for this session.
          </div>
        ) : (
          <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
            {events.map((ev, idx) => {
              const cfg = getSpeakerConfig(ev.speaker_role);
              const SpeakerIcon = cfg.icon;
              const hasPrice = ev.price !== null && ev.price !== undefined;
              const hasDays = ev.delivery_days !== null && ev.delivery_days !== undefined;

              return (
                <div
                  key={ev.id || idx}
                  className={`p-3.5 rounded-lg border text-xs space-y-2 transition-all ${cfg.bubbleBg}`}
                >
                  {/* Speaker Header */}
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className={`w-5 h-5 rounded-md flex items-center justify-center shrink-0 ${cfg.avatarBg}`}>
                        <SpeakerIcon className="w-3 h-3" />
                      </div>
                      <div className="flex items-center gap-1.5 truncate">
                        <span className="font-bold text-slate-900">{cfg.label}</span>
                        <span className={`text-[9px] px-1.5 py-0.2 rounded font-mono font-medium border ${cfg.badgeBg}`}>
                          {ev.event_type || 'OFFER'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 font-mono text-[10px] text-slate-500 shrink-0">
                      <span>Round {ev.round ?? 0}</span>
                      {ev.created_at && (
                        <span>• {new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      )}
                    </div>
                  </div>

                  {/* Message body */}
                  <p className="text-slate-700 leading-relaxed pl-7">
                    {ev.message}
                  </p>

                  {/* Offer parameters pill (strictly public offer and days only) */}
                  {(hasPrice || hasDays) && (
                    <div className="pl-7 pt-1 flex items-center gap-2 flex-wrap">
                      {hasPrice && (
                        <span className="inline-flex items-center gap-1 font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-white/80 border border-[#d8d5ca] text-slate-900">
                          <DollarSign className="w-3 h-3 text-emerald-600" />
                          ${Number(ev.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </span>
                      )}
                      {hasDays && (
                        <span className="inline-flex items-center gap-1 font-mono text-[11px] px-2 py-0.5 rounded bg-white/80 border border-[#d8d5ca] text-slate-700">
                          <Calendar className="w-3 h-3 text-blue-600" />
                          {ev.delivery_days} days SLA
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Human Intervention UI (Section 10) */}
      {/* 1. Government Side Controls */}
      {!isVendorUser && isEscalatedState && (
        <div className="p-4 rounded-lg bg-amber-50/70 border border-amber-200 space-y-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-700 mt-0.5 shrink-0" />
            <div>
              <h4 className="text-xs font-bold text-amber-900">
                Executive Intervention Required (Government Authority)
              </h4>
              <p className="text-[11px] text-amber-800">
                The autonomous negotiation proposal exceeds standard algorithmic limits and has been escalated for your review. Choose an authorized action:
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <input
              type="text"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Add justification or condition for approval / rejection (optional)..."
              className="w-full bg-white border border-amber-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-amber-500"
            />

            <div className="flex items-center gap-2 flex-wrap pt-1">
              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleGovAction('APPROVE')}
                className="btn-primary bg-emerald-600 hover:bg-emerald-700 text-xs py-1.5 px-3"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Approve &amp; Resume Negotiation</span>
              </button>

              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleGovAction('REJECT')}
                className="btn-danger text-xs py-1.5 px-3"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject Proposal</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. Vendor Side Controls */}
      {isVendorUser && (isVendorPendingState || isEscalatedState) && (
        <div className="p-4 rounded-lg bg-purple-50/70 border border-purple-200 space-y-3">
          <div className="flex items-start gap-2">
            <User className="w-4 h-4 text-purple-700 mt-0.5 shrink-0" />
            <div>
              <h4 className="text-xs font-bold text-purple-900">
                Commercial Officer Intervention (Vendor Authority)
              </h4>
              <p className="text-[11px] text-purple-800">
                A formal proposal is awaiting your confirmation or commercial sign-off.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <input
              type="text"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Enter commercial notes or acceptance confirmation..."
              className="w-full bg-white border border-purple-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500"
            />

            <div className="flex items-center gap-2 flex-wrap pt-1">
              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleVendorAction('APPROVE')}
                className="btn-primary bg-purple-600 hover:bg-purple-700 text-xs py-1.5 px-3"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Accept Terms</span>
              </button>

              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleVendorAction('REJECT')}
                className="btn-danger text-xs py-1.5 px-3"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Decline Terms</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
