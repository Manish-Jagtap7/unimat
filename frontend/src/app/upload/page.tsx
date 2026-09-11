"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { Upload, File, X, CheckCircle, AlertCircle, Building2, Zap } from "lucide-react";

export default function UploadPage() {
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [cpse, setCpse] = useState("");
  const [uploading, setUploading] = useState(false);

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

  const handleUpload = async () => {
    if (files.length === 0 || !cpse) return;
    setUploading(true);
    
    try {
      const formData = new FormData();
      // Fast API expects lists of files and corresponding cpse_codes
      files.forEach((file) => {
        formData.append("files", file);
        formData.append("cpse_codes", cpse);
      });

      const response = await api.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      // If success, we should immediately trigger the pipeline processing
      const sessionIds = response.data.sessions.map((s: any) => s.id);
      
      await api.post('/api/pipeline/run', {
        session_ids: sessionIds
      });

      setFiles([]);
      alert("Upload successful! AI Pipeline is now processing the catalogs.");
    } catch (error) {
      console.error("Upload failed", error);
      alert("Failed to upload catalogs. Please check the backend logs.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen p-8 bg-slate-50/50">
      <div className="max-w-4xl mx-auto space-y-8">
        
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Upload CPSE Data</h1>
          <p className="text-slate-500 mt-2 font-medium">Upload raw material catalogs for AI standardization.</p>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, y: 20 }} 
          animate={{ opacity: 1, y: 0 }} 
          className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8"
        >
          {/* CPSE Selection */}
          <div className="mb-8">
            <label className="text-sm font-bold text-slate-700 mb-2 flex items-center">
              <Building2 className="w-4 h-4 mr-2 text-indigo-500" />
              Source CPSE Organization
            </label>
            <select 
              value={cpse}
              onChange={(e) => setCpse(e.target.value)}
              className="w-full mt-2 p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 transition-all text-slate-700 font-semibold"
            >
              <option value="" disabled>Choose an Organization...</option>
              <option value="MIXED">MIXED (Multiple CPSEs in File)</option>
              <option value="IOCL">IOCL - Indian Oil Corporation</option>
              <option value="ONGC">ONGC - Oil and Natural Gas Corp</option>
              <option value="BPCL">BPCL - Bharat Petroleum</option>
              <option value="HPCL">HPCL - Hindustan Petroleum</option>
              <option value="GAIL">GAIL (India) Limited</option>
              <option value="NTPC">NTPC Limited</option>
              <option value="BHEL">BHEL - Bharat Heavy Electricals</option>
            </select>
          </div>



          {/* Drag & Drop Area */}
          <div 
            className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all ${
              dragActive ? "border-indigo-500 bg-indigo-50/50" : "border-slate-300 hover:bg-slate-50"
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input 
              type="file" 
              multiple 
              accept=".xlsx,.xls,.csv" 
              onChange={handleChange} 
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div className="flex flex-col items-center pointer-events-none">
              <div className="p-4 bg-indigo-100 rounded-full text-indigo-600 mb-4">
                <Upload className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-bold text-slate-800">Drag & Drop files here</h3>
              <p className="text-slate-500 mt-2 font-medium">or click to browse from your computer</p>
              <p className="text-xs text-slate-400 mt-4">Supported formats: .XLSX, .XLS, .CSV (Max 50MB)</p>
            </div>
          </div>

          {/* File List */}
          <AnimatePresence>
            {files.length > 0 && (
              <motion.div 
                initial={{ opacity: 0, height: 0 }} 
                animate={{ opacity: 1, height: "auto" }} 
                exit={{ opacity: 0, height: 0 }}
                className="mt-8 space-y-3"
              >
                <h4 className="text-sm font-bold text-slate-700">Files to Upload ({files.length})</h4>
                {files.map((file, i) => (
                  <motion.div 
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    key={`${file.name}-${i}`} 
                    className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl"
                  >
                    <div className="flex items-center">
                      <File className="w-5 h-5 text-indigo-500 mr-3" />
                      <div>
                        <p className="text-sm font-medium text-slate-800">{file.name}</p>
                        <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                    </div>
                    <button 
                      onClick={() => removeFile(i)}
                      className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Upload Button */}
          <div className="mt-8 pt-8 border-t border-slate-100 flex justify-end">
            <button 
              onClick={handleUpload}
              disabled={files.length === 0 || !cpse || uploading}
              className={`px-8 py-3 rounded-xl font-bold transition-all shadow-sm flex items-center justify-center min-w-[200px] ${
                files.length > 0 && cpse && !uploading
                  ? "bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-200"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed"
              }`}
            >
              {uploading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                  Uploading...
                </>
              ) : (
                "Upload & Standardize"
              )}
            </button>
          </div>

        </motion.div>
      </div>
    </div>
  );
}
