// ui/src/hooks/useVoiceInput.js
// Speech-to-text hook using Web Speech API
import { useCallback, useEffect, useRef, useState } from "react";

// Get SpeechRecognition constructor (with vendor prefix for Safari)
const SpeechRecognition =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

/**
 * Hook for speech-to-text input using Web Speech API.
 *
 * @param {Object} options - Configuration options
 * @param {boolean} [options.continuous=false] - Keep listening or stop after pause
 * @param {boolean} [options.interimResults=true] - Show partial results while speaking
 * @param {string} [options.language='en-US'] - Recognition language
 *
 * @returns {Object} Voice input state and controls
 * @returns {boolean} isListening - Whether actively listening
 * @returns {string} transcript - Current/final transcript text
 * @returns {string|null} error - Error message if any
 * @returns {function} startListening - Start speech recognition
 * @returns {function} stopListening - Stop speech recognition
 * @returns {function} clearTranscript - Clear the transcript
 * @returns {boolean} isSupported - Whether speech recognition is supported
 */
export function useVoiceInput({
  continuous = false,
  interimResults = true,
  language = "en-US",
} = {}) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState(null);

  // Ref to hold the recognition instance
  const recognitionRef = useRef(null);

  // Track if we're mounted to avoid state updates after unmount
  const isMountedRef = useRef(true);

  const isSupported = Boolean(SpeechRecognition);

  // Initialize recognition instance
  const getRecognition = useCallback(() => {
    if (!SpeechRecognition) return null;

    if (!recognitionRef.current) {
      const recognition = new SpeechRecognition();
      recognition.continuous = continuous;
      recognition.interimResults = interimResults;
      recognition.lang = language;

      recognition.onstart = () => {
        if (isMountedRef.current) {
          setIsListening(true);
          setError(null);
        }
      };

      recognition.onresult = (event) => {
        if (!isMountedRef.current) return;

        let finalTranscript = "";
        let interimTranscript = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            finalTranscript += result[0].transcript;
          } else {
            interimTranscript += result[0].transcript;
          }
        }

        // For continuous mode, append to existing transcript
        // For non-continuous, replace with current result
        if (continuous) {
          setTranscript((prev) => {
            const base = finalTranscript ? prev + finalTranscript : prev;
            return interimTranscript ? base + interimTranscript : base;
          });
        } else {
          setTranscript(finalTranscript || interimTranscript);
        }
      };

      recognition.onerror = (event) => {
        if (!isMountedRef.current) return;

        // Map error codes to user-friendly messages
        const errorMessages = {
          "no-speech": "No speech detected. Please try again.",
          "audio-capture": "No microphone found. Please check your device.",
          "not-allowed": "Microphone access denied. Please enable permissions.",
          "network": "Network error occurred. Please check your connection.",
          "aborted": "Speech recognition was aborted.",
          "language-not-supported": "Language not supported.",
          "service-not-allowed": "Speech service not allowed.",
        };

        const message = errorMessages[event.error] || `Error: ${event.error}`;
        setError(message);
        setIsListening(false);
      };

      recognition.onend = () => {
        if (isMountedRef.current) {
          setIsListening(false);
        }
      };

      recognitionRef.current = recognition;
    }

    // Update settings if they changed
    recognitionRef.current.continuous = continuous;
    recognitionRef.current.interimResults = interimResults;
    recognitionRef.current.lang = language;

    return recognitionRef.current;
  }, [continuous, interimResults, language]);

  // Start listening
  const startListening = useCallback(() => {
    if (!isSupported) {
      setError("Speech recognition is not supported in this browser.");
      return;
    }

    const recognition = getRecognition();
    if (!recognition) return;

    // Clear previous transcript when starting fresh
    setTranscript("");
    setError(null);

    try {
      recognition.start();
    } catch (err) {
      // Handle "already started" error
      if (err.name === "InvalidStateError") {
        // Already listening, ignore
      } else {
        setError(err.message || "Failed to start speech recognition.");
      }
    }
  }, [isSupported, getRecognition]);

  // Stop listening
  const stopListening = useCallback(() => {
    const recognition = recognitionRef.current;
    if (recognition) {
      try {
        recognition.stop();
      } catch {
        // Ignore errors when stopping
      }
    }
    setIsListening(false);
  }, []);

  // Clear transcript
  const clearTranscript = useCallback(() => {
    setTranscript("");
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      const recognition = recognitionRef.current;
      if (recognition) {
        try {
          recognition.stop();
        } catch {
          // Ignore cleanup errors
        }
        recognitionRef.current = null;
      }
    };
  }, []);

  // Recreate recognition if settings change while not listening
  useEffect(() => {
    if (!isListening && recognitionRef.current) {
      recognitionRef.current = null;
    }
  }, [continuous, interimResults, language, isListening]);

  return {
    isListening,
    transcript,
    error,
    startListening,
    stopListening,
    clearTranscript,
    isSupported,
  };
}

export default useVoiceInput;
