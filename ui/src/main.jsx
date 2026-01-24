import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { AuthProvider } from "./context/AuthContext.jsx"
import { DevModeProvider } from "./context/DevModeContext.jsx"
import { VoiceSettingsProvider } from "./context/VoiceSettingsContext.jsx"

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <DevModeProvider>
        <VoiceSettingsProvider>
          <App />
        </VoiceSettingsProvider>
      </DevModeProvider>
    </AuthProvider>
  </StrictMode>,
)
