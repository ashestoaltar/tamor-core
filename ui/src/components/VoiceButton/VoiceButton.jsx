// ui/src/components/VoiceButton/VoiceButton.jsx
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useVoiceInput } from "../../hooks/useVoiceInput";
import "./VoiceButton.css";

/**
 * Microphone button for voice input in chat.
 *
 * @param {Object} props
 * @param {function} props.onTranscript - Called with final transcript text
 * @param {boolean} [props.disabled=false] - Disable the button
 * @param {string} [props.className] - Additional CSS classes
 */
export default function VoiceButton({ onTranscript, disabled = false, className = "" }) {
  const {
    isListening,
    transcript,
    error,
    startListening,
    stopListening,
    clearTranscript,
    isSupported,
  } = useVoiceInput({
    continuous: false,
    interimResults: true,
  });

  const [showError, setShowError] = useState(false);
  const errorTimeoutRef = useRef(null);
  const lastTranscriptRef = useRef("");

  // Track transcript changes while listening
  useEffect(() => {
    if (isListening && transcript) {
      lastTranscriptRef.current = transcript;
    }
  }, [isListening, transcript]);

  // When listening stops, deliver the transcript
  useEffect(() => {
    if (!isListening && lastTranscriptRef.current) {
      const finalText = lastTranscriptRef.current.trim();
      if (finalText && onTranscript) {
        onTranscript(finalText);
      }
      lastTranscriptRef.current = "";
      clearTranscript();
    }
  }, [isListening, onTranscript, clearTranscript]);

  // Show error briefly
  useEffect(() => {
    if (error) {
      setShowError(true);
      if (errorTimeoutRef.current) {
        clearTimeout(errorTimeoutRef.current);
      }
      errorTimeoutRef.current = setTimeout(() => {
        setShowError(false);
      }, 3000);
    }

    return () => {
      if (errorTimeoutRef.current) {
        clearTimeout(errorTimeoutRef.current);
      }
    };
  }, [error]);

  const handleClick = useCallback(() => {
    if (disabled) return;

    if (isListening) {
      stopListening();
    } else {
      lastTranscriptRef.current = "";
      startListening();
    }
  }, [disabled, isListening, startListening, stopListening]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleClick();
      }
    },
    [handleClick]
  );

  // Don't render if not supported
  if (!isSupported) {
    return null;
  }

  // Determine button state for styling
  const buttonState = showError ? "error" : isListening ? "listening" : "idle";

  // Determine aria-label based on state
  const ariaLabel = isListening
    ? "Stop voice input"
    : showError
    ? `Voice input error: ${error}`
    : "Start voice input";

  return (
    <div className={`voice-button-wrapper ${className}`}>
      <button
        type="button"
        className={`voice-button voice-button-${buttonState}`}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        aria-label={ariaLabel}
        title={showError ? error : isListening ? "Listening... tap to stop" : "Tap to speak"}
      >
        {/* Microphone icon */}
        <svg
          className="voice-button-icon"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>

        {/* Listening indicator ring */}
        {isListening && <span className="voice-button-ring" aria-hidden="true" />}
      </button>

      {/* Live transcript preview (optional visual feedback) */}
      {isListening && transcript && (
        <div className="voice-button-transcript" aria-live="polite">
          {transcript}
        </div>
      )}

      {/* Error tooltip */}
      {showError && error && (
        <div className="voice-button-error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
