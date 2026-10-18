import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, Club } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  clubs: Club[];
  activeClub: Club | null;
  setActiveClubId: (id: string | number) => void;
  login: (formData: URLSearchParams) => Promise<void>;
  logout: () => Promise<void>;
  refreshClubs: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [clubs, setClubs] = useState<Club[]>([]);
  const [activeClubId, setActiveClubIdState] = useState<string | number | null>(() => {
    const saved = localStorage.getItem('activeClubId');
    return saved ? saved : null;
  });
  const [loading, setLoading] = useState<boolean>(true);

  const fetchUserAndClubs = async () => {
    try {
      const u = await api.auth.me();
      setUser(u);
      const clubList = await api.clubs.list();
      setClubs(clubList);
      if (clubList.length > 0) {
        if (!activeClubId || !clubList.some(c => String(c.id) === String(activeClubId))) {
          setActiveClubIdState(clubList[0].id);
          localStorage.setItem('activeClubId', clubList[0].id.toString());
        }
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUserAndClubs();
  }, []);

  const setActiveClubId = (id: string | number) => {
    setActiveClubIdState(id);
    localStorage.setItem('activeClubId', id.toString());
  };

  const login = async (formData: URLSearchParams) => {
    await api.auth.login(formData);
    await fetchUserAndClubs();
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } finally {
      setUser(null);
      setClubs([]);
      setActiveClubIdState(null);
      localStorage.removeItem('activeClubId');
      localStorage.removeItem('csrf_token');
    }
  };

  const refreshClubs = async () => {
    const clubList = await api.clubs.list();
    setClubs(clubList);
  };

  const activeClub = clubs.find(c => String(c.id) === String(activeClubId)) || null;

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        clubs,
        activeClub,
        setActiveClubId,
        login,
        logout,
        refreshClubs,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
