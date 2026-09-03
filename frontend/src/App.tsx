import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import NewTest from "./pages/NewTest";
import SessionResults from "./pages/SessionResults";
import Compare from "./pages/Compare";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <header className="border-b border-slate-200 bg-white sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">
            <Link to="/" className="font-semibold tracking-tight flex items-center gap-2">
              <span className="w-6 h-6 rounded bg-slate-900 text-white grid place-items-center text-xs font-bold">
                UA
              </span>
              UX Autopsy
            </Link>
            <nav className="text-sm text-slate-600 flex gap-4 ml-auto">
              <Link to="/" className="hover:text-slate-900">Dashboard</Link>
              <Link to="/new" className="hover:text-slate-900">New Test</Link>
              <Link to="/compare" className="hover:text-slate-900">Compare</Link>
            </nav>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/new" element={<NewTest />} />
            <Route path="/sessions/:id" element={<SessionResults />} />
            <Route path="/compare" element={<Compare />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
