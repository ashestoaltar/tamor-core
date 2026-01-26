import React, { useState, useEffect } from 'react';
import { isInstalledPWA } from '../../pwa/registerSW';
import './InstallPrompt.css';

function InstallPrompt() {
  const [showPrompt, setShowPrompt] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    // Only show on mobile devices
    const isMobile = /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    if (!isMobile) {
      return;
    }

    // Don't show if already installed
    if (isInstalledPWA()) {
      return;
    }

    // Don't show if dismissed recently
    const dismissed = localStorage.getItem('tamor_install_dismissed');
    if (dismissed) {
      const dismissedAt = parseInt(dismissed, 10);
      const daysSince = (Date.now() - dismissedAt) / (1000 * 60 * 60 * 24);
      if (daysSince < 7) {
        return;
      }
    }

    // Detect iOS
    const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    setIsIOS(iOS);

    if (iOS) {
      // iOS doesn't support beforeinstallprompt, show manual instructions
      // Only show on iOS Safari
      const isSafari = /Safari/.test(navigator.userAgent) && !/Chrome/.test(navigator.userAgent);
      if (isSafari) {
        setTimeout(() => setShowPrompt(true), 3000);
      }
    } else {
      // Android/Desktop: listen for install prompt
      const handleBeforeInstall = (e) => {
        e.preventDefault();
        setDeferredPrompt(e);
        setTimeout(() => setShowPrompt(true), 3000);
      };

      window.addEventListener('beforeinstallprompt', handleBeforeInstall);

      return () => {
        window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      };
    }
  }, []);

  const handleInstall = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;

      if (outcome === 'accepted') {
        setShowPrompt(false);
      }

      setDeferredPrompt(null);
    }
  };

  const handleDismiss = () => {
    setShowPrompt(false);
    localStorage.setItem('tamor_install_dismissed', Date.now().toString());
  };

  if (!showPrompt) {
    return null;
  }

  return (
    <div className="install-prompt">
      <div className="install-content">
        <div className="install-icon">📱</div>
        <div className="install-text">
          <strong>Install Tamor</strong>
          {isIOS ? (
            <p>
              Tap <span className="ios-share">⬆️</span> then "Add to Home Screen"
            </p>
          ) : (
            <p>Add to your home screen for the best experience</p>
          )}
        </div>
      </div>

      <div className="install-actions">
        {!isIOS && (
          <button className="install-btn primary" onClick={handleInstall}>
            Install
          </button>
        )}
        <button className="install-btn secondary" onClick={handleDismiss}>
          {isIOS ? 'Got it' : 'Not now'}
        </button>
      </div>
    </div>
  );
}

export default InstallPrompt;
