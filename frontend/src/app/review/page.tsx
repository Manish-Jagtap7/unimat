"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Check, X, Edit3, AlertTriangle, Search, Zap, RefreshCw } from "lucide-react";

export default function ReviewCenterPage() {
  const [queue, setQueue] = useState<any[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [editedDesc, setEditedDesc] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/review/pending');
      setQueue(response.data);
      setCurrentIndex(0);
    } catch (error) {
      console.error("Failed to fetch pending reviews", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const currentItem = queue[currentIndex];

  const handleResolve = async (action: "APPROVE" | "REJECT" | "OVERRIDE") => {
    if (!currentItem) return;
    setActionLoading(true);

    try {
      const payload: any = {
        action,
        officer_name: "Admin User", // in a real app, from auth session
      };

      if (action === "OVERRIDE") {
        payload.override_description = editedDesc;
      }

      await api.post(`/api/review/${currentItem.material_item.id}/resolve`, payload);
      
      // Move to next item
      if (currentIndex < queue.length - 1) {
        setCurrentIndex(prev => prev + 1);
        setEditedDesc("");
        setIsEditing(false);
      } else {
        // We reached the end of the current batch, re-fetch
        await fetchQueue();
      }
    } catch (error) {
      console.error(`Failed to ${action} item`, error);
      alert(`Failed to ${action} the item. See console.`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen p-8 bg-slate-50/50 flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mb-4"></div>
        <h2 className="text-xl font-bold text-slate-800">Loading HITL Queue...</h2>
      </div>
    );
  }

  if (!currentItem && queue.length === 0) {
    return (
      <div className="min-h-screen p-8 bg-slate-50/50 flex flex-col items-center justify-center">
        <div className="bg-emerald-100 p-6 rounded-full mb-6">
          <Check className="w-12 h-12 text-emerald-600" />
        </div>
        <h2 className="text-2xl font-bold text-slate-800">All Caught Up!</h2>
        <p className="text-slate-500 mt-2">No pending items require human review right now.</p>
        <button 
          onClick={fetchQueue}
          className="mt-8 flex items-center px-6 py-2.5 bg-white border border-slate-200 shadow-sm rounded-xl text-slate-700 font-semibold hover:bg-slate-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh Queue
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 bg-slate-50/50">
      <div className="max-w-5xl mx-auto">
        
        {/* Header */}
        <div className="flex justify-between items-end mb-8">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Review Center</h1>
            <p className="text-slate-500 mt-1 font-medium">Human-in-the-Loop (HITL) resolution for near-duplicate matches.</p>
          </motion.div>
          <div className="bg-amber-100 text-amber-800 px-4 py-2 rounded-xl font-bold text-sm flex items-center border border-amber-200">
            <AlertTriangle className="w-4 h-4 mr-2" />
            {queue.length - currentIndex} Items in Queue
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Main Review Panel */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="lg:col-span-2 space-y-6"
          >
            {/* Raw Input Card */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-slate-300"></div>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4 flex justify-between">
                <span>Raw Source Data</span>
                <span className="text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md">{currentItem.material_item.cpse_source}</span>
              </p>
              
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500 font-semibold">Material Code</label>
                  <p className="font-mono text-slate-800 text-lg bg-slate-50 p-2 rounded-lg mt-1 border border-slate-100">
                    {currentItem.material_item.legacy_item_code || "N/A"}
                  </p>
                </div>
                <div>
                  <label className="text-xs text-slate-500 font-semibold">Legacy Description</label>
                  <p className="text-slate-800 font-medium text-lg bg-slate-50 p-3 rounded-lg mt-1 border border-slate-100 leading-relaxed">
                    {currentItem.material_item.raw_description}
                  </p>
                </div>
              </div>
            </div>

            {/* AI Suggestion Card */}
            <div className="bg-white rounded-2xl p-6 shadow-md shadow-indigo-100/50 border border-indigo-100 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500"></div>
              <div className="flex justify-between items-start mb-6">
                <p className="text-xs font-bold text-indigo-500 uppercase tracking-wider flex items-center">
                  <Zap className="w-4 h-4 mr-1.5" />
                  AI Suggested Match
                </p>
                <div className="flex items-center bg-amber-50 px-3 py-1 rounded-full border border-amber-100">
                  <span className="text-amber-600 text-xs font-bold mr-2">Confidence:</span>
                  <span className="text-amber-700 font-black">{Math.round(currentItem.similarity_score * 100)}%</span>
                </div>
              </div>

              {isEditing ? (
                <div className="space-y-4">
                  <textarea
                    value={editedDesc !== "" ? editedDesc : (currentItem.candidate_cnmc?.standardized_description || "")}
                    onChange={(e) => setEditedDesc(e.target.value)}
                    className="w-full h-32 p-4 text-slate-800 font-medium rounded-xl border-2 border-indigo-500 outline-none focus:ring-4 focus:ring-indigo-500/20 resize-none"
                    placeholder="Enter corrected description..."
                  />
                  <div className="flex justify-end gap-3">
                    <button 
                      onClick={() => setIsEditing(false)}
                      disabled={actionLoading}
                      className="px-4 py-2 text-slate-500 font-semibold hover:bg-slate-100 rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                    <button 
                      onClick={() => handleResolve("OVERRIDE")}
                      disabled={actionLoading}
                      className="px-6 py-2 bg-indigo-600 text-white font-bold rounded-lg hover:bg-indigo-700 transition-colors shadow-sm"
                    >
                      {actionLoading ? "Saving..." : "Save & Override"}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="bg-indigo-50/50 p-4 rounded-xl border border-indigo-100 mb-6 flex flex-col">
                    <p className="text-xs font-mono font-bold text-indigo-500 mb-2">
                      {currentItem.candidate_cnmc?.cnmc_code || "NEW CNMC"}
                    </p>
                    <p className="text-xl text-slate-800 font-bold leading-relaxed">
                      {currentItem.candidate_cnmc?.standardized_description || "No match found"}
                    </p>
                  </div>
                  
                  {/* Action Buttons */}
                  <div className="grid grid-cols-3 gap-4 mt-8">
                    <button 
                      onClick={() => handleResolve("REJECT")}
                      disabled={actionLoading}
                      className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-rose-100 text-rose-600 hover:bg-rose-50 hover:border-rose-200 transition-all font-semibold disabled:opacity-50"
                    >
                      <X className="w-6 h-6 mb-2" />
                      Reject Match (Anomaly)
                    </button>
                    <button 
                      onClick={() => setIsEditing(true)}
                      disabled={actionLoading}
                      className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-all font-semibold disabled:opacity-50"
                    >
                      <Edit3 className="w-6 h-6 mb-2" />
                      Edit Details
                    </button>
                    <button 
                      onClick={() => handleResolve("APPROVE")}
                      disabled={actionLoading}
                      className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-transparent bg-emerald-500 text-white hover:bg-emerald-600 transition-all shadow-md shadow-emerald-200 font-bold disabled:opacity-50"
                    >
                      <Check className="w-6 h-6 mb-2" />
                      Approve Match
                    </button>
                  </div>
                </>
              )}
            </div>
          </motion.div>

          {/* Sidebar Info Panel */}
          <motion.div 
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
            className="space-y-6"
          >
            {/* Flags/Issues */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-rose-100">
              <h3 className="text-sm font-bold text-rose-600 flex items-center mb-4">
                <AlertTriangle className="w-4 h-4 mr-2" />
                AI Flags & Reasons
              </h3>
              <ul className="space-y-3">
                <li className="flex items-start text-sm font-medium text-slate-700 bg-rose-50 p-3 rounded-lg border border-rose-100/50">
                  <div className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 mr-2 flex-shrink-0" />
                  Similarity score ({Math.round(currentItem.similarity_score * 100)}%) is below automatic deduplication threshold (95%).
                </li>
                <li className="flex items-start text-sm font-medium text-slate-700 bg-rose-50 p-3 rounded-lg border border-rose-100/50">
                  <div className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 mr-2 flex-shrink-0" />
                  Potential variance in noun, modifier, or attributes.
                </li>
              </ul>
            </div>

            {/* Catalog Search Help */}
            <div className="bg-slate-900 rounded-2xl p-6 shadow-lg text-white">
              <h3 className="text-sm font-bold text-indigo-400 mb-4">UNIMAT Dictionary Search</h3>
              <p className="text-sm text-slate-300 mb-4">Quickly search existing standard descriptions to find a match.</p>
              
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input 
                  type="text"
                  placeholder="e.g. Centrifugal Pump..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl py-2.5 pl-10 pr-4 text-sm outline-none focus:border-indigo-500 transition-colors"
                />
              </div>
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
}
