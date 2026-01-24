import React, { useEffect, useRef } from "react";
import "./Drawer.css";

/**
 * Reusable Drawer component for mobile slide-in panels.
 *
 * @param {boolean} isOpen - Whether the drawer is open
 * @param {function} onClose - Callback when drawer should close
 * @param {"left" | "right"} side - Which side the drawer slides from
 * @param {string} title - Optional header title
 * @param {React.ReactNode} children - Drawer content
 */
export default function Drawer({
  isOpen,
  onClose,
  side = "left",
  title,
  children,
}) {
  const drawerRef = useRef(null);
  const previousActiveElement = useRef(null);

  // Handle Escape key
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e) {
      if (e.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Body scroll lock
  useEffect(() => {
    if (isOpen) {
      const scrollY = window.scrollY;
      document.body.style.position = "fixed";
      document.body.style.top = `-${scrollY}px`;
      document.body.style.width = "100%";
      document.body.style.overflow = "hidden";

      return () => {
        document.body.style.position = "";
        document.body.style.top = "";
        document.body.style.width = "";
        document.body.style.overflow = "";
        window.scrollTo(0, scrollY);
      };
    }
  }, [isOpen]);

  // Focus trap and focus management
  useEffect(() => {
    if (isOpen) {
      // Store previously focused element
      previousActiveElement.current = document.activeElement;

      // Focus the drawer
      if (drawerRef.current) {
        drawerRef.current.focus();
      }

      return () => {
        // Restore focus when closing
        if (previousActiveElement.current) {
          previousActiveElement.current.focus();
        }
      };
    }
  }, [isOpen]);

  // Focus trap - keep focus within drawer
  useEffect(() => {
    if (!isOpen || !drawerRef.current) return;

    function handleFocusTrap(e) {
      if (e.key !== "Tab") return;

      const focusableElements = drawerRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );

      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    }

    document.addEventListener("keydown", handleFocusTrap);
    return () => document.removeEventListener("keydown", handleFocusTrap);
  }, [isOpen]);

  // Handle backdrop click
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="drawer-backdrop"
      onClick={handleBackdropClick}
      aria-hidden="true"
    >
      <div
        ref={drawerRef}
        className={`drawer drawer-${side}`}
        role="dialog"
        aria-modal="true"
        aria-label={title || "Navigation drawer"}
        tabIndex={-1}
      >
        {/* Header */}
        <div className="drawer-header">
          {title && <h2 className="drawer-title">{title}</h2>}
          <button
            className="drawer-close"
            onClick={onClose}
            aria-label="Close drawer"
          >
            &times;
          </button>
        </div>

        {/* Content */}
        <div className="drawer-content">{children}</div>
      </div>
    </div>
  );
}
