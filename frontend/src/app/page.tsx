"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { 
  Database, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  ArrowRight,
  BarChart3,
  TrendingUp,
  FileText,
  Layers,
  RefreshCw,
  Zap,
  Upload,
  File,
  X
} from "lucide-react";
import Link from "next/link";

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

const itemVariants = {
  hidden: { y: 20, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { type: "spring" as const, stiffness: 100 } }
};

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Upload state
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<{ step: string; pct: number } | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/dashboard/stats');
      setStats(response.data.stats);
    } catch (error) {
      console.error("Failed to fetch dashboard stats", error);
      setStats({
        total_materials: 0,
        total_cnmc_codes: 0,
        duplicate_reduction_pct: 0,
        pending_reviews: 0,
        total_duplicates: 0,
        average_accuracy: null,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  // Upload handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = (newFiles: File[]) => {
    const validFiles = newFiles.filter(
      (file) => file.type === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" || file.type === "text/csv" || file.name.endsWith(".xlsx") || file.name.endsWith(".xls")
    );
    setFiles((prev) => [...prev, ...validFiles]);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Pipeline step labels for display
  const PIPELINE_STEPS = [
    "UPLOADING FILES",
    "PARSING EXCEL DATA",
    "NLP STANDARDIZATION", 
    "TOKENIZING DESCRIPTIONS",
    "EXPANDING ABBREVIATIONS",
    "GENERATING EMBEDDINGS",
    "INDEXING IN VECTOR DB",
    "COMPUTING SIMILARITY",
    "CLASSIFYING ITEMS",
    "GROUPING DUPLICATES",
    "EVALUATING ACCURACY",
    "FINALIZING RESULTS",
  ];

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);

    // ── Smooth client-side progress bar ──────────────────────────────
    // Runs from 0→95% on a fast timer, then snaps to 100% on completion.
    let pct = 0;
    let stepIdx = 0;
    let done = false;

    setProgress({ step: PIPELINE_STEPS[0], pct: 0 });

    const ticker = setInterval(() => {
      if (done) return;

      // Accelerate fast at the start, slow down approaching 95%
      const remaining = 95 - pct;
      const increment = Math.max(0.3, remaining * 0.06);
      pct = Math.min(95, pct + increment);

      // Cycle through step labels based on percentage
      const newStepIdx = Math.min(
        PIPELINE_STEPS.length - 1,
        Math.floor((pct / 95) * PIPELINE_STEPS.length)
      );
      if (newStepIdx !== stepIdx) {
        stepIdx = newStepIdx;
      }

      setProgress({ step: PIPELINE_STEPS[stepIdx], pct: Math.round(pct) });
    }, 80); // tick every 80ms for silky smooth movement

    try {
      // ── Upload files ─────────────────────────────────────────────────
      const formData = new FormData();
      files.forEach((file) => {
        formData.append("files", file);
      });

      const response = await api.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      
      const sessionIds = response.data.sessions.map((s: any) => s.id);

      // ── Trigger pipeline (this returns immediately, pipeline runs in BG) ──
      await api.post('/api/pipeline/run', { session_ids: sessionIds });

      setFiles([]);

      // ── Poll for real completion ─────────────────────────────────────
      const completionCheck = setInterval(async () => {
        try {
          const res = await api.get('/api/pipeline/status');
          const run = res.data;
          if (run && (run.status === "COMPLETED" || run.status === "FAILED")) {
            clearInterval(completionCheck);
            done = true;
            clearInterval(ticker);

            if (run.status === "COMPLETED") {
              setProgress({ step: "✅ COMPLETE", pct: 100 });
              setTimeout(() => { setProgress(null); setUploading(false); fetchStats(); }, 2000);
            } else {
              setProgress({ step: "❌ PIPELINE FAILED", pct: 0 });
              setTimeout(() => { setProgress(null); setUploading(false); }, 3000);
            }
          }
        } catch {
          // Pipeline hasn't started yet or 404, keep waiting
        }
      }, 500);

    } catch (error) {
      clearInterval(ticker);
      console.error("Upload failed", error);
      alert("Failed to upload catalogs. Please check the backend logs.");
      setUploading(false);
      setProgress(null);
    }
  };

  return (
    <div className="min-h-screen p-8 bg-slate-50/50">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Dashboard Overview</h1>
            <p className="text-slate-500 mt-1 font-medium">Real-time metrics for national material standardization.</p>
          </motion.div>
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="flex gap-3">
            <button 
              onClick={fetchStats}
              className="flex items-center px-4 py-2.5 bg-indigo-600 border border-transparent rounded-xl text-sm font-bold text-white hover:bg-indigo-700 transition-all shadow-sm shadow-indigo-200"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Sync Now
            </button>
          </motion.div>
        </div>

        {/* Stats Grid — 4 stat cards */}
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
        >
          {/* Total Materials */}
          <motion.div variants={itemVariants} className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between group hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Total Materials</p>
                <h3 className="text-3xl font-black text-slate-800 mt-2">
                  {loading ? "..." : (stats?.total_materials || 0).toLocaleString()}
                </h3>
              </div>
              <div className="p-3 bg-indigo-50 rounded-xl text-indigo-500 group-hover:bg-indigo-500 group-hover:text-white transition-colors">
                <Layers className="w-6 h-6" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <TrendingUp className="w-4 h-4 text-emerald-500 mr-1" />
              <span className="text-emerald-500 font-semibold">+12%</span>
              <span className="text-slate-400 ml-2">from last month</span>
            </div>
          </motion.div>

          {/* Standardized CNMCs */}
          <motion.div variants={itemVariants} className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between group hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Standardized CNMCs</p>
                <h3 className="text-3xl font-black text-slate-800 mt-2">
                  {loading ? "..." : (stats?.total_cnmc_codes || 0).toLocaleString()}
                </h3>
              </div>
              <div className="p-3 bg-emerald-50 rounded-xl text-emerald-500 group-hover:bg-emerald-500 group-hover:text-white transition-colors">
                <Database className="w-6 h-6" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <div className="w-full bg-slate-100 rounded-full h-1.5 mr-2">
                <div 
                  className="bg-emerald-500 h-1.5 rounded-full" 
                  style={{ width: `${stats?.duplicate_reduction_pct || 0}%` }}
                ></div>
              </div>
              <span className="text-slate-500 font-medium whitespace-nowrap">
                {stats?.duplicate_reduction_pct?.toFixed(1) || 0}% Deduplicated
              </span>
            </div>
          </motion.div>

          {/* Pending Review */}
          <motion.div variants={itemVariants} className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between group hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Pending Review</p>
                <h3 className="text-3xl font-black text-slate-800 mt-2">
                  {loading ? "..." : (stats?.pending_reviews || 0).toLocaleString()}
                </h3>
              </div>
              <div className="p-3 bg-amber-50 rounded-xl text-amber-500 group-hover:bg-amber-500 group-hover:text-white transition-colors">
                <Clock className="w-6 h-6" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <Link href="/review" className="text-indigo-600 font-semibold hover:text-indigo-700 flex items-center">
                Review now <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </div>
          </motion.div>

          {/* AI Accuracy */}
          <motion.div variants={itemVariants} className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between group hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">AI Pipeline Accuracy</p>
                <h3 className="text-3xl font-black text-slate-800 mt-2">
                  {loading ? "..." : (stats?.average_accuracy ? `${stats.average_accuracy}%` : "N/A")}
                </h3>
              </div>
              <div className="p-3 bg-purple-50 rounded-xl text-purple-500 group-hover:bg-purple-500 group-hover:text-white transition-colors">
                <Zap className="w-6 h-6" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <span className="text-purple-500 font-semibold">Based on Ground Truth Eval</span>
            </div>
          </motion.div>
        </motion.div>

        {/* Upload Section — replaces the old "Standardization Progress" chart */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-2xl shadow-sm border border-slate-100 p-8"
        >
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-lg font-bold text-slate-800 flex items-center">
              <Upload className="w-5 h-5 mr-2 text-indigo-500" />
              Upload CPSE Catalog
            </h2>
            <p className="text-sm text-slate-400 font-medium">CPSE auto-detected from file contents</p>
          </div>

          {progress ? (
            <div className="flex flex-col items-center justify-center py-12">
              <p className="text-lg font-bold text-slate-700 mb-4">{progress.step}</p>
              <div className="w-full max-w-lg bg-slate-100 rounded-full h-4">
                <div 
                  className="bg-gradient-to-r from-indigo-500 to-indigo-600 h-4 rounded-full transition-all duration-500 relative overflow-hidden"
                  style={{ width: `${progress.pct}%` }}
                >
                  <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
                </div>
              </div>
              <p className="text-sm text-slate-500 mt-3 font-semibold">{Math.round(progress.pct)}% Complete</p>
            </div>
          ) : (
            <div className="flex flex-col lg:flex-row gap-6">
              {/* Drag & Drop Zone */}
              <div 
                className={`flex-1 border-2 border-dashed rounded-2xl p-10 text-center transition-all cursor-pointer flex flex-col items-center justify-center ${
                  dragActive ? "border-indigo-500 bg-indigo-50/50" : "border-slate-200 bg-slate-50/50 hover:bg-slate-100/50 hover:border-slate-300"
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => document.getElementById("file-upload")?.click()}
              >
                <div className="p-4 bg-indigo-50 rounded-2xl mb-4">
                  <Upload className="w-8 h-8 text-indigo-500" />
                </div>
                <p className="text-base font-bold text-slate-700">Drag & Drop Files Here</p>
                <p className="text-sm text-slate-400 mt-1">or click to browse · .xlsx, .xls, .csv</p>
                <input id="file-upload" type="file" multiple accept=".xlsx,.xls,.csv" className="hidden" onChange={handleChange} />
              </div>

              {/* File List & Upload Button */}
              <div className="flex-1 flex flex-col justify-between">
                {files.length > 0 ? (
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {files.map((file, i) => (
                      <div key={i} className="flex items-center justify-between bg-slate-50 p-3 rounded-xl border border-slate-200">
                        <div className="flex items-center">
                          <FileText className="w-5 h-5 text-indigo-400 mr-3 flex-shrink-0" />
                          <span className="text-sm font-semibold text-slate-700 truncate">{file.name}</span>
                        </div>
                        <button onClick={(e) => { e.stopPropagation(); removeFile(i); }} className="text-slate-400 hover:text-red-500 ml-3 flex-shrink-0">
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-center py-6">
                    <div>
                      <FileText className="w-10 h-10 text-slate-200 mx-auto mb-2" />
                      <p className="text-sm text-slate-400 font-medium">No files selected yet</p>
                    </div>
                  </div>
                )}

                <button 
                  onClick={handleUpload}
                  disabled={files.length === 0 || uploading}
                  className={`w-full mt-4 py-3.5 rounded-xl text-sm font-bold text-white transition-all shadow-sm ${
                    files.length > 0 ? "bg-indigo-600 hover:bg-indigo-700 shadow-indigo-200" : "bg-slate-300 cursor-not-allowed"
                  }`}
                >
                  {uploading ? "Uploading..." : `Process ${files.length > 0 ? files.length : ''} Catalog${files.length !== 1 ? 's' : ''}`}
                </button>
              </div>
            </div>
          )}
        </motion.div>

      </div>
    </div>
  );
}
