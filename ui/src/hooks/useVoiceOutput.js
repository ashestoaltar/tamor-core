// ui/src/hooks/useVoiceOutput.js
// Text-to-speech hook using Web Speech API
import { useCallback, useEffect, useRef, useState } from "react";

// Storage keys for persisting preferences
const STORAGE_KEYS = {
  voice: "tamor_tts_voice",
  rate: "tamor_tts_rate",
};

// Check if speech synthesis is supported
const isSynthesisSupported =
  typeof window !== "undefined" && "speechSynthesis" in window;

/**
 * Hook for text-to-speech output using Web Speech API.
 *
 * @returns {Object} Voice output state and controls
 * @returns {function} speak - Speak the given text
 * @returns {function} stop - Stop current speech
 * @returns {function} pause - Pause current speech
 * @returns {function} resume - Resume paused speech
 * @returns {boolean} isSpeaking - Whether currently speaking
 * @returns {boolean} isPaused - Whether speech is paused
 * @returns {boolean} isSupported - Whether TTS is supported
 * @returns {Array} voices - Available voices
 * @returns {SpeechSynthesisVoice|null} selectedVoice - Currently selected voice
 * @returns {function} setSelectedVoice - Set the voice to use
 * @returns {number} rate - Speech rate (0.5 - 2)
 * @returns {function} setRate - Set the speech rate
 */
export function useVoiceOutput() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoiceState] = useState(null);
  const [rate, setRateState] = useState(() => {
    if (typeof window === "undefined") return 1;
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.rate);
      const parsed = parseFloat(stored);
      return !isNaN(parsed) && parsed >= 0.5 && parsed <= 2 ? parsed : 1;
    } catch {
      return 1;
    }
  });

  // Ref for current utterance
  const utteranceRef = useRef(null);

  // Track if mounted
  const isMountedRef = useRef(true);

  // Load voices (may be async on some browsers)
  const loadVoices = useCallback(() => {
    if (!isSynthesisSupported) return;

    const availableVoices = window.speechSynthesis.getVoices();
    if (availableVoices.length > 0 && isMountedRef.current) {
      setVoices(availableVoices);

      // Restore saved voice preference
      try {
        const savedVoiceName = localStorage.getItem(STORAGE_KEYS.voice);
        if (savedVoiceName) {
          const savedVoice = availableVoices.find(
            (v) => v.name === savedVoiceName
          );
          if (savedVoice) {
            setSelectedVoiceState(savedVoice);
            return;
          }
        }
      } catch {
        // Ignore storage errors
      }

      // Default: prefer English voices, then first available
      const englishVoice = availableVoices.find(
        (v) => v.lang.startsWith("en") && v.localService
      );
      const defaultVoice = englishVoice || availableVoices[0];
      if (defaultVoice) {
        setSelectedVoiceState(defaultVoice);
      }
    }
  }, []);

  // Initialize voices
  useEffect(() => {
    if (!isSynthesisSupported) return;

    // Try to load voices immediately
    loadVoices();

    // Chrome loads voices async, so listen for the event
    window.speechSynthesis.onvoiceschanged = loadVoices;

    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, [loadVoices]);

  // Set voice with persistence
  const setSelectedVoice = useCallback((voice) => {
    setSelectedVoiceState(voice);
    if (voice) {
      try {
        localStorage.setItem(STORAGE_KEYS.voice, voice.name);
      } catch {
        // Ignore storage errors
      }
    }
  }, []);

  // Set rate with persistence
  const setRate = useCallback((newRate) => {
    const clampedRate = Math.max(0.5, Math.min(2, newRate));
    setRateState(clampedRate);
    try {
      localStorage.setItem(STORAGE_KEYS.rate, String(clampedRate));
    } catch {
      // Ignore storage errors
    }
  }, []);

  // Speak text
  const speak = useCallback(
    (text) => {
      if (!isSynthesisSupported || !text) return;

      // Cancel any ongoing speech
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);

      if (selectedVoice) {
        utterance.voice = selectedVoice;
      }
      utterance.rate = rate;
      utterance.pitch = 1;
      utterance.volume = 1;

      utterance.onstart = () => {
        if (isMountedRef.current) {
          setIsSpeaking(true);
          setIsPaused(false);
        }
      };

      utterance.onend = () => {
        if (isMountedRef.current) {
          setIsSpeaking(false);
          setIsPaused(false);
        }
      };

      utterance.onerror = (event) => {
        // Don't treat 'interrupted' or 'canceled' as errors
        if (event.error !== "interrupted" && event.error !== "canceled") {
          console.warn("Speech synthesis error:", event.error);
        }
        if (isMountedRef.current) {
          setIsSpeaking(false);
          setIsPaused(false);
        }
      };

      utterance.onpause = () => {
        if (isMountedRef.current) {
          setIsPaused(true);
        }
      };

      utterance.onresume = () => {
        if (isMountedRef.current) {
          setIsPaused(false);
        }
      };

      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    },
    [selectedVoice, rate]
  );

  // Stop speech
  const stop = useCallback(() => {
    if (!isSynthesisSupported) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    setIsPaused(false);
  }, []);

  // Pause speech
  const pause = useCallback(() => {
    if (!isSynthesisSupported) return;
    window.speechSynthesis.pause();
  }, []);

  // Resume speech
  const resume = useCallback(() => {
    if (!isSynthesisSupported) return;
    window.speechSynthesis.resume();
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      if (isSynthesisSupported) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Chrome bug workaround: speech synthesis stops after ~15 seconds
  // Resume periodically if still speaking
  useEffect(() => {
    if (!isSpeaking || isPaused || !isSynthesisSupported) return;

    const interval = setInterval(() => {
      if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
        window.speechSynthesis.pause();
        window.speechSynthesis.resume();
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [isSpeaking, isPaused]);

  return {
    speak,
    stop,
    pause,
    resume,
    isSpeaking,
    isPaused,
    isSupported: isSynthesisSupported,
    voices,
    selectedVoice,
    setSelectedVoice,
    rate,
    setRate,
  };
}

export default useVoiceOutput;
