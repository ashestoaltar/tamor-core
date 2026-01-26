import React from 'react';
import './AboutTamor.css';

function AboutTamor({ onClose }) {
  return (
    <div className="about-tamor">
      <header className="about-header">
        <h2>About Tamor</h2>
        {onClose && (
          <button className="about-close-btn" onClick={onClose}>×</button>
        )}
      </header>

      <div className="about-content">
        <section className="about-section">
          <h3>What Tamor Is</h3>
          <p>
            Tamor is a <strong>personal AI workspace</strong> for research,
            knowledge management, and assisted creation.
          </p>
          <p>
            Unlike typical chatbots, Tamor emphasizes:
          </p>
          <ul>
            <li><strong>Persistent memory</strong> — remembers what you tell it</li>
            <li><strong>Grounded responses</strong> — cites sources, not just guesses</li>
            <li><strong>Epistemic honesty</strong> — distinguishes fact from interpretation</li>
            <li><strong>Local-first</strong> — your data stays on your hardware</li>
          </ul>
        </section>

        <section className="about-section">
          <h3>Core Principles</h3>
          <div className="about-principles">
            <div className="about-principle">
              <span className="about-principle-icon">🎯</span>
              <div>
                <strong>No autonomous actions</strong>
                <p>Tamor doesn't act without your explicit consent.</p>
              </div>
            </div>
            <div className="about-principle">
              <span className="about-principle-icon">👁️</span>
              <div>
                <strong>No hidden memory</strong>
                <p>Everything Tamor remembers is visible to you.</p>
              </div>
            </div>
            <div className="about-principle">
              <span className="about-principle-icon">⚖️</span>
              <div>
                <strong>No false certainty</strong>
                <p>When topics are contested, Tamor says so.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="about-section">
          <h3>Tamor's Voice</h3>
          <blockquote className="about-quote">
            "I know where the ground is firm, and I won't pretend the hills are bedrock."
          </blockquote>
          <p>
            Tamor aims to be <em>aligned</em>, <em>steady</em>, and <em>illuminating</em>.
          </p>
        </section>

        <section className="about-section">
          <h3>Learn More</h3>
          <ul className="about-links">
            <li>
              <a
                href="https://github.com/ashestoaltar/tamor-core/blob/main/docs/Features.md"
                target="_blank"
                rel="noopener noreferrer"
              >
                Features Guide
              </a>
            </li>
            <li>
              <a
                href="https://github.com/ashestoaltar/tamor-core/blob/main/docs/BOUNDARIES.md"
                target="_blank"
                rel="noopener noreferrer"
              >
                Boundaries & Principles
              </a>
            </li>
            <li>
              <a
                href="https://github.com/ashestoaltar/tamor-core"
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub Repository
              </a>
            </li>
          </ul>
        </section>

        <footer className="about-footer">
          <p>
            <strong>Wholeness • Light • Insight</strong>
          </p>
          <p className="about-version">
            Tamor Core — Phase 8
          </p>
        </footer>
      </div>
    </div>
  );
}

export default AboutTamor;
