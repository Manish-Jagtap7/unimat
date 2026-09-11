"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { Check, X, Edit3, AlertTriangle, Layers, Zap, RefreshCw, Save, ShieldAlert, SplitSquareVertical } from "lucide-react";

export default function ReviewCenterPage() {
  const [queue, setQueue] = useState<any[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  
  // Edit State
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState("");

  // Reconstruct State
  const [isReconstructing, setIsReconstructing] = useState(false);
  const [removedItemIds, setRemovedItemIds] = useState<number[]>([]);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/review/clusters/pending');
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

  const currentCluster = queue[currentIndex];

  const handleResolve = async (action: "APPROVE" | "RECONSTRUCT") => {
    if (!currentCluster) return;
    setActionLoading(true);

    try {
      const payload: any = {
        action,
        officer_name: "Admin User",
      };

      if (editedName && editedName !== currentCluster.candidate_cnmc?.standardized_description) {
        payload.edited_name = editedName;
      }
      
      if (action === "RECONSTRUCT") {
        payload.removed_item_ids = removedItemIds;
      }

      await api.post(`/api/review/cluster/${currentCluster.root_item.id}/resolve`, payload);
      
      // Next item
      if (currentIndex < queue.length - 1) {
        setCurrentIndex(prev => prev + 1);
        resetState();
      } else {
        await fetchQueue();
        resetState();
      }
    } catch (error) {
      console.error(`Failed to ${action} cluster`, error);
      alert(`Failed to resolve the cluster. See console.`);
    } finally {
      setActionLoading(false);
    }
  };

  const resetState = () => {
    setIsEditingName(false);
    setEditedName("");
    setIsReconstructing(false);
    setRemovedItemIds([]);
  };

  const toggleRemoveItem = (id: number) => {
    setRemovedItemIds(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen p-8 bg-slate-50/50 flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mb-4"></div>
        <h2 className="text-xl font-bold text-slate-800">Loading Cluster Queue...</h2>
      </div>
    );
  }

  if (!currentCluster && queue.length === 0) {
    return (
      <div className="min-h-screen p-8 bg-slate-50/50 flex flex-col items-center justify-center">
        <div className="bg-emerald-100 p-6 rounded-full mb-6">
          <Check className="w-12 h-12 text-emerald-600" />
        </div>
        <h2 className="text-2xl font-bold text-slate-800">All Caught Up!</h2>
        <p className="text-slate-500 mt-2">No pending clusters require human review right now.</p>
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

  const defaultName = currentCluster.candidate_cnmc?.standardized_description || currentCluster.root_item.parsed_string;
  const displayName = editedName || defaultName;

  return (
    <div className="min-h-screen p-8 bg-slate-50/50">
      <div className="max-w-5xl mx-auto">
        
        {/* Header */}
        <div className="flex justify-between items-end mb-8">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Cluster Review Center</h1>
            <p className="text-slate-500 mt-1 font-medium">Review and standardize grouped materials into permanent clusters.</p>
          </motion.div>
          <div className="bg-amber-100 text-amber-800 px-4 py-2 rounded-xl font-bold text-sm flex items-center border border-amber-200">
            <AlertTriangle className="w-4 h-4 mr-2" />
            {queue.length - currentIndex} Clusters in Queue
          </div>
        </div>

        {/* Main Panel */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          
          {/* Top: Generated CNMC Name */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-indigo-100 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500"></div>
            <div className="flex justify-between items-start mb-4">
              <p className="text-xs font-bold text-indigo-500 uppercase tracking-wider flex items-center">
                <Zap className="w-4 h-4 mr-1.5" />
                AI Generated Common Name
              </p>
              {!isEditingName && (
                <button 
                  onClick={() => { setIsEditingName(true); setEditedName(defaultName); }}
                  className="text-xs font-bold text-slate-500 hover:text-indigo-600 flex items-center bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200 transition-colors"
                >
                  <Edit3 className="w-3.5 h-3.5 mr-1.5" /> Edit Name
                </button>
              )}
            </div>
            
            {isEditingName ? (
              <div className="flex gap-3">
                <input 
                  type="text" 
                  value={editedName} 
                  onChange={(e) => setEditedName(e.target.value)}
                  className="flex-1 bg-slate-50 border border-indigo-300 rounded-xl px-4 py-3 text-lg font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <button 
                  onClick={() => setIsEditingName(false)}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl font-bold flex items-center transition-colors"
                >
                  <Save className="w-4 h-4 mr-2" /> Save
                </button>
              </div>
            ) : (
              <h2 className="text-2xl font-black text-slate-800 bg-slate-50 border border-slate-100 p-4 rounded-xl leading-relaxed">
                {displayName}
              </h2>
            )}
          </div>

          {/* Items in Cluster */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 relative">
            <div className="flex justify-between items-center mb-6">
              <p className="text-sm font-bold text-slate-800 flex items-center">
                <Layers className="w-5 h-5 mr-2 text-indigo-500" />
                Grouped Materials ({currentCluster.children.length + 1})
              </p>
            </div>

            <div className="space-y-3">
              {/* Root Item */}
              <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-4 flex gap-4 opacity-100">
                 <div className="flex-1">
                   <div className="flex items-center gap-2 mb-1">
                     <span className="text-xs font-bold text-white bg-indigo-500 px-2 py-0.5 rounded">ROOT</span>
                     <span className="text-xs font-bold text-slate-500">{currentCluster.root_item.cpse_source}</span>
                     <span className="text-xs font-mono text-slate-400">{currentCluster.root_item.legacy_item_code}</span>
                   </div>
                   <p className="text-sm font-medium text-slate-800">{currentCluster.root_item.raw_description}</p>
                 </div>
              </div>

              {/* Child Items */}
              {currentCluster.children.map((child: any) => {
                const isRemoved = removedItemIds.includes(child.id);
                return (
                  <div key={child.id} className={`border rounded-xl p-4 flex gap-4 transition-opacity ${isRemoved ? 'bg-red-50/30 border-red-100 opacity-50' : 'bg-slate-50 border-slate-200'}`}>
                    {isReconstructing && (
                      <div className="flex items-center justify-center pt-2">
                        <input 
                          type="checkbox" 
                          checked={!isRemoved}
                          onChange={() => toggleRemoveItem(child.id)}
                          className="w-5 h-5 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer"
                        />
                      </div>
                    )}
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          {child.review_status === "PENDING" && !isRemoved && (
                            <span className="text-xs font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded flex items-center">
                              <AlertTriangle className="w-3 h-3 mr-1" /> PENDING
                            </span>
                          )}
                          <span className="text-xs font-bold text-slate-500">{child.cpse_source}</span>
                          <span className="text-xs font-mono text-slate-400">{child.legacy_item_code}</span>
                        </div>
                        {!isRemoved && child.similarity_score && (
                          <span className={`text-xs font-black ${child.similarity_score >= 0.95 ? 'text-emerald-500' : 'text-amber-500'}`}>
                            {(child.similarity_score * 100).toFixed(1)}% Match
                          </span>
                        )}
                      </div>
                      <p className={`text-sm font-medium ${isRemoved ? 'text-slate-400 line-through' : 'text-slate-800'}`}>
                        {child.raw_description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Action Bar */}
          <div className="flex gap-4 pt-4">
            <button
              onClick={() => handleResolve("APPROVE")}
              disabled={actionLoading}
              className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white py-4 rounded-xl font-bold text-lg shadow-sm shadow-emerald-200 transition-colors flex justify-center items-center"
            >
              <Check className="w-6 h-6 mr-2" />
              {actionLoading ? "Processing..." : "Approve Full Cluster"}
            </button>
            
            <button
              onClick={() => {
                if (isReconstructing) {
                  handleResolve("RECONSTRUCT");
                } else {
                  setIsReconstructing(true);
                }
              }}
              disabled={actionLoading}
              className={`flex-1 py-4 rounded-xl font-bold text-lg shadow-sm transition-colors flex justify-center items-center border-2 ${
                isReconstructing 
                ? 'bg-amber-600 hover:bg-amber-700 border-amber-600 text-white shadow-amber-200' 
                : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-700'
              }`}
            >
              <SplitSquareVertical className="w-6 h-6 mr-2" />
              {isReconstructing ? `Confirm Reconstruct (${removedItemIds.length} removed)` : "Reconstruct Cluster"}
            </button>
          </div>

        </motion.div>
      </div>
    </div>
  );
}
