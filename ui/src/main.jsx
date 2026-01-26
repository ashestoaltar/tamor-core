import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { AuthProvider } from "./context/AuthContext.jsx"
import { DevModeProvider } from "./context/DevModeContext.jsx"
import { VoiceSettingsProvider } from "./context/VoiceSettingsContext.jsx"
import { FocusModeProvider } from "./contexts/FocusModeContext.jsx"
import { registerServiceWorker } from './pwa/registerSW'

// Register service worker for PWA
registerServiceWorker();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <DevModeProvider>
        <VoiceSettingsProvider>
          <FocusModeProvider>
            <App />
          </FocusModeProvider>
        </VoiceSettingsProvider>
      </DevModeProvider>
    </AuthProvider>
  </StrictMode>,
)
