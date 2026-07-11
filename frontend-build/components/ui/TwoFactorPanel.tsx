'use client';

import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  QrCode,
  Key,
  Copy,
  Download,
  Check,
  RefreshCw,
  AlertTriangle,
  Lock,
} from 'lucide-react';
import { api, TotpSetupResponse } from '../../lib/api';

interface TwoFactorPanelProps {
  initialEnabled?: boolean;
  onStatusChange?: (enabled: boolean) => void;
  compact?: boolean;
}

export default function TwoFactorPanel({
  initialEnabled = false,
  onStatusChange,
  compact = false,
}: TwoFactorPanelProps) {
  const [enabled, setEnabled] = useState<boolean>(initialEnabled);
  const [loading, setLoading] = useState<boolean>(false);
  const [setupData, setSetupData] = useState<TotpSetupResponse | null>(null);
  const [verificationCode, setVerificationCode] = useState<string>('');
  const [disableCode, setDisableCode] = useState<string>('');
  const [regenCode, setRegenCode] = useState<string>('');
  const [newBackupCodes, setNewBackupCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [copiedSecret, setCopiedSecret] = useState<boolean>(false);
  const [copiedBackups, setCopiedBackups] = useState<boolean>(false);
  const [showDisableModal, setShowDisableModal] = useState<boolean>(false);
  const [showRegenModal, setShowRegenModal] = useState<boolean>(false);

  useEffect(() => {
    // Check initial 2FA status from server
    const fetchStatus = async () => {
      try {
        const res = await api.get2FaStatus();
        setEnabled(res.enabled);
        onStatusChange?.(res.enabled);
      } catch {
        // Fall back to prop if unauthenticated or error
      }
    };
    fetchStatus();
  }, [onStatusChange]);

  const handleStartSetup = async () => {
    setError(null);
    setSuccessMsg(null);
    setLoading(true);
    try {
      const res = await api.setup2Fa();
      setSetupData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to initialize 2FA setup');
    } finally {
      setLoading(false);
    }
  };

  const handleEnable2Fa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    if (!verificationCode || verificationCode.length < 6) {
      setError('Please enter a valid 6-digit code');
      return;
    }

    setLoading(true);
    try {
      await api.enable2Fa(verificationCode.trim());
      setEnabled(true);
      setSetupData(null);
      setVerificationCode('');
      setSuccessMsg('Two-Factor Authentication is now active!');
      onStatusChange?.(true);
    } catch (err: any) {
      setError(err.message || 'Invalid verification code. Please check your authenticator clock.');
    } finally {
      setLoading(false);
    }
  };

  const handleDisable2Fa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    if (!disableCode) {
      setError('Please enter your 6-digit TOTP or a backup code to disable 2FA');
      return;
    }

    setLoading(true);
    try {
      await api.disable2Fa(disableCode.trim());
      setEnabled(false);
      setShowDisableModal(false);
      setDisableCode('');
      setSuccessMsg('Two-Factor Authentication has been disabled.');
      onStatusChange?.(false);
    } catch (err: any) {
      setError(err.message || 'Invalid verification or backup code');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateBackups = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    if (!regenCode || regenCode.length < 6) {
      setError('Please enter your 6-digit TOTP code');
      return;
    }

    setLoading(true);
    try {
      const res = await api.regenerate2FaBackups(regenCode.trim());
      setNewBackupCodes(res.backup_codes);
      setRegenCode('');
      setSuccessMsg('New backup codes generated successfully.');
    } catch (err: any) {
      setError(err.message || 'Invalid verification code');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, type: 'secret' | 'backups') => {
    navigator.clipboard.writeText(text);
    if (type === 'secret') {
      setCopiedSecret(true);
      setTimeout(() => setCopiedSecret(false), 2000);
    } else {
      setCopiedBackups(true);
      setTimeout(() => setCopiedBackups(false), 2000);
    }
  };

  const downloadBackupCodes = (codes: string[]) => {
    const text = [
      'Stealthy Two-Factor Authentication Backup Codes',
      '==================================================',
      'Store these codes in a safe, offline location.',
      'Each code can only be used ONCE.',
      '',
      ...codes.map((code, idx) => `${idx + 1}. ${code}`),
    ].join('\n');

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'stealthy-backup-codes.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`border border-white/10 rounded-2xl bg-white/[0.03] backdrop-blur-xl ${compact ? 'p-5' : 'p-6'}`}>
      {/* Header */}
      <div className="flex items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div
            className={`p-2.5 rounded-xl border ${
              enabled
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
            }`}
          >
            {enabled ? <ShieldCheck className="w-6 h-6" /> : <ShieldAlert className="w-6 h-6" />}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Two-Factor Authentication (2FA)</h3>
            <p className="text-sm text-neutral-400">
              {enabled
                ? 'Your account is secured with time-based OTP codes.'
                : 'Protect your account with an authenticator app (Google Authenticator, Authy, 1Password).'}
            </p>
          </div>
        </div>
        <span
          className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${
            enabled
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-neutral-800 border-neutral-700 text-neutral-400'
          }`}
        >
          {enabled ? 'Enabled' : 'Disabled'}
        </span>
      </div>

      {/* Alerts */}
      {error && (
        <div className="mb-4 p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center gap-3 text-sm text-red-300">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="mb-4 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-3 text-sm text-emerald-300">
          <Check className="w-5 h-5 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* DISABLED STATE — INITIAL */}
      {!enabled && !setupData && (
        <div className="space-y-4">
          <button
            onClick={handleStartSetup}
            disabled={loading}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition-all disabled:opacity-50"
          >
            {loading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <QrCode className="w-4 h-4" />
            )}
            Start 2FA Setup
          </button>
        </div>
      )}

      {/* SETUP IN PROGRESS */}
      {!enabled && setupData && (
        <div className="space-y-6 pt-2 border-t border-white/10">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Step 1: QR Code & Secret */}
            <div className="space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
                Step 1 — Scan QR Code
              </span>
              <div className="p-4 rounded-xl bg-white inline-block border border-white/20">
                <img
                  src={setupData.qr_data_uri}
                  alt="2FA QR Code"
                  className="w-44 h-44 object-contain"
                />
              </div>
              <p className="text-xs text-neutral-400">
                Can&apos;t scan? Enter this key into your app manually:
              </p>
              <div className="flex items-center gap-2 bg-neutral-900/80 border border-white/10 rounded-lg p-2 font-mono text-xs text-neutral-200">
                <span className="flex-1 truncate">{setupData.secret}</span>
                <button
                  type="button"
                  onClick={() => copyToClipboard(setupData.secret, 'secret')}
                  className="p-1 hover:bg-white/10 rounded text-neutral-400 hover:text-white transition-colors"
                >
                  {copiedSecret ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Step 2: Backup Codes */}
            <div className="space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
                Step 2 — Save Backup Codes
              </span>
              <p className="text-xs text-neutral-300">
                Save these 10 one-time recovery codes securely. Each code can be used once if you lose your device.
              </p>
              <div className="grid grid-cols-2 gap-1.5 p-3 rounded-xl bg-neutral-900/80 border border-white/10 font-mono text-xs text-neutral-300">
                {setupData.backup_codes.map((code, idx) => (
                  <div key={idx} className="px-2 py-1 bg-white/5 rounded">
                    {code}
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => copyToClipboard(setupData.backup_codes.join('\n'), 'backups')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-xs text-white transition-colors"
                >
                  {copiedBackups ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  Copy Codes
                </button>
                <button
                  type="button"
                  onClick={() => downloadBackupCodes(setupData.backup_codes)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-xs text-white transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download .txt
                </button>
              </div>
            </div>
          </div>

          {/* Step 3: Verify Code */}
          <form onSubmit={handleEnable2Fa} className="pt-4 border-t border-white/10 space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-neutral-300 mb-2">
                Step 3 — Enter 6-Digit Verification Code
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  placeholder="000000"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
                  className="w-40 px-4 py-2.5 rounded-xl bg-neutral-900 border border-white/20 text-white font-mono text-center tracking-widest text-lg focus:outline-none focus:border-blue-500"
                />
                <button
                  type="submit"
                  disabled={loading || verificationCode.length < 6}
                  className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-all disabled:opacity-50"
                >
                  {loading ? 'Verifying...' : 'Enable 2FA'}
                </button>
                <button
                  type="button"
                  onClick={() => setSetupData(null)}
                  className="px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-neutral-300 text-sm transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* ENABLED STATE */}
      {enabled && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => {
                setShowRegenModal(true);
                setShowDisableModal(false);
                setError(null);
                setSuccessMsg(null);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white font-medium text-sm transition-colors"
            >
              <Key className="w-4 h-4" />
              Regenerate Backup Codes
            </button>
            <button
              onClick={() => {
                setShowDisableModal(true);
                setShowRegenModal(false);
                setError(null);
                setSuccessMsg(null);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-300 font-medium text-sm transition-colors"
            >
              <Lock className="w-4 h-4" />
              Disable 2FA
            </button>
          </div>

          {/* Regenerate Backups Modal/Panel */}
          {showRegenModal && (
            <div className="p-4 rounded-xl bg-neutral-900/80 border border-white/10 space-y-4">
              <h4 className="text-sm font-semibold text-white">Regenerate Backup Codes</h4>
              <p className="text-xs text-neutral-400">
                Generating new backup codes will immediately invalidate your previous 10 codes. Please enter your authenticator code to confirm.
              </p>
              <form onSubmit={handleRegenerateBackups} className="flex items-center gap-3">
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="000000"
                  value={regenCode}
                  onChange={(e) => setRegenCode(e.target.value.replace(/\D/g, ''))}
                  className="w-36 px-3 py-2 rounded-lg bg-neutral-800 border border-white/20 text-white font-mono text-center tracking-widest focus:outline-none focus:border-blue-500"
                />
                <button
                  type="submit"
                  disabled={loading || regenCode.length < 6}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-all disabled:opacity-50"
                >
                  Generate New Codes
                </button>
                <button
                  type="button"
                  onClick={() => setShowRegenModal(false)}
                  className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-400 text-xs transition-colors"
                >
                  Cancel
                </button>
              </form>

              {newBackupCodes && (
                <div className="pt-3 border-t border-white/10 space-y-2">
                  <span className="text-xs font-semibold text-emerald-400">
                    New Backup Codes Created
                  </span>
                  <div className="grid grid-cols-2 gap-1.5 p-3 rounded-lg bg-black/40 font-mono text-xs text-neutral-300">
                    {newBackupCodes.map((code, idx) => (
                      <div key={idx}>{code}</div>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => downloadBackupCodes(newBackupCodes)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-xs text-white"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download Codes
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Disable 2FA Modal/Panel */}
          {showDisableModal && (
            <div className="p-4 rounded-xl bg-red-950/20 border border-red-500/20 space-y-4">
              <h4 className="text-sm font-semibold text-red-300">Confirm Disable Two-Factor Authentication</h4>
              <p className="text-xs text-neutral-400">
                Disabling 2FA reduces your account security. Enter a 6-digit authenticator code or an unused backup code to confirm.
              </p>
              <form onSubmit={handleDisable2Fa} className="flex items-center gap-3">
                <input
                  type="text"
                  placeholder="6-digit or backup code"
                  value={disableCode}
                  onChange={(e) => setDisableCode(e.target.value)}
                  className="flex-1 max-w-xs px-3 py-2 rounded-lg bg-neutral-900 border border-red-500/30 text-white font-mono text-sm focus:outline-none focus:border-red-500"
                />
                <button
                  type="submit"
                  disabled={loading || !disableCode}
                  className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold transition-all disabled:opacity-50"
                >
                  Confirm Disable
                </button>
                <button
                  type="button"
                  onClick={() => setShowDisableModal(false)}
                  className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-400 text-xs transition-colors"
                >
                  Cancel
                </button>
              </form>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
