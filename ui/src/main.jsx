import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { AuthProvider } from "./context/AuthContext.jsx"
import { DevModeProvider } from "./context/DevModeContext.jsx"

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <DevModeProvider>
        <App />
      </DevModeProvider>
    </AuthProvider>
  </StrictMode>,
)
