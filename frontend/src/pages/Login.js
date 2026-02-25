import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const { login, user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Already logged in -> redirect
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-fg-navy via-fg-dark to-fg-navy">
        <div className="animate-spin w-8 h-8 border-2 border-fg-teal border-t-transparent rounded-full" />
      </div>
    );
  }
  if (user) return <Navigate to="/" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await login(email, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-fg-navy via-fg-dark to-fg-navy p-4">
      <div className="w-full max-w-md animate-slide-up">
        {/* Logo + branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-1 mb-3">
            <span className="text-4xl font-black text-fg-teal tracking-tight">QA</span>
            <span className="text-4xl font-black text-white tracking-tight">Forge</span>
          </div>
          <p className="text-gray-400 text-sm tracking-wide">
            Where Quality Is Engineered
          </p>
        </div>

        {/* Login card */}
        <div className="card-static overflow-hidden">
          {/* Gradient accent */}
          <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />

          <div className="p-8">
            <h2 className="text-xl font-bold text-fg-navy mb-1">Welcome back</h2>
            <p className="text-sm text-fg-mid mb-6">Sign in to your account</p>

            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 animate-fade-in">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label" htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@freshgravity.com"
                  className="input-field"
                  autoComplete="email"
                  autoFocus
                />
              </div>

              <div>
                <label className="label" htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="input-field"
                  autoComplete="current-password"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-lg font-semibold text-sm text-white
                  bg-gradient-to-r from-fg-teal to-fg-green
                  hover:from-fg-tealDark hover:to-fg-green
                  focus:ring-2 focus:ring-fg-teal focus:ring-offset-2
                  disabled:opacity-50 disabled:cursor-not-allowed
                  transition-all duration-150 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Signing in...
                  </>
                ) : (
                  'Sign In'
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-gray-500 mt-6">
          FreshGravity &middot; QAForge v0.1
        </p>
      </div>
    </div>
  );
}
