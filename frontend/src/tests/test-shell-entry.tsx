import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { AppShell } from '../components/layout/AppShell';
import { api } from '../api/client';
import '../index.css';

// Mark welcome tour as seen
try {
  localStorage.setItem('clubdocs.tour.v1.1', 'done');
  localStorage.setItem('clubdocs.tour.v1.anon', 'done');
} catch {}

// Mock API responses for test harness
(api.auth as any).me = async () => ({
  id: '1',
  email: 'test@svnit.ac.in',
  name: 'Test Administrator',
  is_platform_admin: false,
});

(api.clubs as any).list = async () => [
  {
    id: 1,
    name: 'Robotics Club',
    short_name: 'RoboClub',
    my_role: 'admin',
  },
  {
    id: 2,
    name: 'Coding Club',
    short_name: 'CodingClub',
    my_role: 'member',
  },
];

(api.clubs as any).listJoinRequests = async () => [];

function TestRoot() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell>
          <div id="test-main-content" className="p-4" style={{ height: '3000px' }}>
            <h1 className="text-2xl font-bold mb-4">Milestone 1 Test Page</h1>
            <p className="text-slate-600">Simulated long scrollable content area for scroll lock tests.</p>
          </div>
        </AppShell>
      </AuthProvider>
    </BrowserRouter>
  );
}

const rootEl = document.getElementById('root');
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(<TestRoot />);
}
