import React from 'react';
import './ProjectTemplates.css';

const TEMPLATES = [
  {
    id: 'general',
    name: 'General',
    description: 'Standard project',
    icon: '📁',
    ghm: false,
  },
  {
    id: 'scripture_study',
    name: 'Scripture Study',
    description: 'Bible study with hermeneutic constraints',
    icon: '📖',
    ghm: true,
  },
  {
    id: 'theological_research',
    name: 'Theological Research',
    description: 'In-depth theological work',
    icon: '🔬',
    ghm: true,
  },
  {
    id: 'engineering',
    name: 'Engineering',
    description: 'Code, systems, technical design',
    icon: '⚙️',
    ghm: false,
  },
  {
    id: 'writing',
    name: 'Writing',
    description: 'General writing projects',
    icon: '✍️',
    ghm: false,
  },
];

function ProjectTemplates({ selected, onSelect }) {
  return (
    <div className="project-templates">
      <label className="templates-label">Project Type</label>
      <div className="templates-grid">
        {TEMPLATES.map(template => (
          <button
            key={template.id}
            className={`template-card ${selected === template.id ? 'selected' : ''}`}
            onClick={() => onSelect(template.id)}
            type="button"
          >
            <span className="template-icon">{template.icon}</span>
            <span className="template-name">{template.name}</span>
            <span className="template-desc">{template.description}</span>
            {template.ghm && (
              <span className="template-ghm">GHM</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

export default ProjectTemplates;
