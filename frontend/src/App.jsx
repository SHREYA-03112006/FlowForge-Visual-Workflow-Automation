import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import EditorPage from './pages/EditorPage.jsx';
import WorkflowListPage from './pages/WorkflowListPage.jsx';
import RunHistoryPage from './pages/RunHistoryPage.jsx';
import Toast from './components/common/Toast.jsx';
import Logo from './components/common/Logo.jsx';

function Shell({ children }) {
  return (
    <div className="shell">
      <header className="shell-bar">
        <NavLink to="/" className="brand"><Logo /> Flowforge</NavLink>
        <nav>
          <NavLink to="/" end>Workflows</NavLink>
          <NavLink to="/runs">Run history</NavLink>
        </nav>
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Shell><WorkflowListPage /></Shell>} />
        <Route path="/runs" element={<Shell><RunHistoryPage /></Shell>} />
        <Route path="/editor/:id?" element={<EditorPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toast />
    </>
  );
}
