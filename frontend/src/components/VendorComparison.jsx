import React, { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Play, RotateCcw } from "lucide-react";
import { vendorAPI } from "../services/api";

export default function VendorComparison({
  prId,
  recommendations = [],
  onNegotiationComplete,
}) {
  const [loading, setLoading] = useState(false);
  const [resumeLoading, setResumeLoading] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const startNegotiation = async () => {
    try {
      setLoading(true);
      setError("");

      const response = await vendorAPI.negotiate(prId);
      setResult(response.data);

      if (onNegotiationComplete) {
        onNegotiationComplete(response.data);
      }
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Negotiation could not be started."
      );
    } finally {
      setLoading(false);
    }
  };

  const resumeNegotiation = async (sessionId) => {
    try {
      setResumeLoading(sessionId);
      setError("");

      const response = await vendorAPI.resumeNegotiation(sessionId);
      setResult(response.data);

      if (onNegotiationComplete) {
        onNegotiationComplete(response.data);
      }
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Negotiation could not be resumed."
      );
    } finally {
      setResumeLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Vendor Comparison</h2>
          <p className="text-sm text-muted-foreground">
            Compare vendors and let the procurement agent negotiate within policy.
          </p>
        </div>

        <button
          onClick={startNegotiation}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {loading ? "Negotiating..." : "Start Negotiation"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="grid gap-4">
        {recommendations.map((vendor) => (
          <div
            key={vendor.vendor_id}
            className="rounded-xl border bg-card p-5 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold">{vendor.vendor_name}</h3>
                <p className="text-sm text-muted-foreground">
                  ₹{Number(vendor.quoted_price).toLocaleString()} ·{" "}
                  {vendor.delivery_days} days
                </p>
              </div>

              <div className="text-right">
                <div className="font-semibold">{vendor.bid_score}</div>
                <div className="text-xs text-muted-foreground">Bid Score</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {result?.results?.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Negotiation Results</h3>

          {result.results.map((item) => (
            <div
              key={item.session_id || item.vendor_id}
              className="rounded-xl border bg-card p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h4 className="font-semibold">{item.vendor_name}</h4>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Final: ₹{Number(item.final_price).toLocaleString()} ·{" "}
                    {item.final_days} days
                  </p>
                </div>

                {item.action === "ACCEPT" && (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                )}

                {item.action === "ESCALATE" && (
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                )}
              </div>

              <div className="mt-4 text-sm">
                <span className="font-medium">Status:</span>{" "}
                {item.status}
              </div>

              {item.savings > 0 && (
                <div className="mt-2 text-sm text-green-600">
                  Savings: ₹{Number(item.savings).toLocaleString()} (
                  {item.savings_percentage.toFixed(1)}%)
                </div>
              )}

              {item.action === "ESCALATE" && item.session_id && (
                <button
                  onClick={() => resumeNegotiation(item.session_id)}
                  disabled={resumeLoading === item.session_id}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium disabled:opacity-50"
                >
                  {resumeLoading === item.session_id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RotateCcw className="h-4 w-4" />
                  )}
                  Resume After Approval
                </button>
              )}

              <div className="mt-5 space-y-3">
                {item.transcript?.map((turn, index) => (
                  <div
                    key={`${turn.round}-${index}`}
                    className="rounded-lg bg-muted/40 p-3"
                  >
                    <div className="flex justify-between text-xs font-medium">
                      <span>{turn.speaker}</span>
                      <span>Round {turn.round}</span>
                    </div>
                    <p className="mt-1 text-sm">{turn.message}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      ₹{Number(turn.offered_price).toLocaleString()} ·{" "}
                      {turn.offered_days} days
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}