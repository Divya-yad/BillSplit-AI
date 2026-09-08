import React from 'react'
import useBillStore from './store/billStore'
import UploadScreen from './components/UploadScreen'
import ReviewScreen from './components/ReviewScreen'
import PeopleScreen from './components/PeopleScreen'
import AssignScreen from './components/AssignScreen'
import BreakdownScreen from './components/BreakdownScreen'

// Step metadata for the progress bar
const STEPS = [
  { key: 'upload',    label: 'Upload',   icon: '📷' },
  { key: 'review',    label: 'Review',   icon: '✏️' },
  { key: 'people',    label: 'People',   icon: '👥' },
  { key: 'assign',    label: 'Assign',   icon: '🍽️' },
  { key: 'breakdown', label: 'Split',    icon: '✅' },
]

function StepBar({ current }) {
  const currentIdx = STEPS.findIndex(s => s.key === current)
  return (
    <div className="step-bar" style={{ maxWidth: 700, margin: '0 auto', padding: '16px 24px' }}>
      {STEPS.map((step, idx) => {
        const done = idx < currentIdx
        const active = idx === currentIdx
        return (
          <React.Fragment key={step.key}>
            <div className={`step ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
              <div className="step-dot">
                {done ? '✓' : active ? step.icon : idx + 1}
              </div>
              <span className="step-label">{step.label}</span>
            </div>
            {idx < STEPS.length - 1 && (
              <div style={{
                flex: 1,
                height: 2,
                background: done ? 'var(--accent-1)' : 'var(--border)',
                transition: 'background 0.3s ease',
                marginBottom: 20,
              }} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

export default function App() {
  const { screen, error } = useBillStore()

  return (
    <div>
      {/* Global step indicator (hidden on upload/breakdown for cleanliness) */}
      {screen !== 'upload' && screen !== 'breakdown' && (
        <StepBar current={screen} />
      )}

      {/* Global error toast */}
      {error && screen !== 'upload' && (
        <div
          className="alert alert-danger"
          style={{
            position: 'fixed',
            top: 16,
            right: 16,
            zIndex: 1000,
            maxWidth: 360,
            boxShadow: 'var(--shadow-lg)',
            animation: 'fadeIn 0.3s ease',
          }}
        >
          <span>⚠️</span>
          <span style={{ flex: 1, fontSize: '0.85rem' }}>{error}</span>
        </div>
      )}

      {/* Screen routing */}
      {screen === 'upload'    && <UploadScreen />}
      {screen === 'review'    && <ReviewScreen />}
      {screen === 'people'    && <PeopleScreen />}
      {screen === 'assign'    && <AssignScreen />}
      {screen === 'breakdown' && <BreakdownScreen />}
    </div>
  )
}
