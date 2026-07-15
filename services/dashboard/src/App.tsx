import { useEffect, useState, useCallback } from 'react';
import { Shield, AlertTriangle, CheckCircle, Search, Mail, Activity, Menu, ShieldAlert, Check, XCircle, Clock, User, FileText, Server, Database, Wifi, RefreshCw, Eye } from 'lucide-react';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { motion } from 'framer-motion';
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- Type Definitions ---
interface Alert {
  alert_id: string;
  message_id: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  threat_type: string;
  sender_email: string;
  subject: string;
  action_taken: string;
  timestamp: string;
}

interface Stats {
  total_processed: number;
  allowed: number;
  quarantined: number;
  blocked: number;
  avg_threat_score: number;
}

interface InboxEmail {
  message_id: string;
  timestamp_received: string;
  sender_email: string;
  subject: string;
  decision: string;
  threat_score: number;
}

interface QuarantineEmail {
  message_id: string;
  timestamp_received: string;
  sender_email: string;
  subject: string;
  decision: string;
  threat_score: number;
  reasoning: Record<string, string>;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8001/api/ws/alerts';

// --- Reusable Table Component ---
function DataTable({ columns, data, emptyMessage, onRowClick }: {
  columns: { key: string; label: string; render?: (val: any, row: any) => React.ReactNode }[];
  data: any[];
  emptyMessage: string;
  onRowClick?: (row: any) => void;
}) {
  return (
    <div className="glass-panel overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="border-b border-slate-700/50 bg-slate-900/50">
              {columns.map(col => (
                <th key={col.key} className="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-16 text-center">
                  <div className="flex flex-col items-center gap-3 text-slate-500">
                    <Mail className="opacity-30" size={40} />
                    <p className="text-sm font-medium">{emptyMessage}</p>
                  </div>
                </td>
              </tr>
            ) : (
              data.map((row, i) => (
                <tr
                  key={row.message_id || i}
                  className={cn("transition-colors hover:bg-slate-800/30", onRowClick && "cursor-pointer")}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map(col => (
                    <td key={col.key} className="px-6 py-4 text-slate-300 whitespace-nowrap">
                      {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --- Badge Components ---
function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    HIGH: 'bg-red-500/20 text-red-400 border-red-500/30',
    MEDIUM: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    LOW: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  };
  return (
    <span className={cn("text-xs font-bold px-2.5 py-1 rounded-md tracking-wide border", styles[severity] || styles.LOW)}>
      {severity}
    </span>
  );
}

function DecisionBadge({ decision }: { decision: string }) {
  const styles: Record<string, string> = {
    ALLOW: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    BLOCK: 'bg-red-500/20 text-red-400 border-red-500/30',
    QUARANTINE: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  };
  return (
    <span className={cn("text-xs font-bold px-2.5 py-1 rounded-md tracking-wide border", styles[decision] || 'bg-slate-500/20 text-slate-300 border-slate-500/30')}>
      {decision}
    </span>
  );
}

function formatTimestamp(ts: string): string {
  if (!ts) return '—';
  try {
    const date = new Date(ts);
    return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}

// ==================== MAIN APP ====================

function App() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<Stats>({ total_processed: 0, allowed: 0, quarantined: 0, blocked: 0, avg_threat_score: 0 });
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isConnected, setIsConnected] = useState(false);

  // Tab-specific data
  const [inboxEmails, setInboxEmails] = useState<InboxEmail[]>([]);
  const [quarantineEmails, setQuarantineEmails] = useState<QuarantineEmail[]>([]);
  const [allAlerts, setAllAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch data for the active tab
  const fetchTabData = useCallback(async (tab: string) => {
    setIsLoading(true);
    try {
      if (tab === 'inbox') {
        const res = await fetch(`${API_BASE}/api/inbox?limit=50`);
        const data = await res.json();
        setInboxEmails(Array.isArray(data) ? data : []);
      } else if (tab === 'quarantine') {
        const res = await fetch(`${API_BASE}/api/quarantine?limit=50`);
        const data = await res.json();
        setQuarantineEmails(Array.isArray(data) ? data : []);
      } else if (tab === 'alerts') {
        const res = await fetch(`${API_BASE}/api/alerts?limit=50`);
        const data = await res.json();
        setAllAlerts(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error(`Failed to fetch ${tab} data:`, e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTabData(activeTab);
  }, [activeTab, fetchTabData]);

  useEffect(() => {
    // Initial fetch
    fetch(`${API_BASE}/api/stats`)
      .then(r => r.json())
      .then(d => setStats(d))
      .catch(e => console.error('Failed to fetch stats:', e));

    fetch(`${API_BASE}/api/alerts?limit=20`)
      .then(r => r.json())
      .then(d => setAlerts(Array.isArray(d) ? d : []))
      .catch(e => console.error('Failed to fetch initial alerts:', e));

    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connectWs = () => {
      ws = new WebSocket(WS_URL);
      
      ws.onopen = () => setIsConnected(true);
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setAlerts(prev => {
            const arr = Array.isArray(prev) ? prev : [];
            return [data, ...arr].slice(0, 50);
          });
        
          setStats(prev => ({
            ...prev,
            total_processed: prev.total_processed + 1,
            blocked: data.action_taken === 'BLOCK' ? prev.blocked + 1 : prev.blocked,
            quarantined: data.action_taken === 'QUARANTINE' ? prev.quarantined + 1 : prev.quarantined,
            allowed: data.action_taken === 'ALLOW' ? prev.allowed + 1 : prev.allowed,
          }));
        } catch(e) {
          console.error("Error parsing websocket message", e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimer = setTimeout(connectWs, 3000);
      };
    };

    connectWs();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  const chartData = [
    { name: '10:00', emails: 400, threats: 24 },
    { name: '11:00', emails: 300, threats: 13 },
    { name: '12:00', emails: 1200, threats: 98 },
    { name: '13:00', emails: 2500, threats: 190 },
    { name: '14:00', emails: 1800, threats: 105 },
    { name: '15:00', emails: 800, threats: 43 },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex overflow-hidden relative">
      {/* Dynamic Background Glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-brand-primary/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-brand-accent/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Sidebar */}
      <div className="w-64 glass-panel flex-col m-4 mr-0 hidden md:flex z-10 border border-slate-700/40">
        <div className="p-6 flex items-center gap-3 text-brand-primary border-b border-slate-800">
          <div className="relative">
            <Shield size={32} />
            {isConnected && (
              <span className="absolute bottom-0 right-0 w-3 h-3 bg-brand-safe rounded-full border-2 border-slate-900 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
            )}
          </div>
          <h1 className="text-2xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-brand-primary to-brand-accent">
            SecureMail
          </h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          {['Dashboard', 'Inbox', 'Quarantine', 'Alerts', 'Admin'].map(item => (
            <button 
              key={item}
              onClick={() => setActiveTab(item.toLowerCase())}
              className={cn(
                "w-full text-left px-4 py-3 rounded-xl flex items-center gap-3 transition-all duration-300 relative overflow-hidden group",
                activeTab === item.toLowerCase() 
                  ? "text-white shadow-lg" 
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
              )}
            >
              {activeTab === item.toLowerCase() && (
                <motion.div 
                  layoutId="activeTab" 
                  className="absolute inset-0 bg-gradient-to-r from-brand-primary/20 to-brand-accent/20 border border-brand-primary/30 rounded-xl"
                  initial={false}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
              <div className="relative z-10 flex items-center gap-3">
                {item === 'Dashboard' && <Activity size={20} className={activeTab === 'dashboard' ? 'text-brand-primary' : ''} />}
                {item === 'Inbox' && <CheckCircle size={20} className={activeTab === 'inbox' ? 'text-brand-safe' : ''} />}
                {item === 'Quarantine' && <AlertTriangle size={20} className={activeTab === 'quarantine' ? 'text-amber-400' : ''} />}
                {item === 'Alerts' && <ShieldAlert size={20} className={activeTab === 'alerts' ? 'text-brand-danger' : ''} />}
                {item === 'Admin' && <Menu size={20} />}
                <span className="font-semibold">{item}</span>
              </div>
            </button>
          ))}
        </nav>
        
        <div className="p-4 border-t border-slate-800">
          <div className="glass-card p-4 rounded-xl flex items-center gap-3">
             <div className={cn("w-2 h-2 rounded-full", isConnected ? "bg-brand-safe shadow-[0_0_10px_rgba(16,185,129,0.8)]" : "bg-brand-danger shadow-[0_0_10px_rgba(239,68,68,0.8)]")} />
             <span className="text-xs font-medium text-slate-400">{isConnected ? 'System Online' : 'Reconnecting...'}</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-4 md:p-8 overflow-y-auto z-10">
        <header className="flex justify-between items-center mb-8 glass-panel p-4 px-6 rounded-2xl">
          <div>
            <h2 className="text-3xl font-bold text-white capitalize tracking-tight">{activeTab}</h2>
            <p className="text-slate-400 mt-1 text-sm font-medium">Real-time threat intelligence platform</p>
          </div>
          <div className="bg-slate-900/50 border border-slate-700/50 rounded-full px-4 py-2 flex items-center gap-2 focus-within:ring-2 ring-brand-primary/50 transition-all shadow-inner">
            <Search size={18} className="text-slate-400" />
            <input 
              type="text" 
              placeholder="Search indicators..." 
              className="bg-transparent border-none outline-none text-sm placeholder:text-slate-500 w-64 text-white"
            />
          </div>
        </header>

        {/* ===== DASHBOARD TAB ===== */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Stats row */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {[
                { label: 'Processed', value: stats.total_processed, icon: Mail, color: 'text-brand-primary', border: 'border-brand-primary/50', glow: 'shadow-[0_0_20px_rgba(59,130,246,0.15)]' },
                { label: 'Allowed', value: stats.allowed, icon: Check, color: 'text-brand-safe', border: 'border-brand-safe/50', glow: 'shadow-[0_0_20px_rgba(16,185,129,0.15)]' },
                { label: 'Quarantined', value: stats.quarantined, icon: AlertTriangle, color: 'text-amber-400', border: 'border-amber-400/50', glow: 'shadow-[0_0_20px_rgba(251,191,36,0.15)]' },
                { label: 'Blocked', value: stats.blocked, icon: XCircle, color: 'text-brand-danger', border: 'border-brand-danger/50', glow: 'shadow-[0_0_20px_rgba(239,68,68,0.15)]' },
              ].map((stat, i) => (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  key={stat.label + '-' + i} 
                  className={cn("glass-panel p-6 border-t-2 relative overflow-hidden", stat.border, stat.glow)}
                >
                  <div className="absolute -right-4 -top-4 opacity-10">
                    <stat.icon size={100} />
                  </div>
                  <div className="text-slate-400 text-sm font-semibold mb-2 flex items-center gap-2">
                    <stat.icon size={16} className={stat.color} /> 
                    {stat.label}
                  </div>
                  <div className="text-4xl font-black tracking-tight text-[#f8fafc]">
                    {(stat.value || 0).toLocaleString()}
                  </div>
                </motion.div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[500px]">
              {/* Chart */}
              <div className="lg:col-span-2 glass-panel p-6 flex flex-col">
                <h3 className="text-xl font-bold text-white mb-6">Traffic & Threat Volume</h3>
                <div className="flex-1 min-h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorEmails" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorThreats" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                      <XAxis dataKey="name" stroke="#64748b" axisLine={false} tickLine={false} />
                      <YAxis stroke="#64748b" axisLine={false} tickLine={false} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', backdropFilter: 'blur(10px)', borderColor: '#334155', borderRadius: '12px' }}
                        itemStyle={{ color: '#f1f5f9' }}
                      />
                      <Area type="monotone" dataKey="emails" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorEmails)" />
                      <Area type="monotone" dataKey="threats" stroke="#ef4444" strokeWidth={3} fillOpacity={1} fill="url(#colorThreats)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Alerts Feed */}
              <div className="glass-panel p-0 flex flex-col overflow-hidden">
                <div className="p-6 pb-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
                  <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    <Activity size={20} className="text-brand-primary" />
                    Live Threat Feed
                  </h3>
                  <span className="flex h-3 w-3 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                  </span>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar relative">
                  {!Array.isArray(alerts) || alerts.length === 0 ? (
                     <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500">
                        <Activity className="animate-pulse mb-2 opacity-50" size={32} />
                        <p className="text-sm font-medium">Listening for events...</p>
                     </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {alerts.map((alert, i) => (
                        <div 
                          key={alert.alert_id || i} 
                          className={cn(
                            "glass-card p-4 flex flex-col gap-2 relative overflow-hidden group transition-all",
                            alert.severity === 'HIGH' && i === 0 ? 'animate-glow border-red-500/50' : ''
                          )}
                        >
                          {alert.severity === 'HIGH' && (
                            <div className="absolute top-0 left-0 w-1 h-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.8)]" />
                          )}
                          <div className="flex justify-between items-center">
                            <SeverityBadge severity={alert.threat_type === 'SAFE' ? 'LOW' : alert.severity} />
                            <span className="text-[10px] text-slate-500 font-medium">{formatTimestamp(alert.timestamp)}</span>
                          </div>
                          <div>
                            <div className="text-sm font-bold text-white truncate group-hover:text-brand-primary transition-colors cursor-pointer">
                              {alert.sender_email || 'Unknown Sender'}
                            </div>
                            <div className="text-xs text-slate-400 truncate mt-0.5">{alert.subject || 'No Subject'}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ===== INBOX TAB ===== */}
        {activeTab === 'inbox' && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <CheckCircle size={20} className="text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Allowed Emails</h3>
                  <p className="text-xs text-slate-500">Emails that passed all security checks</p>
                </div>
              </div>
              <button
                onClick={() => fetchTabData('inbox')}
                className="glass-card px-4 py-2 rounded-xl text-sm font-medium text-slate-300 hover:text-white flex items-center gap-2 transition-colors"
              >
                <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>

            <DataTable
              columns={[
                { key: 'timestamp_received', label: 'Date', render: (val: string) => (
                  <span className="flex items-center gap-2 text-slate-400"><Clock size={14} />{formatTimestamp(val)}</span>
                )},
                { key: 'sender_email', label: 'From', render: (val: string) => (
                  <span className="flex items-center gap-2 font-medium text-white"><User size={14} className="text-slate-500" />{val}</span>
                )},
                { key: 'subject', label: 'Subject', render: (val: string) => (
                  <span className="max-w-[300px] truncate block">{val || '(No Subject)'}</span>
                )},
                { key: 'decision', label: 'Decision', render: (val: string) => <DecisionBadge decision={val} /> },
                { key: 'threat_score', label: 'Risk Score', render: (val: number) => (
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                      <div className={cn("h-full rounded-full", val > 60 ? 'bg-red-500' : val > 30 ? 'bg-amber-500' : 'bg-emerald-500')} style={{ width: `${Math.min(val || 0, 100)}%` }} />
                    </div>
                    <span className="text-xs font-mono text-slate-400">{val ?? 0}</span>
                  </div>
                )},
              ]}
              data={inboxEmails}
              emptyMessage="No allowed emails yet. Emails that pass security checks will appear here."
            />
          </motion.div>
        )}

        {/* ===== QUARANTINE TAB ===== */}
        {activeTab === 'quarantine' && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20">
                  <AlertTriangle size={20} className="text-amber-400" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Quarantined & Blocked Emails</h3>
                  <p className="text-xs text-slate-500">Emails flagged as suspicious or malicious</p>
                </div>
              </div>
              <button
                onClick={() => fetchTabData('quarantine')}
                className="glass-card px-4 py-2 rounded-xl text-sm font-medium text-slate-300 hover:text-white flex items-center gap-2 transition-colors"
              >
                <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>

            <DataTable
              columns={[
                { key: 'timestamp_received', label: 'Date', render: (val: string) => (
                  <span className="flex items-center gap-2 text-slate-400"><Clock size={14} />{formatTimestamp(val)}</span>
                )},
                { key: 'sender_email', label: 'From', render: (val: string) => (
                  <span className="flex items-center gap-2 font-medium text-white"><User size={14} className="text-red-400" />{val}</span>
                )},
                { key: 'subject', label: 'Subject', render: (val: string) => (
                  <span className="max-w-[300px] truncate block text-amber-200/80">{val || '(No Subject)'}</span>
                )},
                { key: 'decision', label: 'Decision', render: (val: string) => <DecisionBadge decision={val} /> },
                { key: 'threat_score', label: 'Risk Score', render: (val: number) => (
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                      <div className="h-full rounded-full bg-red-500" style={{ width: `${Math.min(val || 0, 100)}%` }} />
                    </div>
                    <span className="text-xs font-mono text-red-400 font-bold">{val ?? 0}</span>
                  </div>
                )},
                { key: 'reasoning', label: 'Reason', render: (val: any) => (
                  <span className="text-xs text-slate-400 max-w-[200px] truncate block">
                    {typeof val === 'object' ? val?.explanation || '—' : val || '—'}
                  </span>
                )},
              ]}
              data={quarantineEmails}
              emptyMessage="No quarantined emails. Suspicious emails will appear here."
            />
          </motion.div>
        )}

        {/* ===== ALERTS TAB ===== */}
        {activeTab === 'alerts' && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-red-500/10 border border-red-500/20">
                  <ShieldAlert size={20} className="text-red-400" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Security Alerts</h3>
                  <p className="text-xs text-slate-500">All threat detection events</p>
                </div>
              </div>
              <button
                onClick={() => fetchTabData('alerts')}
                className="glass-card px-4 py-2 rounded-xl text-sm font-medium text-slate-300 hover:text-white flex items-center gap-2 transition-colors"
              >
                <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>

            <DataTable
              columns={[
                { key: 'timestamp', label: 'Time', render: (val: string) => (
                  <span className="flex items-center gap-2 text-slate-400"><Clock size={14} />{formatTimestamp(val)}</span>
                )},
                { key: 'severity', label: 'Severity', render: (val: string) => <SeverityBadge severity={val} /> },
                { key: 'threat_type', label: 'Threat Type', render: (val: string) => (
                  <span className="flex items-center gap-2">
                    <ShieldAlert size={14} className={val === 'PHISHING' ? 'text-red-400' : 'text-slate-500'} />
                    <span className="font-medium">{val}</span>
                  </span>
                )},
                { key: 'sender_email', label: 'Sender', render: (val: string) => (
                  <span className="font-medium text-white">{val}</span>
                )},
                { key: 'subject', label: 'Subject', render: (val: string) => (
                  <span className="max-w-[250px] truncate block text-slate-300">{val || '(No Subject)'}</span>
                )},
                { key: 'action_taken', label: 'Action', render: (val: string) => <DecisionBadge decision={val} /> },
              ]}
              data={allAlerts}
              emptyMessage="No alerts yet. Threat detections will appear here."
            />
          </motion.div>
        )}

        {/* ===== ADMIN TAB ===== */}
        {activeTab === 'admin' && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-xl bg-slate-500/10 border border-slate-500/20">
                <Server size={20} className="text-slate-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">System Administration</h3>
                <p className="text-xs text-slate-500">Service status and system overview</p>
              </div>
            </div>

            {/* Service Status Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { name: 'SMTP Gateway', desc: 'Email receiver & parser', icon: Mail, port: '587/25', status: 'active' },
                { name: 'API Service', desc: 'REST API & Decision engine', icon: Server, port: '8001', status: 'active' },
                { name: 'AI Worker', desc: 'Gemini phishing classifier', icon: Eye, port: 'Kafka consumer', status: 'active' },
                { name: 'Reputation Worker', desc: 'VirusTotal URL/hash lookup', icon: ShieldAlert, port: 'Kafka consumer', status: 'active' },
                { name: 'PostgreSQL', desc: 'Email & threat data store', icon: Database, port: '5432', status: 'active' },
                { name: 'Redis', desc: 'Caching & rate limiting', icon: Database, port: '6379', status: 'active' },
                { name: 'Kafka', desc: 'Event streaming broker', icon: Activity, port: '9092', status: 'active' },
                { name: 'Prometheus', desc: 'Metrics collection', icon: FileText, port: '9090', status: 'active' },
                { name: 'Grafana', desc: 'Monitoring dashboards', icon: Activity, port: '3001', status: 'active' },
              ].map((svc, i) => (
                <motion.div
                  key={svc.name}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="glass-card p-5 flex items-start gap-4 group hover:border-brand-primary/30 transition-all"
                >
                  <div className="p-2.5 rounded-xl bg-slate-800/50 border border-slate-700/30 group-hover:border-brand-primary/30 transition-colors">
                    <svc.icon size={18} className="text-slate-400 group-hover:text-brand-primary transition-colors" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-bold text-white">{svc.name}</h4>
                      <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.8)]" />
                        <span className="text-[10px] text-emerald-400 font-medium uppercase tracking-wider">Active</span>
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{svc.desc}</p>
                    <span className="text-[10px] text-slate-600 font-mono mt-1 block">{svc.port}</span>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Pipeline Overview */}
            <div className="glass-panel p-6">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <Wifi size={18} className="text-brand-primary" />
                Pipeline Architecture
              </h3>
              <div className="flex items-center justify-between gap-2 py-4 overflow-x-auto">
                {[
                  { label: 'SMTP Gateway', sub: 'Receive & Parse' },
                  { label: 'Kafka', sub: 'email.events' },
                  { label: 'AI Worker', sub: 'Gemini Classification' },
                  { label: 'API Service', sub: 'Decision Engine' },
                  { label: 'Dashboard', sub: 'Real-time Alerts' },
                ].map((step, i, arr) => (
                  <div key={step.label} className="flex items-center gap-2">
                    <div className="flex flex-col items-center gap-1 min-w-[120px]">
                      <div className="w-10 h-10 rounded-xl bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center text-brand-primary font-bold text-sm">
                        {i + 1}
                      </div>
                      <span className="text-xs font-bold text-white text-center">{step.label}</span>
                      <span className="text-[10px] text-slate-500 text-center">{step.sub}</span>
                    </div>
                    {i < arr.length - 1 && (
                      <div className="flex-shrink-0 w-8 h-px bg-gradient-to-r from-brand-primary/50 to-brand-accent/50" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Stats Summary */}
            <div className="glass-panel p-6">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <FileText size={18} className="text-brand-primary" />
                System Summary
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 glass-card rounded-xl">
                  <div className="text-2xl font-black text-brand-primary">{stats.total_processed}</div>
                  <div className="text-xs text-slate-500 mt-1">Total Processed</div>
                </div>
                <div className="text-center p-4 glass-card rounded-xl">
                  <div className="text-2xl font-black text-emerald-400">{stats.allowed}</div>
                  <div className="text-xs text-slate-500 mt-1">Allowed</div>
                </div>
                <div className="text-center p-4 glass-card rounded-xl">
                  <div className="text-2xl font-black text-amber-400">{stats.quarantined}</div>
                  <div className="text-xs text-slate-500 mt-1">Quarantined</div>
                </div>
                <div className="text-center p-4 glass-card rounded-xl">
                  <div className="text-2xl font-black text-red-400">{stats.blocked}</div>
                  <div className="text-xs text-slate-500 mt-1">Blocked</div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

export default App;
