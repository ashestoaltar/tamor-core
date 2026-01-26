import React, { useState, useEffect } from 'react';
import { applyUpdate } from '../../pwa/registerSW';
import './UpdateNotification.css';

function UpdateNotification() {
  const [updateAvailable, setUpdateAvailable] = useState(false);

  useEffect(() => {
    const handleUpdate = () => {
      setUpdateAvailable(true);
    };

    window.addEventListener('tamor-update-available', handleUpdate);

    return () => {
      window.removeEventListener('tamor-update-available', handleUpdate);
    };
  }, []);

  if (!updateAvailable) {
    return null;
  }

  const handleUpdate = () => {
    applyUpdate();
  };

  const handleDismiss = () => {
    setUpdateAvailable(false);
  };

  return (
    <div className="update-notification">
      <div className="update-content">
        <span className="update-icon">✨</span>
        <span className="update-message">Update available</span>
      </div>
      <div className="update-actions">
        <button className="update-btn primary" onClick={handleUpdate}>
          Update Now
        </button>
        <button className="update-btn secondary" onClick={handleDismiss}>
          Later
        </button>
      </div>
    </div>
  );
}

export default UpdateNotification;
