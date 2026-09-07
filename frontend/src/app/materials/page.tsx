"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import {
  Search,
  CheckCircle2,
  Clock,
  AlertCircle,
  ArrowDownToLine,
  MoreVertical,
  Sparkles,
  Layers,
  ChevronDown,
  ChevronRight,
  Link as LinkIcon,
  FolderOpen,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────
interface MaterialItem {
  id: number;
  cpse_source: string;
  legacy_item_code: string;
  raw_description: string;
  standardized_description: string | null;
  cnmc_code: string | null;
  classification: "UNIQUE" | "NEAR_DUPLICATE" | "DUPLICATE";
  review_status: "PENDING" | "APPROVED" | "REJECTED";
  similarity_score: number | null;
  matched_cnmc_id: number | null;
  matched_material_id: number | null;
  cluster_number: number | null;
  created_at: string;
}

interface ClusterGroup {
  parent: MaterialItem;
  children: MaterialItem[];
  isExpanded: boolean;
}

// ─── Badge for child items only ─────────────────────────────────────────────
const ChildBadge = ({ classification, score }: { classification: string; score: number }) => {
  const pct = Math.round(score * 100);

  if (classification === "DUPLICATE") {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 mr-1" />
          Duplicate
        </span>
        <span className="text-xs font-bold text-emerald-600">{pct}%</span>
      </div>
    );
  } else {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
          <Clock className="w-3 h-3 mr-1" />
          Near Duplicate
        </span>
        <span className="text-xs font-bold text-amber-600">{pct}%</span>
      </div>
    );
  }
};

// ─── Cluster label for parent rows ──────────────────────────────────────────
const ClusterLabel = ({ number, childCount }: { number: number; childCount: number }) => (
  <div className="flex flex-col items-start gap-1">
    <span className="inline-flex items-center px-3 py-1 rounded-lg text-xs font-extrabold bg-indigo-600 text-white shadow-sm">
      <FolderOpen className="w-3.5 h-3.5 mr-1.5" />
      Cluster {number}
    </span>
    <span className="text-[11px] text-slate-500 font-medium ml-0.5">
      {childCount} duplicate{childCount !== 1 ? "s" : ""} found
    </span>
  </div>
);

// ─── Unique label for singletons ────────────────────────────────────────────
const UniqueLabel = () => (
  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
    <AlertCircle className="w-3 h-3 mr-1" />
    Unique
  </span>
);

