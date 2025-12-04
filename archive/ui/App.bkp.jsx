import "./styles/dark.css";
import { useState } from "react";

import LeftPanel from "./components/LeftPanel/LeftPanel";
import ChatPanel from "./components/ChatPanel/ChatPanel";
import RightPanel from "./components/RightPanel/RightPanel";

function App() {
  const [lastMemoryMatches, setLastMemoryMatches] = useState([]);
  const [memoryRefreshToken, setMemoryRefreshToken] = useState(0);
  const [activeMode, setActiveMode] = useState("Scholar");

  return (
    <div className="app-container">
      <div className="left-panel">
        <LeftPanel
          refreshToken={memoryRefreshToken}
          activeMode={activeMode}
          setActiveMode={setActiveMode}
        />
      </div>

      <div className="chat-panel-wrapper">
        <ChatPanel
          setLastMemoryMatches={setLastMemoryMatches}
          setMemoryRefreshToken={setMemoryRefreshToken}
          activeMode={activeMode}
        />
      </div>

      <div className="right-panel">
        <RightPanel
          lastMemoryMatches={lastMemoryMatches}
          activeMode={activeMode}
        />
      </div>
    </div>
  );
}

export default App;

