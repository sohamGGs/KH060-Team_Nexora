import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  Eye,
  CheckCircle,
  Truck,
  Search,
  ShieldCheck,
  X,
  ArrowRight,
  Database,
  Cloud,
  Check
} from 'lucide-react';
import { approvalsAPI } from '../api';

export default function PurchaseOrders({ onNavigateToTab }) {
  const [pos, setPos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [previewPo, setPreviewPo] = useState(null);
  const [downloadingPo, setDownloadingPo] = useState(null);
  const [updatingPo, setUpdatingPo] = useState(null);
  const [netsuitePo, setNetsuitePo] = useState(null);
  const [netsuiteLoading, setNetsuiteLoading] = useState(false);
  const [netsuiteData, setNetsuiteData] = useState(null);

  const fetchPOs = async () => {
    try {
      setLoading(true);
      const data = await approvalsAPI.getAllPOs();
      setPos(data);
    } catch (err) {
      console.error('Failed to load POs:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenNetSuiteSync = async (poNumber) => {
    setNetsuitePo(poNumber);
    setNetsuiteLoading(true);
    try {
      const data = await approvalsAPI.getNetSuiteSync(poNumber);
      setNetsuiteData(data);
    } catch (err) {
      console.error('Failed to fetch NetSuite sync payload:', err);
    } finally {
      setNetsuiteLoading(false);
    }
  };

  useEffect(() => {
    fetchPOs();
  }, []);

  const handleDownloadPDF = async (poNumber) => {
    setDownloadingPo(poNumber);
    try {
      await approvalsAPI.downloadPDF(poNumber);
    } catch (err) {
      console.error('Failed to download PDF:', err);
      // Fallback direct link
      window.open(approvalsAPI.getDownloadUrl(poNumber), '_blank');
    } finally {
      setDownloadingPo(null);
    }
  };

  const handleStatusTransition = async (poNumber, newStatus) => {
    setUpdatingPo(poNumber);
    try {
      await approvalsAPI.updatePOStatus(poNumber, newStatus);
      fetchPOs();
    } catch (err) {
      console.error('Failed to update status:', err);
    } finally {
      setUpdatingPo(null);
    }
  };

  const filteredPOs = pos.filter((po) => {
    const matchesSearch =
      po.po_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
      po.vendor?.name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'All' || po.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'Delivered':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200 font-mono text-[9px] uppercase font-semibold';
      case 'Acknowledged':
        return 'bg-blue-50 text-blue-700 border-blue-200 font-mono text-[9px] uppercase font-semibold';
      case 'Sent':
        return 'bg-amber-50 text-amber-700 border-amber-200 font-mono text-[9px] uppercase font-semibold';
      default:
        return 'bg-slate-100 border-slate-200 text-slate-600 font-mono text-[9px] uppercase font-medium';
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <span className="text-[10px] uppercase font-mono tracking-widest text-slate-500 font-bold block mb-1">
            NetSuite PO Register &amp; Lifecycle
          </span>
          <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight">
            Purchase Orders &amp; 3-Way Match
          </h1>
          <p className="text-slate-500 text-xs mt-0.5">
            Track authorized PO lifecycle (Sent &rarr; In Transit &rarr; Delivered) and download ReportLab ERP documentation.
          </p>
        </div>

        <button
          onClick={() => onNavigateToTab('new_pr')}
          className="btn-primary self-start md:self-auto"
        >
          <span>Create New PR</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="enterprise-card p-4 space-y-2">
          <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest font-mono">Total Issued POs</span>
          <div className="text-2xl lg:text-3xl font-mono tabular-nums font-extrabold text-slate-900">{pos.length}</div>
        </div>
        <div className="enterprise-card p-4 space-y-2">
          <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest font-mono">Total Authorized Spend</span>
          <div className="text-2xl lg:text-3xl font-mono tabular-nums font-extrabold text-emerald-700">
            ${pos.reduce((acc, p) => acc + p.total_amount, 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </div>
        </div>
        <div className="enterprise-card p-4 space-y-2">
          <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest font-mono">In Transit</span>
          <div className="text-2xl lg:text-3xl font-mono tabular-nums font-extrabold text-blue-700">
            {pos.filter((p) => p.status === 'Acknowledged').length}
          </div>
        </div>
        <div className="enterprise-card p-4 space-y-2">
          <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest font-mono">3-Way Match Closed</span>
          <div className="text-2xl lg:text-3xl font-mono tabular-nums font-extrabold text-emerald-700">
            {pos.filter((p) => p.status === 'Delivered').length}
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="enterprise-card p-3.5 flex flex-col sm:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search PO# or supplier..."
            className="w-full bg-white border border-[#dcd9ce] rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 font-mono shadow-sm"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1 p-1 rounded-lg bg-[#f3f2ec] border border-[#e8e6df] text-xs w-full sm:w-auto overflow-x-auto font-mono">
          {['All', 'Sent', 'Acknowledged', 'Delivered'].map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors cursor-pointer ${
                statusFilter === status
                  ? 'bg-[#fbfbfa] text-slate-900 border border-[#d8d5ca] shadow-sm font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* PO Register Table */}
      <div className="enterprise-card p-5 space-y-3">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#e8e6df] text-slate-500 uppercase text-[10px] tracking-wider bg-[#f3f2ec]">
                <th className="py-2.5 px-3 font-mono">PO Number</th>
                <th className="py-2.5 px-3">Supplier</th>
                <th className="py-2.5 px-3 font-mono text-right">Total Amount</th>
                <th className="py-2.5 px-3">Issue Date</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-center">Lifecycle Stage</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eeebe3]">
              {filteredPOs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400 text-xs">
                    No purchase orders found matching your criteria.
                  </td>
                </tr>
              ) : (
                filteredPOs.map((po) => (
                  <tr key={po.id} className="hover:bg-[#f5f4f0]/80 transition-colors">
                    {/* PO Number */}
                    <td className="py-3 px-3 font-mono font-semibold text-slate-900">
                      {po.po_number}
                    </td>

                    {/* Vendor */}
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900 text-xs">{po.vendor?.name || 'Primary Vendor'}</div>
                      <div className="text-[10px] text-slate-500">{po.vendor?.pricing_tier}</div>
                    </td>

                    {/* Total Amount */}
                    <td className="py-3 px-3 font-mono font-bold text-slate-900 text-xs text-right">
                      ${po.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>

                    {/* Issue Date */}
                    <td className="py-3 px-3 text-slate-700 text-xs">
                      {new Date(po.created_at).toLocaleDateString()}
                    </td>

                    {/* Lifecycle Status */}
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${getStatusBadge(po.status)}`}>
                        {po.status === 'Sent' && 'Sent to Vendor'}
                        {po.status === 'Acknowledged' && 'In Transit'}
                        {po.status === 'Delivered' && '3-Way Match Verified'}
                      </span>
                    </td>

                    {/* Status Transition Controls */}
                    <td className="py-3 px-3 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        {po.status === 'Sent' && (
                          <button
                            type="button"
                            disabled={updatingPo === po.po_number}
                            onClick={() => handleStatusTransition(po.po_number, 'Acknowledged')}
                            className="btn-secondary text-[10px] py-1 px-2 text-blue-700 font-medium"
                          >
                            <Truck className="w-3 h-3" />
                            <span>Mark In-Transit</span>
                          </button>
                        )}

                        {po.status === 'Acknowledged' && (
                          <button
                            type="button"
                            disabled={updatingPo === po.po_number}
                            onClick={() => handleStatusTransition(po.po_number, 'Delivered')}
                            className="btn-success text-[10px] py-1 px-2"
                          >
                            <CheckCircle className="w-3 h-3" />
                            <span>Verify 3-Way Match</span>
                          </button>
                        )}

                        {po.status === 'Delivered' && (
                          <span className="text-[10px] text-emerald-700 font-semibold flex items-center gap-1">
                            <ShieldCheck className="w-3 h-3" /> Closed
                          </span>
                        )}
                      </div>
                    </td>

                    {/* PDF & NetSuite Actions */}
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => handleOpenNetSuiteSync(po.po_number)}
                          className="btn-secondary text-[11px] p-1.5 text-indigo-700"
                          title="NetSuite SuiteTalk ERP Sync Payload"
                        >
                          <Database className="w-3.5 h-3.5" />
                        </button>

                        <button
                          type="button"
                          onClick={() => setPreviewPo(po)}
                          className="btn-secondary text-[11px] p-1.5 text-slate-700"
                          title="Preview Document"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>

                        <button
                          type="button"
                          disabled={downloadingPo === po.po_number}
                          onClick={() => handleDownloadPDF(po.po_number)}
                          className="btn-secondary text-[11px] py-1 px-2.5 text-blue-700 font-medium"
                        >
                          <Download className="w-3 h-3" />
                          <span>PDF</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* NetSuite SuiteTalk ERP Sync Inspector Modal */}
      {netsuitePo && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="enterprise-card p-5 md:p-6 max-w-2xl w-full space-y-4 shadow-2xl animate-fade-in max-h-[90vh] overflow-y-auto bg-[#fbfbfa] border border-[#e8e6df]">
            <div className="flex items-center justify-between border-b border-[#e8e6df] pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-indigo-600" />
                    Oracle NetSuite SuiteTalk REST API Sync Hub
                  </h3>
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5 font-mono">PO: {netsuitePo} // Internal ID: {netsuiteData?.netsuite_internal_id || 'NS-REC-10482'}</p>
              </div>
              <button
                onClick={() => { setNetsuitePo(null); setNetsuiteData(null); }}
                className="p-1.5 rounded-lg bg-[#f3f2ec] text-slate-500 hover:text-slate-900 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {netsuiteLoading ? (
              <div className="py-10 text-center space-y-2">
                <div className="w-6 h-6 border-2 border-indigo-600/20 border-t-indigo-600 rounded-full animate-spin mx-auto" />
                <p className="text-xs text-slate-500">Connecting to Oracle NetSuite SuiteTalk REST API...</p>
              </div>
            ) : netsuiteData ? (
              <div className="space-y-3.5">
                {/* Status Pills */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="p-2.5 rounded-lg bg-[#f5f4f0] border border-[#e8e6df]">
                    <div className="text-[9px] text-slate-500 uppercase font-medium">Sync Status</div>
                    <div className="text-xs font-bold text-emerald-700 flex items-center gap-1 mt-0.5">
                      <Check className="w-3 h-3" /> Live Synced
                    </div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#f5f4f0] border border-[#e8e6df]">
                    <div className="text-[9px] text-slate-500 uppercase font-medium">GL Account</div>
                    <div className="text-xs font-bold text-blue-700 font-mono mt-0.5">6010 CapEx</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#f5f4f0] border border-[#e8e6df]">
                    <div className="text-[9px] text-slate-500 uppercase font-medium">Subsidiary</div>
                    <div className="text-xs font-bold text-slate-800 mt-0.5">TechCorp Sub-01</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#f5f4f0] border border-[#e8e6df]">
                    <div className="text-[9px] text-slate-500 uppercase font-medium">3-Way Match</div>
                    <div className="text-xs font-bold text-slate-800 mt-0.5">Active</div>
                  </div>
                </div>

                {/* SuiteTalk JSON Viewer */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span className="font-semibold flex items-center gap-1 text-slate-700 text-[11px]">
                      <Cloud className="w-3 h-3 text-indigo-600" /> SuiteTalk REST API JSON Payload
                    </span>
                    <span className="text-[10px] font-mono text-emerald-700 font-semibold">HTTP 200 OK</span>
                  </div>
                  <pre className="p-3.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-100 overflow-x-auto max-h-56 leading-relaxed">
                    {JSON.stringify(netsuiteData.suitetalk_rest_payload, null, 2)}
                  </pre>
                </div>

                <div className="p-2.5 rounded-lg bg-[#f5f4f0] border border-[#e8e6df] text-[11px] text-slate-700 flex items-start gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-indigo-600 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-slate-900">NetSuite 3-Way Match Validation:</strong> Automatically binds NetSuite <code className="bg-[#e8e6df] px-1 py-0.5 rounded text-slate-800">purchaseOrder</code> to <code className="bg-[#e8e6df] px-1 py-0.5 rounded text-slate-800">itemReceipt</code> on delivery dock check-in and verifies against <code className="bg-[#e8e6df] px-1 py-0.5 rounded text-slate-800">vendorBill</code> before releasing payment.
                  </span>
                </div>
              </div>
            ) : null}

            <div className="flex justify-end gap-2.5 pt-2 border-t border-[#e8e6df]">
              <button
                type="button"
                onClick={() => { setNetsuitePo(null); setNetsuiteData(null); }}
                className="btn-secondary text-xs"
              >
                Close NetSuite Hub
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PO Document Preview Modal */}
      {previewPo && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="enterprise-card p-5 md:p-6 max-w-2xl w-full space-y-4 shadow-2xl animate-fade-in max-h-[90vh] overflow-y-auto bg-[#fbfbfa] border border-[#e8e6df]">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#e8e6df] pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-blue-600" />
                  NetSuite ERP Purchase Order Document
                </h3>
                <span className="font-mono text-xs text-blue-600 font-semibold">{previewPo.po_number}</span>
              </div>
              <button
                onClick={() => setPreviewPo(null)}
                className="p-1.5 rounded-lg bg-[#f3f2ec] text-slate-500 hover:text-slate-900 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Document Body */}
            <div className="p-4 rounded-lg bg-[#f5f4f0] border border-[#e8e6df] space-y-4 text-xs text-slate-700">
              {/* Document Header */}
              <div className="flex items-start justify-between border-b border-[#e8e6df] pb-3">
                <div>
                  <div className="text-base font-bold text-slate-900">
                    ProcureIQ <span className="text-blue-600">ERP</span>
                  </div>
                  <p className="text-[10px] text-slate-500">NetSuite Autonomous Procurement Engine</p>
                </div>
                <div className="text-right">
                  <div className="font-mono font-bold text-slate-900 text-sm">{previewPo.po_number}</div>
                  <div className="text-slate-500 text-[10px]">Issue Date: {new Date(previewPo.created_at).toLocaleDateString()}</div>
                  <div className="mt-0.5">
                    <span className={`px-1.5 py-0.2 rounded text-[9px] font-medium border ${getStatusBadge(previewPo.status)}`}>
                      {previewPo.status}
                    </span>
                  </div>
                </div>
              </div>

              {/* Vendor & Ship-To Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-2.5 rounded bg-[#fbfbfa] border border-[#e8e6df] space-y-0.5 shadow-sm">
                  <div className="font-semibold text-slate-500 uppercase text-[9px]">Vendor / Supplier</div>
                  <div className="font-bold text-slate-900 text-xs">{previewPo.vendor?.name}</div>
                  <div className="text-[10px]">Tier: {previewPo.vendor?.pricing_tier}</div>
                  <div className="text-[10px]">Email: {previewPo.vendor?.contact_email}</div>
                  <div className="text-[10px]">Phone: {previewPo.vendor?.phone}</div>
                </div>

                <div className="p-2.5 rounded bg-[#fbfbfa] border border-[#e8e6df] space-y-0.5 shadow-sm">
                  <div className="font-semibold text-slate-500 uppercase text-[9px]">Ship-To / Department</div>
                  <div className="font-bold text-slate-900 text-xs">ProcureIQ Global Facilities</div>
                  <div className="text-[10px]">Delivery SLA: {previewPo.vendor?.avg_delivery_days} Business Days</div>
                  <div className="text-[10px]">3-Way Match Verification Active</div>
                </div>
              </div>

              {/* Amount Box */}
              <div className="p-3 rounded-lg bg-[#fbfbfa] border border-[#e8e6df] flex items-center justify-between shadow-sm">
                <div>
                  <div className="text-[10px] text-slate-500">Total Purchase Order Value</div>
                  <div className="text-[11px] text-slate-700 font-medium">Commercial terms Net-30</div>
                </div>
                <div className="text-base font-mono font-bold text-emerald-700">
                  ${previewPo.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
              </div>

              {/* Barcode & Compliance */}
              <div className="pt-2 flex items-center justify-between text-[10px] text-slate-500 border-t border-[#e8e6df]">
                <span>Certified under NetSuite Automated Procurement Protocol</span>
                <span className="font-mono">{previewPo.po_number} // VERIFIED</span>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setPreviewPo(null)}
                className="btn-secondary text-xs"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => handleDownloadPDF(previewPo.po_number)}
                className="btn-primary text-xs"
              >
                <Download className="w-3.5 h-3.5" /> Download ReportLab PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
