"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { 
  LayoutDashboard, 
  UploadCloud, 
  Database, 
  CheckSquare, 
  Trash2 
} from "lucide-react";
import { api } from "@/lib/api";

const navItems = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Upload Data", href: "/upload", icon: UploadCloud },
  { name: "Materials Master", href: "/materials", icon: Database },
  { name: "Review Center", href: "/review", icon: CheckSquare },
];

export function Sidebar() {
  const pathname = usePathname();

  const handleResetDb = async () => {
    if (confirm("Are you sure you want to completely wipe the database? This cannot be undone.")) {
      try {
        await api.post('/api/admin/reset-db');
        alert("Database wiped successfully. You can now start a fresh demo.");
        window.location.href = "/";
      } catch (error) {
        console.error("Failed to reset database", error);
        alert("Failed to wipe database.");
      }
    }
  };

  return (
    <div className="flex flex-col w-64 bg-slate-900 border-r border-slate-800 h-screen text-slate-300">
      <div className="flex items-center justify-center h-16 border-b border-slate-800">
        <h1 className="text-xl font-bold text-white tracking-wider flex items-center gap-2">
          <Database className="w-6 h-6 text-indigo-400" />
          UNIMAT
        </h1>
      </div>
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-2">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors duration-200",
                  isActive
                    ? "bg-indigo-600/10 text-indigo-400"
                    : "hover:bg-slate-800 hover:text-white"
                )}
              >
                <item.icon
                  className={cn(
                    "mr-3 flex-shrink-0 h-5 w-5 transition-colors duration-200",
                    isActive ? "text-indigo-400" : "text-slate-400 group-hover:text-slate-300"
                  )}
                  aria-hidden="true"
                />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>
      
      {/* Admin Reset Button */}
      <div className="px-4 py-4">
        <button 
          onClick={handleResetDb}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-lg text-sm font-bold transition-colors"
        >
          <Trash2 className="w-4 h-4" />
          Reset Database
        </button>
      </div>

      <div className="p-4 border-t border-slate-800">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-full bg-indigo-500 flex items-center justify-center text-white font-bold">
              A
            </div>
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-white">Admin User</p>
            <p className="text-xs font-medium text-slate-400">CPSE Hub</p>
          </div>
        </div>
      </div>
    </div>
  );
}
