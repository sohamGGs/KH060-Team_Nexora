import React, { useState, useEffect, useCallback } from 'react';
import Login from './components/Login';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import PurchaseRequestForm from './components/PurchaseRequestForm';
import VendorComparison from './components/VendorComparison';
import ApprovalQueue from './components/ApprovalQueue';
import PurchaseOrders from './components/PurchaseOrders';
import { authAPI, approvalsAPI } from './api';
import { CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';

export default function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedPrId, setSelectedPrId] = useState(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);
  const [toast, setToast] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4000);
  };

  const fetchPendingCount = useCallback(async () => {
    if (!token) return;
    try {
      const queue = await approvalsAPI.getQueue('Pending');
      setPendingApprovalsCount(queue.length);
    } catch (err) {
      // ignore
    }
  }, [token]);

  // Initial Auth Check
  useEffect(() => {
    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');

    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      } catch (e) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
    setAuthChecking(false);
  }, []);

  // Listen for unauthorized events
  useEffect(() => {
    const handleUnauth = () => {
      setUser(null);
      setToken(null);
      showToast('Session expired. Please sign in again.', 'error');
    };
    window.addEventListener('auth:unauthorized', handleUnauth);
    return () => window.removeEventListener('auth:unauthorized', handleUnauth);
  }, []);

  // Update pending queue count
  useEffect(() => {
    if (token) {
      fetchPendingCount();
    }
  }, [token, activeTab, fetchPendingCount]);

  const handleLoginSuccess = (userData, userToken) => {
    setUser(userData);
    setToken(userToken);
    setActiveTab('dashboard');
    showToast(`Welcome back, ${userData.full_name} (${userData.role})`, 'success');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
    setToken(null);
    setActiveTab('dashboard');
    showToast('Signed out of ProcureIQ ERP', 'success');
  };

  const handleSwitchPersona = async (email, password) => {
    try {
      const data = await authAPI.login(email, password);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      setUser(data.user);
      setToken(data.access_token);
      showToast(`Switched persona to ${data.user.full_name} (${data.user.role})`, 'success');
      fetchPendingCount();
    } catch (err) {
      showToast('Failed to switch persona', 'error');
    }
  };

  const handlePrCreated = (prId) => {
    setSelectedPrId(prId);
    setActiveTab('vendor_comparison');
    showToast(`PR-${prId.toString().padStart(4, '0')} Created & RFQ Bids Broadcast!`, 'success');
    fetchPendingCount();
  };

  const handlePoGenerated = (po) => {
    showToast(`PO ${po.po_number} successfully authorized and PDF compiled!`, 'success');
    fetchPendingCount();
  };

  if (authChecking) {
    return (
      <div className="min-h-screen w-full bg-[#f5f4f0] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-600/30 border-t-blue-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (!user || !token) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="flex min-h-screen bg-[#f5f4f0] text-slate-900 antialiased font-sans relative selection:bg-blue-600 selection:text-white">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 animate-fade-in">
          <div className={`px-3.5 py-2.5 rounded-lg shadow-lg border flex items-center gap-2 text-xs font-medium ${
            toast.type === 'error'
              ? 'bg-[#fbfbfa] border-rose-200 text-rose-800 shadow-rose-500/5'
              : 'bg-[#fbfbfa] border-[#e8e6df] text-slate-800 shadow-slate-500/10'
          }`}>
            {toast.type === 'error' ? (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            )}
            <span>{toast.message}</span>
          </div>
        </div>
      )}

      {/* Main ERP Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={user}
        onLogout={handleLogout}
        onSwitchPersona={handleSwitchPersona}
        pendingCount={pendingApprovalsCount}
      />

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 overflow-y-auto h-screen">
        {activeTab === 'dashboard' && (
          <Dashboard
            onNavigateToTab={setActiveTab}
            onSelectPrForComparison={(id) => {
              setSelectedPrId(id);
              setActiveTab('vendor_comparison');
            }}
            onTriggerNewPr={() => setActiveTab('new_pr')}
          />
        )}

        {(activeTab === 'new_pr' || activeTab === 'purchase_requests') && (
          <PurchaseRequestForm onPrCreated={handlePrCreated} />
        )}

        {activeTab === 'vendor_comparison' && (
          <VendorComparison
            selectedPrId={selectedPrId}
            onSelectPr={setSelectedPrId}
            onNavigateToTab={setActiveTab}
            onPoGenerated={handlePoGenerated}
          />
        )}

        {activeTab === 'approval_queue' && (
          <ApprovalQueue
            user={user}
            onNavigateToTab={setActiveTab}
            onSelectPrForComparison={(id) => {
              setSelectedPrId(id);
              setActiveTab('vendor_comparison');
            }}
            onPoGenerated={handlePoGenerated}
          />
        )}

        {activeTab === 'purchase_orders' && (
          <PurchaseOrders onNavigateToTab={setActiveTab} />
        )}
      </main>
    </div>
  );
}