// ═════════════════════════════════════════════════════════════════════════════
// Main Page Component
// ═════════════════════════════════════════════════════════════════════════════
export default function MaterialsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterTab, setFilterTab] = useState<"All" | "Clusters" | "Unique">("All");

  const [clusters, setClusters] = useState<ClusterGroup[]>([]);
  const [singletons, setSingletons] = useState<MaterialItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  // Bulk actions
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [generating, setGenerating] = useState(false);

  // ─── Fetch ──────────────────────────────────────────────────────────────────
  const fetchMaterials = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: "150",
      });

      if (filterTab === "Clusters") params.append("filter_mode", "CLUSTER");
      else if (filterTab === "Unique") params.append("filter_mode", "UNIQUE");

      if (searchTerm) params.append("search", searchTerm);

      const response = await api.get(`/api/materials?${params.toString()}`);
      const items: MaterialItem[] = response.data.items;

      // Separate parents (cluster heads) from children and singletons
      const parentMap = new Map<number, ClusterGroup>();
      const childItems: MaterialItem[] = [];
      const uniqueItems: MaterialItem[] = [];

      // First pass: identify parents (items with cluster_number set)
      items.forEach((item) => {
        if (item.cluster_number != null) {
          parentMap.set(item.id, { parent: item, children: [], isExpanded: false });
        }
      });

      // Second pass: assign children to parents, collect singletons
      items.forEach((item) => {
        if (item.cluster_number != null) return; // already handled as parent

        if (item.matched_material_id && parentMap.has(item.matched_material_id)) {
          parentMap.get(item.matched_material_id)!.children.push(item);
        } else if (item.matched_material_id) {
          // Orphan child — its parent wasn't fetched; show it standalone
          uniqueItems.push(item);
        } else {
          // True singleton
          uniqueItems.push(item);
        }
      });

      setClusters(Array.from(parentMap.values()));
      setSingletons(uniqueItems);
      setTotalPages(response.data.total_pages);
      setTotalItems(response.data.total);
    } catch (error) {
      console.error("Error fetching materials", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const delay = setTimeout(() => fetchMaterials(), 300);
    return () => clearTimeout(delay);
  }, [searchTerm, filterTab, page]);

  // ─── Handlers ──────────────────────────────────────────────────────────────
  const toggleExpand = (parentId: number) => {
    setClusters((prev) =>
      prev.map((c) =>
        c.parent.id === parentId ? { ...c, isExpanded: !c.isExpanded } : c
      )
    );
  };

  const toggleSelection = (id: number) => {
    const next = new Set(selectedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedIds(next);
  };

  const handleGenerateNames = async () => {
    setGenerating(true);
    try {
      await api.post("/api/materials/generate-names");
      alert("AI Generation triggered in the background. The catalog will update shortly.");
      fetchMaterials();
    } catch {
      alert("Failed to start generation.");
    } finally {
      setGenerating(false);
    }
  };

  // ─── What to render ─────────────────────────────────────────────────────────
  // In "All" tab: clusters first, then singletons
  // In "Clusters" tab: only clusters
  // In "Unique" tab: only singletons
  const showClusters = filterTab !== "Unique";
  const showSingletons = filterTab !== "Clusters";
  const hasAny = (showClusters && clusters.length > 0) || (showSingletons && singletons.length > 0);

  // ─── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen p-8 bg-slate-50/50">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Materials Master</h1>
            <p className="text-slate-500 mt-1 font-medium">Browse, filter, and review AI-grouped material clusters.</p>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="flex gap-3">
            <button
              onClick={handleGenerateNames}
              disabled={generating}
              className="flex items-center px-4 py-2 bg-indigo-100 border border-indigo-200 rounded-xl text-sm font-bold text-indigo-700 hover:bg-indigo-200 transition-colors shadow-sm disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4 mr-2 text-indigo-600" />
              {generating ? "Generating..." : "Generate Names"}
            </button>
            <button className="flex items-center px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-sm">
              <ArrowDownToLine className="w-4 h-4 mr-2 text-slate-400" />
              Export
            </button>
          </motion.div>
        </div>

        {/* Search + Tabs */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 flex flex-col md:flex-row gap-4 items-center justify-between"
        >
          <div className="relative w-full md:w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="text"
              placeholder="Search descriptions, codes..."
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
              className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-medium text-sm"
            />
          </div>

          <div className="flex bg-slate-100 p-1 rounded-xl w-full md:w-auto">
            {(["All", "Clusters", "Unique"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => { setFilterTab(tab); setPage(1); setSelectedIds(new Set()); }}
                className={`px-5 py-1.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-all ${
                  filterTab === tab
                    ? "bg-white text-indigo-600 shadow-sm"
                    : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                }`}
              >
                {tab === "Clusters" ? "Duplicates" : tab}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden min-h-[500px]"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider w-16"></th>
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">CPSE / Code</th>
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Raw Description</th>
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Standardized Details</th>
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto" />
                      <p className="text-slate-500 mt-4 font-medium text-sm">Loading materials...</p>
                    </td>
                  </tr>
                ) : !hasAny ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                      No materials found matching your criteria.
                    </td>
                  </tr>
                ) : (
                  <>
                    {/* ── Cluster Rows ──────────────────────────────────── */}
                    {showClusters &&
                      clusters.map((cluster, idx) => (
                        <React.Fragment key={`cluster-${cluster.parent.id}`}>
                          {/* Parent (Cluster Head) */}
                          <motion.tr
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: Math.min(idx * 0.03, 0.4) }}
                            onClick={() => toggleExpand(cluster.parent.id)}
                            className="cursor-pointer hover:bg-indigo-50/40 transition-colors"
                          >
                            <td className="px-6 py-4">
                              {cluster.isExpanded ? (
                                <ChevronDown className="w-5 h-5 text-indigo-500" />
                              ) : (
                                <ChevronRight className="w-5 h-5 text-slate-400" />
                              )}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="flex flex-col">
                                <span className="text-sm font-bold text-slate-800">{cluster.parent.cpse_source}</span>
                                <span className="text-xs text-slate-500 font-mono mt-0.5">{cluster.parent.legacy_item_code}</span>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800 line-clamp-2 max-w-md" title={cluster.parent.raw_description}>
                                {cluster.parent.raw_description}
                              </p>
                            </td>
                            <td className="px-6 py-4">
                              {cluster.parent.standardized_description ? (
                                <span className="text-sm font-bold text-indigo-700 line-clamp-1">{cluster.parent.standardized_description}</span>
                              ) : (
                                <span className="text-sm italic text-slate-400">Awaiting LLM Generation</span>
                              )}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <ClusterLabel number={cluster.parent.cluster_number!} childCount={cluster.children.length} />
                            </td>
                          </motion.tr>

                          {/* Children (expanded dropdown) */}
                          <AnimatePresence>
                            {cluster.isExpanded &&
                              cluster.children.map((child) => (
                                <motion.tr
                                  key={child.id}
                                  initial={{ opacity: 0, height: 0 }}
                                  animate={{ opacity: 1, height: "auto" }}
                                  exit={{ opacity: 0, height: 0 }}
                                  className="bg-slate-50/80 border-l-4 border-l-indigo-400"
                                >
                                  <td className="px-6 py-3 pl-10">
                                    <LinkIcon className="w-4 h-4 text-indigo-300" />
                                  </td>
                                  <td className="px-6 py-3 whitespace-nowrap">
                                    <div className="flex flex-col">
                                      <span className="text-xs font-bold text-slate-700">{child.cpse_source}</span>
                                      <span className="text-[11px] text-slate-500 font-mono mt-0.5">{child.legacy_item_code}</span>
                                    </div>
                                  </td>
                                  <td className="px-6 py-3">
                                    <p className="text-xs font-medium text-slate-600 line-clamp-2 max-w-md" title={child.raw_description}>
                                      {child.raw_description}
                                    </p>
                                  </td>
                                  <td className="px-6 py-3">
                                    <span className="text-xs italic text-slate-400">
                                      Maps to Cluster {cluster.parent.cluster_number}
                                    </span>
                                  </td>
                                  <td className="px-6 py-3 whitespace-nowrap">
                                    <ChildBadge
                                      classification={child.classification}
                                      score={child.similarity_score || 0}
                                    />
                                  </td>
                                </motion.tr>
                              ))}
                          </AnimatePresence>
                        </React.Fragment>
                      ))}

                    {/* ── Singleton (Unique) Rows ──────────────────────── */}
                    {showSingletons &&
                      singletons.map((item, idx) => (
                        <motion.tr
                          key={`unique-${item.id}`}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: Math.min(idx * 0.02, 0.3) }}
                          className="hover:bg-slate-50/50 transition-colors"
                        >
                          <td className="px-6 py-4">
                            <span className="w-5 h-5 block" />
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex flex-col">
                              <span className="text-sm font-bold text-slate-800">{item.cpse_source}</span>
                              <span className="text-xs text-slate-500 font-mono mt-0.5">{item.legacy_item_code}</span>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <p className="text-sm font-medium text-slate-700 line-clamp-2 max-w-md" title={item.raw_description}>
                              {item.raw_description}
                            </p>
                          </td>
                          <td className="px-6 py-4">
                            {item.standardized_description ? (
                              <span className="text-sm font-bold text-indigo-700 line-clamp-1">{item.standardized_description}</span>
                            ) : (
                              <span className="text-sm italic text-slate-400">Awaiting LLM Generation</span>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <UniqueLabel />
                          </td>
                        </motion.tr>
                      ))}
                  </>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
            <span className="text-sm text-slate-500">
              {showClusters && clusters.length > 0 && (
                <><span className="font-bold text-indigo-600">{clusters.length}</span> clusters</>
              )}
              {showClusters && showSingletons && clusters.length > 0 && singletons.length > 0 && " · "}
              {showSingletons && singletons.length > 0 && (
                <><span className="font-bold text-slate-700">{singletons.length}</span> unique items</>
              )}
              {" "}(Total <span className="font-bold text-slate-700">{totalItems}</span> rows)
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
                className="px-3 py-1 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || loading || totalPages === 0}
                className="px-3 py-1 text-sm font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
