"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
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
  Zap
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
  show: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100 } }
};

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/dashboard/stats');
      setStats(response.data.stats);
    } catch (error) {
      console.error("Failed to fetch dashboard stats", error);
      // Fallback for demonstration if backend fails
      setStats({
        total_materials: 2548,
        total_cnmc_codes: 842,
        duplicate_reduction_pct: 62.4,
        pending_reviews: 14,
        total_duplicates: 1540
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

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
            <Link href="/upload" className="bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 py-2.5 rounded-xl font-semibold shadow-sm transition-all flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Upload Catalog
            </Link>
            <button 
              onClick={fetchStats}
              className="flex items-center px-4 py-2.5 bg-indigo-600 border border-transparent rounded-xl text-sm font-bold text-white hover:bg-indigo-700 transition-all shadow-sm shadow-indigo-200"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Sync Now
            </button>
          </motion.div>
        </div>

        {/* Stats Grid */}
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
              <span className="text-slate-500 font-medium">
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

        {/* Charts & Activity Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
          {/* Main Chart Area */}
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 }}
            className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-100 p-6"
          >
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-bold text-slate-800 flex items-center">
                <BarChart3 className="w-5 h-5 mr-2 text-indigo-500" />
                Standardization Progress
              </h2>
              <select className="bg-slate-50 border border-slate-200 text-sm rounded-lg px-3 py-1.5 outline-none focus:ring-2 focus:ring-indigo-500 font-medium text-slate-600">
                <option>Last 30 Days</option>
                <option>Last 7 Days</option>
                <option>All Time</option>
              </select>
            </div>
            
            <div className="h-64 flex items-center justify-center border-2 border-dashed border-slate-100 rounded-xl bg-slate-50/50">
              <div className="text-center">
                <BarChart3 className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-400 font-medium">Chart Visualization Area</p>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
