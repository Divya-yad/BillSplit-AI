import React, { useState, useCallback, useMemo } from 'react'
import { setAssignments as apiSetAssignments, computeBreakdown } from '../api/client'
import useBillStore from '../store/billStore'

const fmt = (v) => `₹${parseFloat(v || 0).toFixed(2)}`

function Avatar({ name, colorIdx, size = 32, selected, onClick }) {
  const initials = name.trim().split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || '?'
  return (
    <div
      className={`avatar avatar-${colorIdx % 7} ${selected ? 'selected' : ''}`}
      style={{ width: size, height: size, fontSize: size * 0.32 }}
      onClick={onClick}
      title={name}
    >
      {initials}
    </div>
  )
}

function ItemRow({ item, people, assignment, onAssignmentChange }) {
  const shares = assignment?.shares || {}
  const assignedCount = Object.keys(shares).length
  const isAssigned = assignedCount > 0

  // Toggle a person in/out of this item
  const togglePerson = (personId) => {
    const current = { ...shares }
    if (current[personId]) {
      delete current[personId]
    } else {
      current[personId] = 1
    }
    // Normalise to sum to 1
    const total = Object.values(current).reduce((a, b) => a + b, 0)
    const normalised = {}
    for (const [pid, w] of Object.entries(current)) {
      normalised[pid] = w / total
    }
    onAssignmentChange(normalised)
  }

  const assignEveryone = () => {
    const eligible = people.filter(p => !p.left_early)
    const n = eligible.length
    if (n === 0) return
    const eq = {}
    eligible.forEach(p => { eq[p.id] = 1 / n })
    onAssignmentChange(eq)
  }

  return (
    <div className={`item-row ${isAssigned ? 'assigned' : ''} animate-fade`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{item.name}</div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '1px 8px',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: 'var(--accent-2)',
            }}>
              Qty: {item.quantity || 1}
            </span>
            <span>•</span>
            <span>₹{parseFloat(item.unit_price || item.total_price || 0).toFixed(2)} each</span>
          </div>
        </div>
        <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
          {fmt(item.total_price)}
        </div>
      </div>

      {/* Assignment row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          Who had this?
        </span>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', flex: 1 }}>
          {people.map((p, idx) => (
            <div key={p.id} className="tooltip-wrap">
              <Avatar
                name={p.name}
                colorIdx={idx}
                size={34}
                selected={!!shares[p.id]}
                onClick={() => togglePerson(p.id)}
              />
              <div className="tooltip">
                {p.name}
                {shares[p.id] ? ` (${(shares[p.id] * 100).toFixed(0)}%)` : ''}
                {p.left_early ? ' 🚶 left early' : ''}
              </div>
            </div>
          ))}
        </div>

        <button
          className="chip"
          style={{ fontSize: '0.75rem', padding: '4px 10px' }}
          onClick={assignEveryone}
          title="Assign to everyone still at the table"
        >
          👥 Everyone
        </button>

        {isAssigned && (
          <button
            className="chip"
            style={{ fontSize: '0.75rem', padding: '4px 10px', color: 'var(--danger)', borderColor: 'hsla(0,85%,60%,0.3)' }}
            onClick={() => onAssignmentChange({})}
          >
            ✕ Clear
          </button>
        )}
      </div>

      {/* Share breakdown if multiple people */}
      {assignedCount > 1 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {Object.entries(shares).map(([pid, frac]) => {
            const person = people.find(p => p.id === pid)
            if (!person) return null
            const personIdx = people.indexOf(person)
            return (
              <span
                key={pid}
                style={{
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-full)',
                  background: `var(--avatar-${personIdx % 7}-bg, var(--bg-elevated))`,
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border)',
                }}
              >
                {person.name}: {fmt(parseFloat(item.total_price) * frac)}
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function AssignScreen() {
  const { billId, extracted, people, setAssignments, setBreakdown, setScreen, setLoading, loading, setError } = useBillStore()
  const [assignmentMap, setAssignmentMap] = useState({})  // line_item_id → shares dict

  const items = extracted?.line_items || []

  const updateAssignment = useCallback((itemId, shares) => {
    setAssignmentMap(prev => ({ ...prev, [itemId]: shares }))
  }, [])

  // Running per-person totals
  const runningTotals = useMemo(() => {
    const totals = {}
    people.forEach(p => { totals[p.id] = 0 })
    for (const item of items) {
      const shares = assignmentMap[item.id] || {}
      for (const [pid, frac] of Object.entries(shares)) {
        totals[pid] = (totals[pid] || 0) + parseFloat(item.total_price) * frac
      }
    }
    return totals
  }, [assignmentMap, items, people])

  const unassignedItems = items.filter(i => !assignmentMap[i.id] || Object.keys(assignmentMap[i.id]).length === 0)
  const canContinue = unassignedItems.length === 0

  const handleCompute = async () => {
    setLoading(true)
    setError(null)
    try {
      const assignments = items.map(item => ({
        line_item_id: item.id,
        shares: assignmentMap[item.id] || {},
      }))
      await apiSetAssignments(billId, assignments)
      setAssignments(assignments)
      const breakdown = await computeBreakdown(billId)
      setBreakdown(breakdown)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  // Assign all remaining items to everyone
  const assignAllToEveryone = () => {
    const eligible = people.filter(p => !p.left_early)
    const n = eligible.length
    if (n === 0) return
    const newMap = { ...assignmentMap }
    for (const item of unassignedItems) {
      const eq = {}
      eligible.forEach(p => { eq[p.id] = 1 / n })
      newMap[item.id] = eq
    }
    setAssignmentMap(newMap)
  }

  return (
    <div className="screen animate-fade">
      <header className="header">
        <span className="logo">⚡ BillSplit AI</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Step 3 of 4
        </span>
      </header>

      <div className="content" style={{ maxWidth: 760, margin: '0 auto', width: '100%', paddingBottom: 100 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ fontSize: '1.8rem', marginBottom: 8 }}>
              Who had <span className="text-gradient">what?</span>
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
              Tap avatars to assign each item. Tap multiple for a shared dish.
            </p>
          </div>
          {unassignedItems.length > 0 && (
            <button className="btn btn-secondary btn-sm" onClick={assignAllToEveryone}>
              👥 Assign remaining to everyone
            </button>
          )}
        </div>

        {/* Progress */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 16px',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border)',
        }}>
          <div style={{
            flex: 1,
            height: 6,
            background: 'var(--border)',
            borderRadius: 3,
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${((items.length - unassignedItems.length) / Math.max(items.length, 1)) * 100}%`,
              background: 'var(--accent-grad)',
              borderRadius: 3,
              transition: 'width 0.3s ease',
            }} />
          </div>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
            {items.length - unassignedItems.length} / {items.length} assigned
          </span>
        </div>

        {/* Item rows */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map(item => (
            <ItemRow
              key={item.id}
              item={item}
              people={people}
              assignment={{ shares: assignmentMap[item.id] || {} }}
              onAssignmentChange={shares => updateAssignment(item.id, shares)}
            />
          ))}
        </div>
      </div>

      {/* Sticky footer with running totals */}
      <div className="sticky-footer">
        <div style={{ maxWidth: 760, margin: '0 auto' }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, overflowX: 'auto', paddingBottom: 4 }}>
            {people.map((p, idx) => (
              <div key={p.id} className="person-total-pill">
                <span className="name">{p.name.split(' ')[0]}</span>
                <span className="amount" style={{ color: `hsl(${[262,198,152,38,330,175,15][idx%7]}, 80%, 70%)` }}>
                  ₹{(runningTotals[p.id] || 0).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button className="btn btn-ghost" onClick={() => setScreen('people')}>← Back</button>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {unassignedItems.length > 0 && (
                <span style={{ fontSize: '0.8rem', color: 'var(--warning)' }}>
                  ⚠ {unassignedItems.length} item{unassignedItems.length > 1 ? 's' : ''} unassigned
                </span>
              )}
              <button
                className="btn btn-primary"
                onClick={handleCompute}
                disabled={!canContinue || loading}
                id="assign-compute-btn"
              >
                {loading ? (
                  <><div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} /> Computing…</>
                ) : '🧮 Compute Split →'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
