import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../api/client';
import { User } from '../types';

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('nexarag_token'));
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadUser() {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const currentUser = await api.auth.me();
        setUser(currentUser);
      } catch (err) {
        console.error('Failed to authenticate token:', err);
        localStorage.removeItem('nexarag_token');
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, [token]);

  const login = async (email: string, password: string) => {
    const data = await api.auth.login(email, password);
    localStorage.setItem('nexarag_token', data.access_token);
    setToken(data.access_token);
    const currentUser = await api.auth.me();
    setUser(currentUser);
  };

  const register = async (email: string, password: string) => {
    await api.auth.register(email, password);
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem('nexarag_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
