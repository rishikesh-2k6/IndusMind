import React, { useState, useEffect, useRef } from 'react';
import {
  LayoutDashboard, FileText, Cpu, Upload, Filter,
  MessageSquare, AlertTriangle, CheckCircle2, TrendingUp, Loader2, Send, Trash2,
  LogOut, ShieldCheck, Wrench
} from 'lucide-react';
import { api } from './api/client';


const TYPE_BADGE = {
  pdf: 'bg-red-50 text-red-500',
  docx: 'bg-blue-50 text-blue-500',
  xlsx: 'bg-emerald-50 text-emerald-600',
  csv: 'bg-emerald-50 text-emerald-600',
  txt: 'bg-slate-100 text-slate-500',
  image: 'bg-purple-50 text-purple-500',
};

const STATUS_BADGE = {
  ready: 'bg-emerald-100 text-emerald-700',
  processing: 'bg-amber-100 text-amber-700',
  failed: 'bg-red-100 text-red-700',
};

export default function AdminDashboard({ onLogout }) {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  // AI prompt panel state
  const [prompt, setPrompt] = useState('');
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);

  const loadDocuments = async () => {
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch (err) {
      setError(err.message || 'Failed to load documents');
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  // Poll while any document is still processing.
  useEffect(() => {
    const anyProcessing = documents.some((d) => d.status === 'processing');
    if (!anyProcessing) return;
    const t = setInterval(loadDocuments, 3000);
    return () => clearInterval(t);
  }, [documents]);

  const handleUploadClick = () => fileInputRef.current?.click();

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-uploading the same file
    if (!file) return;

    setError('');
    setUploading(true);
    try {
      await api.uploadDocument(file);
      await loadDocuments();
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this document? This cannot be undone.')) return;
    try {
      await api.deleteDocument(id);
      await loadDocuments();
    } catch (err) {
      setError(err.message || 'Delete failed');
    }
  };

  const handleAsk = async (e) => {
    e.preventDefault();
    const q = prompt.trim();
    if (!q || asking) return;
    setAsking(true);
    setAnswer(null);
    try {
      const res = await api.query(q);
      setAnswer(res);
    } catch (err) {
      setError(err.message || 'Query failed');
    } finally {
      setAsking(false);
    }
  };

  const readyCount = documents.filter((d) => d.status === 'ready').length;

  return (
    <div className="min-h-screen h-screen w-screen bg-slate-50 text-slate-800 flex font-sans antialiased overflow-hidden">

      {/* LEFT NAV */}
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col justify-between border-r border-slate-800 flex-shrink-0">
        <div>
          <div className="p-6 flex items-center gap-2.5 border-b border-slate-800/60">
            <Cpu className="text-indigo-500 w-6 h-6" />
            <div>
              <h2 className="text-sm font-black tracking-tight text-white leading-none">IndusMind</h2>
              <span className="text-[10px] text-slate-500 font-medium tracking-wide">Admin Dashboard</span>
            </div>
          </div>

          <div className="p-4 space-y-5">
            <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white shadow">
              <LayoutDashboard className="w-4 h-4" /> Dashboard
            </button>
            <div className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 px-3 block mb-1">Knowledge</span>
              <button onClick={handleUploadClick} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"><FileText className="w-4 h-4" /> Documents</button>
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-slate-800/80 bg-slate-950/40 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center font-bold text-xs text-white">A</div>
            <div>
              <p className="text-xs font-bold text-white leading-tight">Administrator</p>
              <p className="text-[10px] text-slate-500">IndusMind</p>
            </div>
          </div>
          <button onClick={onLogout} className="text-slate-500 hover:text-red-400 transition-colors p-1">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* MAIN */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        <header className="bg-white border-b border-slate-200 h-16 px-8 flex items-center justify-between sticky top-0 z-40 flex-shrink-0">
          <div>
            <h1 className="text-sm font-bold text-slate-900">System Command Center</h1>
            <p className="text-[11px] text-slate-400">IndusMind — Admin Panel</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-xs">A</div>
          </div>
        </header>

        <main className="p-8 space-y-6 flex-1 overflow-y-auto">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900">System Command Center Dashboard 📊</h1>
              <p className="text-xs text-slate-500">Live analytical monitoring overlay and cross-linked knowledge indices.</p>
            </div>
            <div className="flex gap-2 text-xs">
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileChange}
                accept="*"
                className="hidden"
              />
              <button
                onClick={handleUploadClick}
                disabled={uploading}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white px-3 py-2 rounded-lg font-medium shadow-sm"
              >
                {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                {uploading ? 'Uploading…' : 'Upload document'}
              </button>
              <button onClick={loadDocuments} className="flex items-center gap-1.5 bg-white border border-slate-200 px-3 py-2 rounded-lg text-slate-600 font-medium shadow-sm"><Filter className="w-3.5 h-3.5" /> Refresh</button>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg px-4 py-2.5">{error}</div>
          )}

          {/* KPI CARDS */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex items-start gap-4">
              <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl"><FileText className="w-5 h-5" /></div>
              <div>
                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total Documents</p>
                <h3 className="text-lg font-black text-slate-900 mt-0.5">{documents.length}</h3>
                <span className="text-[10px] font-semibold text-emerald-600 flex items-center gap-0.5 mt-1"><TrendingUp className="w-3 h-3" /> {readyCount} ready</span>
              </div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex items-start gap-4">
              <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl"><Cpu className="w-5 h-5" /></div>
              <div>
                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Processing</p>
                <h3 className="text-lg font-black text-slate-900 mt-0.5">{documents.filter((d) => d.status === 'processing').length}</h3>
                <span className="text-[10px] font-bold text-amber-500 mt-1 block">In ingestion pipeline</span>
              </div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex items-start gap-4">
              <div className="p-3 bg-amber-50 text-amber-600 rounded-xl"><Wrench className="w-5 h-5" /></div>
              <div>
                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Failed</p>
                <h3 className="text-lg font-black text-slate-900 mt-0.5">{documents.filter((d) => d.status === 'failed').length}</h3>
                <span className="text-[10px] font-bold text-red-500 mt-1 block">Need re-upload</span>
              </div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex items-start gap-4">
              <div className="p-3 bg-blue-50 text-blue-600 rounded-xl"><ShieldCheck className="w-5 h-5" /></div>
              <div>
                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Indexed Ratio</p>
                <h3 className="text-lg font-black text-slate-900 mt-0.5">{documents.length ? Math.round((readyCount / documents.length) * 100) : 0}%</h3>
                <span className="text-[10px] font-semibold text-emerald-600 flex items-center gap-0.5 mt-1"><TrendingUp className="w-3 h-3" /> searchable</span>
              </div>
            </div>
          </div>

          {/* SPLIT */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* AI Prompt Assistant */}
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 bg-indigo-50 text-indigo-600 rounded-lg flex items-center justify-center"><MessageSquare className="w-4 h-4" /></div>
                  <h4 className="text-xs font-bold text-slate-900">AI Prompt Assistant Panel</h4>
                </div>
                <form onSubmit={handleAsk} className="relative">
                  <input
                    type="text"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Ask: Why did Pump P101 fail? / Summarize incidents for Boiler B201…"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-4 pr-12 py-3 text-xs text-slate-800 focus:outline-none focus:bg-white"
                  />
                  <button type="submit" disabled={asking} className="absolute right-2 top-2 w-8 h-8 flex items-center justify-center bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white rounded-lg">
                    {asking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  </button>
                </form>
                {answer && (
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                    <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">{answer.answer}</p>
                    {answer.sources?.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {[...new Set(answer.sources.map((s) => s.file_name))].map((name, i) => (
                          <span key={i} className="flex items-center gap-1 bg-white border border-slate-200 px-2 py-1 rounded text-[10px] font-mono text-slate-500"><FileText className="w-3 h-3" /> {name}</span>
                        ))}
                      </div>
                    )}
                    <div className="text-[10px] text-slate-400">Confidence: {Math.round((answer.confidence_score || 0) * 100)}%</div>
                  </div>
                )}
              </div>

              {/* Recent Document Ingestion Feed */}
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-900">Recent Document Ingestion Feed</h4>
                  <span className="text-[10px] text-slate-400">{documents.length} total</span>
                </div>
                <div className="space-y-2 text-xs max-h-72 overflow-y-auto">
                  {documents.length === 0 && (
                    <p className="text-slate-400 py-4 text-center">No documents yet — upload one to populate the knowledge base.</p>
                  )}
                  {documents.slice(0, 12).map((doc) => (
                    <div key={doc.id} className="flex items-center gap-2 py-1.5 border-b border-slate-100 last:border-0 group">
                      <span className={`p-1 rounded font-mono text-[9px] font-bold uppercase ${TYPE_BADGE[doc.file_type] || 'bg-slate-100 text-slate-500'}`}>{doc.file_type}</span>
                      <span className="truncate font-medium text-slate-700 flex-1">{doc.file_name}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-semibold ${STATUS_BADGE[doc.status] || 'bg-slate-100 text-slate-500'}`}>{doc.status}</span>
                      <button onClick={() => handleDelete(doc.id)} className="text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
                <h4 className="text-xs font-bold text-slate-900">Pipeline Status</h4>
                <div className="space-y-2 text-xs">
                  {documents.filter((d) => d.status === 'failed').length === 0 ? (
                    <div className="bg-emerald-50/60 border border-emerald-100 p-2.5 rounded-lg flex gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                      <div>
                        <p className="font-bold text-slate-800 leading-none">All documents healthy</p>
                        <p className="text-[10px] text-slate-500 mt-1">No failed ingestions</p>
                      </div>
                    </div>
                  ) : (
                    documents.filter((d) => d.status === 'failed').map((d) => (
                      <div key={d.id} className="bg-red-50/60 border border-red-100 p-2.5 rounded-lg flex gap-2">
                        <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
                        <div>
                          <p className="font-bold text-slate-800 leading-none truncate">{d.file_name}</p>
                          <p className="text-[10px] text-slate-500 mt-1">{d.error || 'Ingestion failed'}</p>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </main>

        <footer className="bg-white border-t border-slate-200 p-4 text-[11px] text-slate-500 font-medium flex justify-between items-center px-8 flex-shrink-0">
          <div className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-500" /> Knowledge base: <span className="text-slate-800 font-bold">{readyCount} indexed</span></div>
          <div>Documents tracked: <span className="text-slate-800 font-bold">{documents.length}</span></div>
        </footer>
      </div>
    </div>
  );
}
