import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useFocusMode } from '../../contexts/FocusModeContext';
import { useVoiceInput } from '../../hooks/useVoiceInput';
import { useVoiceOutput } from '../../hooks/useVoiceOutput';
import { apiFetch } from '../../api/client';
import './FocusMode.css';

function FocusMode({
  projectName,
  activeConversationId,
  currentProjectId,
  activeMode = 'Auto',
  onConversationCreated
}) {
  const { exitFocusMode, focusSettings } = useFocusMode();
  const [inputText, setInputText] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(activeConversationId);
  const inputRef = useRef(null);

  const {
    isListening,
    transcript,
    startListening,
    stopListening,
    isSupported: voiceInputSupported
  } = useVoiceInput();

  const { speak, isSpeaking, stop: stopSpeaking, isSupported: voiceOutputSupported } = useVoiceOutput();

  // Load existing conversation messages if we have an active conversation
  useEffect(() => {
    if (!activeConversationId) {
      setMessages([]);
      return;
    }

    const loadMessages = async () => {
      try {
        const data = await apiFetch(`/conversations/${activeConversationId}/messages`);
        if (data?.messages) {
          setMessages(data.messages);
        }
      } catch (err) {
        console.error('Failed to load messages:', err);
      }
    };

    loadMessages();
  }, [activeConversationId]);

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

  const handleSubmit = useCallback(async () => {
    const trimmed = inputText.trim();
    if (!trimmed || isThinking) return;

    setIsThinking(true);
    setInputText('');

    // Add user message locally
    const userMsg = { role: 'user', content: trimmed, _local: true };
    setMessages(prev => [...prev, userMsg]);

    try {
      const data = await apiFetch('/chat', {
        method: 'POST',
        body: {
          message: trimmed,
          mode: activeMode,
          conversation_id: conversationId,
          project_id: currentProjectId,
          tz_name: Intl.DateTimeFormat().resolvedOptions().timeZone,
          tz_offset_minutes: new Date().getTimezoneOffset(),
        },
      });

      const reply = data?.reply ?? data?.tamor ?? data?.reply_text ?? '';
      const newConvId = data?.conversation_id;

      // Update conversation ID if new
      if (newConvId && newConvId !== conversationId) {
        setConversationId(newConvId);
        onConversationCreated?.(newConvId);
      }

      // Add assistant response
      const assistantMsg = { role: 'assistant', content: reply };
      setMessages(prev => [...prev, assistantMsg]);

      // Auto-read response if enabled
      if (focusSettings.voiceFirst && voiceOutputSupported) {
        speak(reply);
      }
    } catch (err) {
      console.error('Focus mode send failed:', err);
      const errorMsg = { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsThinking(false);
    }
  }, [inputText, isThinking, activeMode, conversationId, currentProjectId, onConversationCreated, focusSettings.voiceFirst, voiceOutputSupported, speak]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleMicClick = () => {
    if (isListening) {
      stopListening();
      // Auto-submit after voice input stops
      setTimeout(() => {
        if (inputText.trim()) {
          handleSubmit();
        }
      }, 300);
    } else {
      startListening();
    }
  };

  const handleReadClick = () => {
    if (isSpeaking) {
      stopSpeaking();
    } else if (lastAssistantMessage?.content) {
      speak(lastAssistantMessage.content);
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
                className={`focus-read-btn ${isSpeaking ? 'speaking' : ''}`}
                onClick={handleReadClick}
                title={isSpeaking ? 'Stop reading' : 'Read aloud'}
              >
                {isSpeaking ? '⏹️' : '🔊'}
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
              disabled={isThinking}
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
                disabled={isThinking}
              />
              <button
                className="focus-send-btn"
                onClick={handleSubmit}
                disabled={!inputText.trim() || isThinking}
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
              disabled={isThinking}
            />
            <button
              className="focus-send-btn"
              onClick={handleSubmit}
              disabled={!inputText.trim() || isThinking}
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
