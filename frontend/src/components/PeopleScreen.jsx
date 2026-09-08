import React, { useState, useRef } from 'react'
import { setPeople as apiSetPeople } from '../api/client'
import useBillStore from '../store/billStore'

// Color cycle for avatars
const AVATAR_COLORS = [0, 1, 2, 3, 4, 5, 6]

function Avatar({ name, colorIdx, size = 40 }) {
  const initials = name.trim().split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || '?'
  return (
    <div
      className={`avatar avatar-${colorIdx % 7}`}
      style={{ width: size, height: size, fontSize: size * 0.32 }}
    >
      {initials}
    </div>
  )
}

export default function PeopleScreen() {
  const { billId, setPeople, setScreen, setLoading, loading, setError } = useBillStore()
  const [people, setPeopleLocal] = useState([])
  const [inputName, setInputName] = useState('')
  const inputRef = useRef(null)

  const addPerson = () => {
    const name = inputName.trim()
    if (!name) return
    const id = `person-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    setPeopleLocal(prev => [...prev, { id, name, left_early: false }])
    setInputName('')
    inputRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') addPerson()
  }

  const removePerson = (id) => {
    setPeopleLocal(prev => prev.filter(p => p.id !== id))
  }

  const toggleLeftEarly = (id) => {
    setPeopleLocal(prev =>
      prev.map(p => p.id === id ? { ...p, left_early: !p.left_early } : p)
    )
  }

  const handleContinue = async () => {
    if (people.length < 1) return
    setLoading(true)
    setError(null)
    try {
      await apiSetPeople(billId, people)
      setPeople(people)
      setScreen('assign')
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="screen animate-fade">
      <header className="header">
        <span className="logo">⚡ BillSplit AI</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Step 2 of 4
        </span>
      </header>

      <div className="content" style={{ maxWidth: 560, margin: '0 auto', width: '100%' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', marginBottom: 8 }}>
            Who's at the <span className="text-gradient">table?</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Add everyone who needs to split this bill.
          </p>
        </div>

        {/* Input */}
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            ref={inputRef}
            className="input"
            placeholder="Enter a name and press Enter…"
            value={inputName}
            onChange={e => setInputName(e.target.value)}
            onKeyDown={handleKeyDown}
            id="people-name-input"
            autoFocus
          />
          <button
            className="btn btn-primary"
            onClick={addPerson}
            disabled={!inputName.trim()}
            id="people-add-btn"
          >
            Add
          </button>
        </div>

        {/* Quick add chips */}
        <div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8 }}>Quick add</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['Alice', 'Bob', 'Carol', 'Dave', 'Eva', 'Frank'].map(name => (
              <button
                key={name}
                className="chip"
                onClick={() => {
                  const id = `person-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
                  setPeopleLocal(prev => [...prev, { id, name, left_early: false }])
                }}
                style={{ fontSize: '0.8rem', padding: '6px 14px' }}
              >
                + {name}
              </button>
            ))}
          </div>
        </div>

        {/* People List */}
        {people.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {people.length} {people.length === 1 ? 'person' : 'people'}
            </p>
            {people.map((person, idx) => (
              <div
                key={person.id}
                className="person-card animate-pop"
                style={{ display: 'flex', alignItems: 'center', gap: 14 }}
              >
                <Avatar name={person.name} colorIdx={idx} />

                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{person.name}</div>
                  {person.left_early && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--amber)', marginTop: 2 }}>
                      🚶 Left early — won't be included in shared items ordered after
                    </div>
                  )}
                </div>

                {/* Left early toggle */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <label className="toggle">
                    <input
                      type="checkbox"
                      checked={person.left_early}
                      onChange={() => toggleLeftEarly(person.id)}
                      id={`left-early-${person.id}`}
                    />
                    <span className="toggle-track" />
                  </label>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Left early</span>
                </div>

                <button
                  className="btn btn-ghost btn-icon"
                  onClick={() => removePerson(person.id)}
                  title="Remove"
                  style={{ color: 'var(--danger)' }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {people.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '40px 20px',
            color: 'var(--text-muted)',
            border: '1px dashed var(--border)',
            borderRadius: 'var(--radius-lg)',
          }}>
            <div style={{ fontSize: '2.5rem', marginBottom: 8 }}>👥</div>
            <p>Add at least one person to continue</p>
          </div>
        )}
      </div>

      {/* Sticky Footer */}
      <div className="sticky-footer">
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button className="btn btn-ghost" onClick={() => setScreen('review')}>
            ← Back
          </button>
          <button
            className="btn btn-primary"
            onClick={handleContinue}
            disabled={people.length < 1 || loading}
            id="people-continue-btn"
          >
            {loading ? 'Saving…' : `Assign Items (${people.length} ${people.length === 1 ? 'person' : 'people'}) →`}
          </button>
        </div>
      </div>
    </div>
  )
}
