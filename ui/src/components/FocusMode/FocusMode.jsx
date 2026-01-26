import React, { useState, useRef, useEffect } from 'react';
import { useFocusMode } from '../../contexts/FocusModeContext';
import { useVoiceInput } from '../../hooks/useVoiceInput';
import { useVoiceOutput } from '../../hooks/useVoiceOutput';
import './FocusMode.css';

function FocusMode({ projectName, onSendMessage, messages }) {
  const { exitFocusMode, focusSettings } = useFocusMode();
  const [inputText, setInputText] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const inputRef = useRef(null);

  const {
    isListening,
    transcript,
    startListening,
    stopListening,
    isSupported: voiceInputSupported
  } = useVoiceInput();

  const { speak, isSupported: voiceOutputSupported } = useVoiceOutput();

  // Update input with voice transcript
  useEffect(() => {
    if (transcript) {
      setInputText(transcript);
    }
  }, [transcript]);

  // Get last assistant message for display
  const lastAssistantMessage = messages
    ?.filter(m => m.role === 'assistant')
    .slice(-1)[0];

  const handleSubmit = async () => {
    if (!inputText.trim()) return;

    setIsThinking(true);
    await onSendMessage(inputText);
    setInputText('');
    setIsThinking(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleMicClick = () => {
    if (isListening) {
      stopListening();
      // Auto-submit after voice input
      if (transcript.trim()) {
        setTimeout(() => handleSubmit(), 300);
      }
    } else {
      startListening();
    }
  };

  return (
    <div className="focus-mode">
      {/* Minimal header */}
      <header className="focus-header">
        {focusSettings.showProjectIndicator && projectName && (
          <span className="focus-project">{projectName}</span>
        )}
        <button
          className="focus-exit-btn"
          onClick={exitFocusMode}
          title="Exit Focus Mode (Esc)"
        >
          ×
        </button>
      </header>

      {/* Response area */}
      <div className="focus-response-area">
        {isThinking ? (
          <div className="focus-thinking">
            <div className="thinking-dots">
              <span></span><span></span><span></span>
            </div>
            <p>Thinking...</p>
          </div>
        ) : lastAssistantMessage ? (
          <div className="focus-response">
            <p>{lastAssistantMessage.content}</p>
            {voiceOutputSupported && (
              <button
                className="focus-read-btn"
                onClick={() => speak(lastAssistantMessage.content)}
                title="Read aloud"
              >
                🔊
              </button>
            )}
          </div>
        ) : (
          <div className="focus-welcome">
            <h2>Ready</h2>
            <p>Speak or type your question</p>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="focus-input-area">
        {focusSettings.voiceFirst && voiceInputSupported ? (
          <>
            <button
              className={`focus-mic-btn ${isListening ? 'listening' : ''}`}
              onClick={handleMicClick}
            >
              <span className="mic-icon">🎤</span>
              {isListening && <span className="mic-pulse"></span>}
            </button>

            {isListening && transcript && (
              <div className="focus-transcript">{transcript}</div>
            )}

            <div className="focus-text-fallback">
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Or type here..."
                className="focus-text-input"
              />
              <button
                className="focus-send-btn"
                onClick={handleSubmit}
                disabled={!inputText.trim()}
              >
                →
              </button>
            </div>
          </>
        ) : (
          <div className="focus-text-primary">
            <input
              ref={inputRef}
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything..."
              className="focus-text-input"
              autoFocus
            />
            <button
              className="focus-send-btn"
              onClick={handleSubmit}
              disabled={!inputText.trim()}
            >
              →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default FocusMode;
