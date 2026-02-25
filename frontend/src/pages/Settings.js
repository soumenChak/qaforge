import React, { useState, useEffect } from 'react';
import { settingsAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';

const PROVIDER_ICONS = {
  anthropic: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
    </svg>
  ),
  openai: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Z" />
    </svg>
  ),
  groq: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  ),
  ollama: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 0 1-3-3m3 3a3 3 0 1 0 0 6h13.5a3 3 0 1 0 0-6m-16.5-3a3 3 0 0 1 3-3h13.5a3 3 0 0 1 3 3m-19.5 0a4.5 4.5 0 0 1 .9-2.7L5.737 5.1a3.375 3.375 0 0 1 2.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 0 1 .9 2.7m0 0a3 3 0 0 1-3 3m0 3h.008v.008h-.008v-.008Zm0-6h.008v.008h-.008v-.008Zm-3 6h.008v.008h-.008v-.008Zm0-6h.008v.008h-.008v-.008Z" />
    </svg>
  ),
  mock: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="none" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437 1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008Z" />
    </svg>
  ),
};

const ENV_KEYS = {
  anthropic: 'ANTHROPIC_API_KEY',
  openai: 'OPENAI_API_KEY',
  groq: 'GROQ_API_KEY',
  ollama: 'OLLAMA_BASE_URL',
  mock: '(none required)',
};

export default function Settings() {
  const { isAdmin } = useAuth();
  const [providers, setProviders] = useState({});
  const [currentSettings, setCurrentSettings] = useState({ provider: '', model: '' });
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const [settingsRes, providersRes] = await Promise.all([
          settingsAPI.getLLM(),
          settingsAPI.getProviders(),
        ]);
        setCurrentSettings(settingsRes.data);
        setProviders(providersRes.data);
        setSelectedProvider(settingsRes.data.provider);
        setSelectedModel(settingsRes.data.model);
      } catch (err) {
        console.error('Failed to load settings:', err);
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, []);

  const handleSelectProvider = (key) => {
    setSelectedProvider(key);
    const prov = providers[key];
    if (prov?.models?.length > 0) {
      setSelectedModel(prov.models[0]);
    }
  };

  const handleSave = async () => {
    if (!isAdmin) return;
    setSaving(true);
    setMessage({ type: '', text: '' });
    try {
      const res = await settingsAPI.updateLLM({
        provider: selectedProvider,
        model: selectedModel,
      });
      setCurrentSettings(res.data);
      setMessage({ type: 'success', text: 'LLM settings updated successfully.' });
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to update settings.' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="flex items-center justify-center py-20">
          <svg className="animate-spin w-8 h-8 text-fg-teal" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-fg-navy">Settings</h1>
        <p className="text-sm text-fg-mid mt-1">Configure the LLM provider for test case generation</p>
      </div>

      {/* Messages */}
      {message.text && (
        <div className={`mb-6 p-3 rounded-lg text-sm animate-fade-in ${
          message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' :
          'bg-red-50 border border-red-200 text-red-700'
        }`}>
          {message.text}
        </div>
      )}

      {/* Current config */}
      <div className="card-static p-5 mb-6">
        <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-3">Current Configuration</h3>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-fg-mid">Provider:</span>
          <span className="font-medium text-fg-dark capitalize">{currentSettings.provider}</span>
          <span className="text-fg-mid ml-2">Model:</span>
          <span className="font-medium text-fg-dark">{currentSettings.model}</span>
        </div>
      </div>

      {/* Provider cards */}
      <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-4">LLM Providers</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {Object.entries(providers).map(([key, prov]) => {
          const isSelected = selectedProvider === key;
          const isConfigured = prov.configured;

          return (
            <button
              key={key}
              onClick={() => handleSelectProvider(key)}
              disabled={!isAdmin}
              className={`card-static p-5 text-left transition-all duration-150
                ${isSelected
                  ? 'ring-2 ring-fg-teal bg-fg-tealLight/30'
                  : 'hover:shadow-card-hover'
                }
                ${!isAdmin ? 'cursor-default' : 'cursor-pointer'}
              `}
            >
              <div className="flex items-start justify-between mb-3">
                <div className={`${isSelected ? 'text-fg-teal' : 'text-fg-mid'}`}>
                  {PROVIDER_ICONS[key] || PROVIDER_ICONS.mock}
                </div>
                {isConfigured ? (
                  <CheckCircleIcon className="w-5 h-5 text-green-500 flex-shrink-0" />
                ) : (
                  <XCircleIcon className="w-5 h-5 text-gray-300 flex-shrink-0" />
                )}
              </div>

              <h4 className="text-sm font-bold text-fg-navy mb-1">{prov.name}</h4>

              <p className={`text-xs mb-2 ${isConfigured ? 'text-green-600' : 'text-fg-mid'}`}>
                {isConfigured ? 'Configured' : 'Not configured'}
              </p>

              {/* Models */}
              <div className="space-y-1">
                {prov.models?.map((model) => (
                  <div key={model} className="text-xs text-fg-mid">
                    {model}
                  </div>
                ))}
              </div>

              <p className="text-xxs text-gray-400 mt-2 font-mono">
                {ENV_KEYS[key] || ''}
              </p>
            </button>
          );
        })}
      </div>

      {/* Model selection for chosen provider */}
      {selectedProvider && providers[selectedProvider] && (
        <div className="card-static p-5 mb-6 animate-fade-in">
          <h3 className="text-sm font-bold text-fg-navy mb-3">
            Select Model for {providers[selectedProvider].name}
          </h3>
          <div className="flex flex-wrap gap-3">
            {providers[selectedProvider].models?.map((model) => (
              <button
                key={model}
                onClick={() => setSelectedModel(model)}
                disabled={!isAdmin}
                className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all
                  ${selectedModel === model
                    ? 'border-fg-teal bg-fg-tealLight text-fg-tealDark'
                    : 'border-gray-200 text-fg-mid hover:border-gray-300'
                  }
                  ${!isAdmin ? 'cursor-default' : ''}`}
              >
                {model}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Save */}
      {isAdmin && (
        <div className="flex justify-end">
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      )}

      {/* Platform info */}
      <div className="mt-10 card-static p-5">
        <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-3">Platform Info</h3>
        <div className="grid grid-cols-2 gap-y-2 text-sm">
          <span className="text-fg-mid">Platform</span>
          <span className="text-fg-dark">QAForge v0.1</span>
          <span className="text-fg-mid">Company</span>
          <span className="text-fg-dark">FreshGravity</span>
          <span className="text-fg-mid">Architecture</span>
          <span className="text-fg-dark">FastAPI + React + PostgreSQL</span>
        </div>
      </div>
    </div>
  );
}
