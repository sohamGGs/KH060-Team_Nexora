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
  Info,
  X,
  FileText
} from 'lucide-react';
import { negotiationsAPI, vendorPortalAPI } from '../../api';

export default function NegotiationPanel({
  session,
  events = [],
  escalations = [],
  userRole = 'Lead Procurement Officer',
  onActionComplete,
  onRefresh
}) {
  const [actionLoading, setActionLoading] = useState(false);
  const [comment, setComment] = useState('');
  const [showCounterModal, setShowCounterModal] = useState(false);
  const [counterPrice, setCounterPrice] = useState('');
  const [counterDays, setCounterDays] = useState('');
  const [counterMessage, setCounterMessage] = useState('');
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const isVendorUser = userRole === 'Vendor';
  const isGovUser = !isVendorUser;
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
      case 'PENDING_GOV_APPROVAL':
      case 'PENDING_APPROVAL':
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
      case 'RESUMED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-teal-50 text-teal-800 border border-teal-200">
            <RotateCcw className="w-3.5 h-3.5 text-teal-600" /> RESUMED
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
        label: 'LokProcure Policy Engine',
        subtext: 'Deterministic State & Policy Boundary',
        type: 'SYSTEM',
        avatarBg: 'bg-slate-700 text-white',
        bubbleBg: 'bg-[#f5f4f0] border-[#e8e6df] text-slate-800',
        badgeBg: 'bg-slate-200 text-slate-800 border-slate-300',
        icon: Shield,
        align: 'center'
      };
    }
  };

  // Determine active escalation info
  const allEscalations = session?.escalations || escalations || [];
  const relevantEscalation = allEscalations.find(e => e.status === 'PENDING') || allEscalations[allEscalations.length - 1];

  const currentStatus = (session?.status || '').toUpperCase();
  const isPendingGovState = ['PENDING_GOV_APPROVAL', 'PENDING_APPROVAL', 'ESCALATED'].includes(currentStatus);
  const isPendingVendorState = currentStatus === 'PENDING_VENDOR_APPROVAL';

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
      
      // If approved, trigger resume
      if (decision === 'APPROVE') {
        try {
          await negotiationsAPI.resumeNegotiation(sessionId);
          setSuccessMsg('Escalation approved and negotiation successfully resumed!');
        } catch (resumeErr) {
          console.warn('Resume triggered with notice:', resumeErr);
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
    }
  };

  // Vendor human escalation actions
  const handleVendorAction = async (decision) => {
    if (!sessionId) return;
    setActionLoading(true);
    setError('');
    setSuccessMsg('');
    try {
      const resp = await vendorPortalAPI.actionEscalation(
        sessionId,
        decision,
        comment || (decision === 'APPROVE' ? 'Commercial concession approved by vendor management' : 'Vendor commercial management declined terms')
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
    }
  };

  // Submit manual counteroffer (Gov or Vendor)
  const handleManualCounterSubmit = async (e) => {
    e.preventDefault();
    if (!counterPrice || !counterDays) {
      setError('Please provide both price and delivery days');
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccessMsg('');

    try {
      let resp;
      if (isGovUser) {
        resp = await negotiationsAPI.counterOffer(
          sessionId,
          Number(counterPrice),
          Number(counterDays),
          counterMessage
        );
        setSuccessMsg(`Government counteroffer of $${Number(counterPrice).toLocaleString()} submitted! Vendor Agent is responding.`);
      } else {
        resp = await vendorPortalAPI.counterOffer(
          sessionId,
          Number(counterPrice),
          Number(counterDays),
          counterMessage
        );
        setSuccessMsg(`Vendor counteroffer of $${Number(counterPrice).toLocaleString()} submitted! Government Agent is responding.`);
      }

      setShowCounterModal(false);
      setCounterPrice('');
      setCounterDays('');
      setCounterMessage('');
      if (onActionComplete) onActionComplete(resp);
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Manual counteroffer error:', err);
      setError(err?.response?.data?.detail || 'Failed to submit manual counteroffer');
    } finally {
      setActionLoading(false);
    }
  };

  const currentPrice = session?.current_price ?? (events?.length ? events[events.length - 1]?.price : null);
  const currentDays = session?.current_delivery_days ?? (events?.length ? events[events.length - 1]?.delivery_days : null);

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
              Round: <strong className="font-mono text-slate-900">{session?.current_round ?? (events?.length ? Math.max(...events.map(e => e.round || 0)) : 0)}</strong>
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
            <span className="text-[10px] uppercase tracking-wider text-slate-500 font-mono block">
              Current Offer
            </span>
            <span className="text-sm font-bold font-mono text-slate-900">
              {currentPrice !== null && currentPrice !== undefined
                ? `$${Number(currentPrice).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                : '---'}
            </span>
          </div>

          <div className="w-[1px] h-6 bg-[#d8d5ca]" />

          <div className="text-right">
            <span className="text-[10px] uppercase tracking-wider text-slate-500 font-mono block">
              Delivery
            </span>
            <span className="text-xs font-semibold font-mono text-slate-800">
              {currentDays !== null && currentDays !== undefined
                ? `${currentDays} days`
                : '---'}
            </span>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button type="button" onClick={() => setError('')} className="text-rose-500 hover:text-rose-700">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between">
          <span>{successMsg}</span>
          <button type="button" onClick={() => setSuccessMsg('')} className="text-emerald-500 hover:text-emerald-700">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ESCALATION CARD: Displayed when role-appropriate escalation requires human action */}
      {isGovUser && isPendingGovState && (
        <div className="p-4 rounded-lg bg-amber-50/80 border-2 border-amber-300 space-y-3 shadow-sm">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-md bg-amber-600 text-white flex items-center justify-center shrink-0 mt-0.5">
                <AlertTriangle className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[10px] uppercase font-mono font-bold tracking-wider text-amber-800 block">
                  Government Authority Escalation
                </span>
                <h4 className="text-sm font-bold text-amber-950">
                  Algorithmic Authority Limit Reached
                </h4>
                <p className="text-xs text-amber-900 mt-1 leading-relaxed">
                  {relevantEscalation?.reason || 'Vendor proposed price or delivery parameters exceed standard algorithmic spending authority. Supervisory intervention is required to proceed.'}
                </p>
              </div>
            </div>

            <div className="shrink-0 text-right">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-200 text-amber-900 font-bold border border-amber-300">
                Rule: {relevantEscalation?.role === 'GOVERNMENT' ? 'GOV_MAX_PRICE_CEILING' : 'GOV_AUTHORITY_THRESHOLD'}
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-amber-200/80 flex items-center justify-between flex-wrap gap-3">
            <div className="text-xs text-amber-900">
              Current Public Proposal: <strong className="font-mono">${Number(currentPrice || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong> ({currentDays || '--'} days)
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleGovAction('APPROVE')}
                className="btn-primary bg-emerald-600 hover:bg-emerald-700 text-xs py-1.5 px-3 shadow-sm"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Approve &amp; Resume</span>
              </button>

              <button
                type="button"
                disabled={actionLoading}
                onClick={() => {
                  setCounterPrice(currentPrice ? String(currentPrice) : '');
                  setCounterDays(currentDays ? String(currentDays) : '');
                  setShowCounterModal(true);
                }}
                className="btn-secondary bg-white hover:bg-amber-100/50 text-amber-900 border-amber-300 text-xs py-1.5 px-3"
              >
                <Send className="w-3.5 h-3.5 text-amber-700" />
                <span>Manual Counteroffer</span>
              </button>

              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleGovAction('REJECT')}
                className="btn-danger text-xs py-1.5 px-3"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {isVendorUser && isPendingVendorState && (
        <div className="p-4 rounded-lg bg-purple-50/80 border-2 border-purple-300 space-y-3 shadow-sm">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-md bg-purple-600 text-white flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[10px] uppercase font-mono font-bold tracking-wider text-purple-800 block">
                  Vendor Commercial Escalation
                </span>
                <h4 className="text-sm font-bold text-purple-950">
                  Commercial Margin Boundary Reached
                </h4>
                <p className="text-xs text-purple-900 mt-1 leading-relaxed">
                  {relevantEscalation?.reason || 'Government proposal is below your configured minimum floor. Executive commercial approval is required to concede, counteroffer, or decline.'}
                </p>
              </div>
            </div>

            <div className="shrink-0 text-right">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-200 text-purple-900 font-bold border border-purple-300">
                Rule: {relevantEscalation?.role === 'VENDOR' ? 'VENDOR_MIN_PRICE_FLOOR' : 'VENDOR_COMMERCIAL_BOUNDARY'}
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-purple-200/80 flex items-center justify-between flex-wrap gap-3">
            <div className="text-xs text-purple-900">
              Government Offer: <strong className="font-mono">${Number(currentPrice || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong> ({currentDays || '--'} days)
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleVendorAction('APPROVE')}
                className="btn-primary bg-purple-600 hover:bg-purple-700 text-xs py-1.5 px-3 shadow-sm"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Approve &amp; Resume</span>
              </button>

              <button
                type="button"
                disabled={actionLoading}
                onClick={() => {
                  setCounterPrice(currentPrice ? String(currentPrice) : '');
                  setCounterDays(currentDays ? String(currentDays) : '');
                  setShowCounterModal(true);
                }}
                className="btn-secondary bg-white hover:bg-purple-100/50 text-purple-900 border-purple-300 text-xs py-1.5 px-3"
              >
                <Send className="w-3.5 h-3.5 text-purple-700" />
                <span>Manual Counteroffer</span>
              </button>

              <button
                type="button"
                disabled={actionLoading}
                onClick={() => handleVendorAction('REJECT')}
                className="btn-danger text-xs py-1.5 px-3"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Timeline Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold text-slate-900 uppercase font-mono tracking-wider flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-slate-500" />
            Bilateral Negotiation Transcript ({events.length} events)
          </h4>

          <div className="flex items-center gap-2">
            {/* Quick manual counter button for active sessions */}
            {['NEGOTIATING', 'RESUMED'].includes(currentStatus) && (
              <button
                type="button"
                onClick={() => {
                  setCounterPrice(currentPrice ? String(currentPrice) : '');
                  setCounterDays(currentDays ? String(currentDays) : '');
                  setShowCounterModal(true);
                }}
                className="text-[11px] font-medium text-slate-600 hover:text-slate-900 bg-white border border-[#d8d5ca] px-2.5 py-1 rounded-md flex items-center gap-1"
              >
                <Send className="w-3 h-3 text-slate-500" />
                <span>Submit Counteroffer</span>
              </button>
            )}

            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                className="text-slate-400 hover:text-slate-600 p-1 rounded"
                title="Refresh transcript"
              >
                <RotateCcw className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {events.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 border border-dashed border-[#d8d5ca] rounded-lg bg-[#fbfbfa]">
            <Bot className="w-6 h-6 text-slate-400 mx-auto mb-2" />
            No negotiation events recorded for this session yet.
          </div>
        ) : (
          <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
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

      {/* MANUAL COUNTEROFFER MODAL */}
      {showCounterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-white rounded-xl shadow-xl border border-[#d8d5ca] max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#e8e6df] pb-3">
              <div className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-md flex items-center justify-center text-white ${isGovUser ? 'bg-amber-600' : 'bg-purple-600'}`}>
                  <User className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Submit Manual Counteroffer
                  </h3>
                  <span className="text-[10px] font-mono text-slate-500">
                    {isGovUser ? 'Government Procurement Authority' : 'Vendor Commercial Authority'}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowCounterModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleManualCounterSubmit} className="space-y-3.5">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 uppercase font-mono mb-1">
                    Proposed Price ($)
                  </label>
                  <div className="relative">
                    <DollarSign className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={counterPrice}
                      onChange={(e) => setCounterPrice(e.target.value)}
                      placeholder="e.g. 15000.00"
                      className="w-full pl-7 pr-3 py-1.5 text-xs bg-[#fbfbfa] border border-[#d8d5ca] rounded-lg text-slate-900 focus:outline-none focus:border-blue-600 font-mono font-bold"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-700 uppercase font-mono mb-1">
                    Delivery SLA (Days)
                  </label>
                  <div className="relative">
                    <Calendar className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                    <input
                      type="number"
                      required
                      value={counterDays}
                      onChange={(e) => setCounterDays(e.target.value)}
                      placeholder="e.g. 10"
                      className="w-full pl-7 pr-3 py-1.5 text-xs bg-[#fbfbfa] border border-[#d8d5ca] rounded-lg text-slate-900 focus:outline-none focus:border-blue-600 font-mono font-bold"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 uppercase font-mono mb-1">
                  Optional Commercial Justification / Message
                </label>
                <textarea
                  rows="3"
                  value={counterMessage}
                  onChange={(e) => setCounterMessage(e.target.value)}
                  placeholder="Explain terms, volume discount conditions, or scheduling adjustments..."
                  className="w-full px-3 py-2 text-xs bg-[#fbfbfa] border border-[#d8d5ca] rounded-lg text-slate-900 focus:outline-none focus:border-blue-600 placeholder-slate-400"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-[#e8e6df]">
                <button
                  type="button"
                  onClick={() => setShowCounterModal(false)}
                  className="btn-secondary text-xs py-1.5 px-3"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="btn-primary text-xs py-1.5 px-4 bg-blue-600 hover:bg-blue-700"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{actionLoading ? 'Submitting...' : 'Submit Counteroffer'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
