import React, { useState, useCallback } from 'react'
import { correctBill } from '../api/client'
import useBillStore from '../store/billStore'

const fmt = (v) => parseFloat(v || 0).toFixed(2)

function confClass(value) {
  if (value >= 0.75) return 'conf-high'
  if (value >= 0.5)  return 'conf-med'
  return 'conf-low'
}

function ConfidenceDot({ value, reason }) {
  const color = value >= 0.75 ? 'var(--success)' : value >= 0.5 ? 'var(--amber)' : 'var(--danger)'
  return (
    <div className="tooltip-wrap">
      <span style={{
        display: 'inline-block',
        width: 8, height: 8,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
        marginLeft: 4,
      }} />
      <div className="tooltip">{(value * 100).toFixed(0)}% — {reason}</div>
    </div>
  )
}

function EditableCell({ value, type = 'text', onChange, confValue = 1, align = 'left', step, min }) {
  return (
    <td className={`editable-cell ${confClass(confValue)}`} style={{ borderRadius: 6 }}>
      <input
        type={type}
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        step={step ?? (type === 'number' ? 'any' : undefined)}
        min={min ?? (type === 'number' ? '0' : undefined)}
        style={{ fontFamily: 'inherit', textAlign: align }}
      />
    </td>
  )
}

export default function ReviewScreen() {
  const { billId, extracted, setExtracted, setScreen, setLoading, loading, setError } = useBillStore()
  const [items, setItems] = useState(() => extracted?.line_items?.map(i => ({ ...i })) ?? [])
  const [charges, setCharges] = useState(() => extracted?.charges?.map(c => ({ ...c })) ?? [])
  const [dismissed, setDismissed] = useState(new Set())
  const [saving, setSaving] = useState(false)

  const printedTotal = parseFloat(extracted?.printed_total || 0)
  const computedTotal = parseFloat(extracted?.computed_total || 0)
  const hasMismatch = extracted?.total_mismatch
  const delta = Math.abs(printedTotal - computedTotal).toFixed(2)

  const updateItem = useCallback((idx, field, val) => {
    setItems(prev => {
      const next = [...prev]
      next[idx] = { ...next[idx], [field]: field === 'name' ? val : parseFloat(val) || 0 }
      // Auto-update total_price when qty or unit_price changes
      if (field === 'quantity' || field === 'unit_price') {
        const item = next[idx]
        next[idx].total_price = (item.quantity * item.unit_price).toFixed(2)
      }
      return next
    })
  }, [])

  const updateCharge = useCallback((idx, field, val) => {
    setCharges(prev => {
      const next = [...prev]
      next[idx] = { ...next[idx], [field]: val }
      return next
    })
  }, [])

  const dismissField = (id) => setDismissed(prev => new Set([...prev, id]))

  const allFlagged = [
    ...items.filter(i => i.confidence.value < 0.75).map(i => i.id),
    ...charges.filter(c => c.confidence.value < 0.75).map(c => c.id),
  ]
  const unresolvedFlags = allFlagged.filter(id => !dismissed.has(id))
  const canContinue = unresolvedFlags.length === 0 && !hasMismatch || (hasMismatch && extracted?.trust_computed !== undefined)

  const handleTrustComputed = async () => {
    await applyCorrection({ trust_computed: true })
  }

  const handleTrustPrinted = async () => {
    await applyCorrection({ trust_computed: false })
  }

  async function applyCorrection(extra = {}) {
    setSaving(true)
    try {
      const updated = await correctBill(billId, {
        line_items: items,
        charges: charges,
        ...extra,
      })
      setExtracted(updated)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleContinue = async () => {
    setLoading(true)
    try {
      await applyCorrection()
      setScreen('people')
    } catch {
      // error set inside
    } finally {
      setLoading(false)
    }
  }

  // Confidence legend
  const legendItems = [
    { label: 'High confidence', color: 'transparent' },
    { label: 'Review recommended', color: 'hsla(38,100%,55%,0.25)' },
    { label: 'Low confidence — edit or dismiss', color: 'hsla(0,85%,60%,0.25)' },
  ]

  return (
    <div className="screen animate-fade">
      <header className="header">
        <span className="logo">⚡ BillSplit AI</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {saving && <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />}
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {extracted?.restaurant_name || 'Review Bill'}
          </span>
        </div>
      </header>

      <div className="content" style={{ maxWidth: 900, margin: '0 auto', width: '100%' }}>

        {/* Mismatch Banner */}
        {hasMismatch && (
          <div className="alert alert-warning animate-fade" style={{ flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span>⚠️</span>
              <strong>Total mismatch detected</strong>
            </div>
            <p style={{ fontSize: '0.875rem' }}>
              Printed total <strong>₹{fmt(printedTotal)}</strong> vs.
              our calculated <strong>₹{fmt(computedTotal)}</strong> — difference of <strong>₹{delta}</strong>.
              Which total should we use to split?
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary btn-sm" onClick={handleTrustComputed} id="trust-computed-btn">
                ✅ Use calculated ₹{fmt(computedTotal)}
              </button>
              <button className="btn btn-secondary btn-sm" onClick={handleTrustPrinted} id="trust-printed-btn">
                🧾 Use printed ₹{fmt(printedTotal)}
              </button>
            </div>
          </div>
        )}

        {/* Confidence legend */}
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Confidence:
          </span>
          {legendItems.map(l => (
            <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <span style={{ width: 12, height: 12, borderRadius: 3, background: l.color, border: '1px solid var(--border)', display: 'inline-block' }} />
              {l.label}
            </div>
          ))}
        </div>

        {/* Line Items Table */}
        <section>
          <h2 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            🍽️ Line Items
            <span style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-muted)' }}>
              ({items.length} items)
            </span>
          </h2>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ minWidth: 200 }}>Item</th>
                  <th style={{ width: 85, textAlign: 'center' }}>Qty</th>
                  <th style={{ width: 110, textAlign: 'right' }}>Unit ₹</th>
                  <th style={{ width: 110, textAlign: 'right' }}>Total ₹</th>
                  <th style={{ width: 60 }}>Conf.</th>
                  <th style={{ width: 80 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const flagged = item.confidence.value < 0.75
                  const isDismissed = dismissed.has(item.id)
                  return (
                    <tr key={item.id} style={{ opacity: isDismissed ? 0.5 : 1 }}>
                      <EditableCell
                        value={item.name}
                        onChange={v => updateItem(idx, 'name', v)}
                        confValue={item.confidence.value}
                      />
                      <EditableCell
                        value={item.quantity}
                        type="number"
                        align="center"
                        step="1"
                        min="0"
                        onChange={v => updateItem(idx, 'quantity', v)}
                        confValue={item.confidence.value}
                      />
                      <EditableCell
                        value={item.unit_price != null ? item.unit_price : ''}
                        type="number"
                        align="right"
                        step="0.01"
                        min="0"
                        onChange={v => updateItem(idx, 'unit_price', v)}
                        confValue={item.confidence.value}
                      />
                      <EditableCell
                        value={item.total_price != null ? item.total_price : ''}
                        type="number"
                        align="right"
                        step="0.01"
                        min="0"
                        onChange={v => updateItem(idx, 'total_price', v)}
                        confValue={item.confidence.value}
                      />
                      <td>
                        <ConfidenceDot value={item.confidence.value} reason={item.confidence.reason} />
                      </td>
                      <td>
                        {flagged && !isDismissed ? (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => dismissField(item.id)}
                            title="Dismiss this flag"
                          >Dismiss</button>
                        ) : isDismissed ? (
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>✓</span>
                        ) : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Charges Table */}
        {charges.length > 0 && (
          <section>
            <h2 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 12 }}>
              📊 Taxes & Charges
            </h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Label</th>
                    <th style={{ width: 130 }}>Type</th>
                    <th style={{ width: 110, textAlign: 'right' }}>Amount ₹</th>
                    <th style={{ width: 90, textAlign: 'right' }}>Percent %</th>
                    <th style={{ width: 60 }}>Conf.</th>
                  </tr>
                </thead>
                <tbody>
                  {charges.map((charge, idx) => (
                    <tr key={charge.id}>
                      <EditableCell
                        value={charge.label}
                        onChange={v => updateCharge(idx, 'label', v)}
                        confValue={charge.confidence.value}
                      />
                      <td>
                        <select
                          value={charge.kind}
                          onChange={e => updateCharge(idx, 'kind', e.target.value)}
                          className="input"
                          style={{ padding: '6px 8px' }}
                        >
                          {['tax', 'service_charge', 'discount', 'other_fee'].map(k => (
                            <option key={k} value={k}>{k.replace('_', ' ')}</option>
                          ))}
                        </select>
                      </td>
                      <EditableCell
                        value={charge.amount != null ? charge.amount : ''}
                        type="number"
                        align="right"
                        step="0.01"
                        onChange={v => updateCharge(idx, 'amount', v || null)}
                        confValue={charge.confidence.value}
                      />
                      <EditableCell
                        value={charge.percent != null ? charge.percent : ''}
                        type="number"
                        align="right"
                        step="0.01"
                        onChange={v => updateCharge(idx, 'percent', v || null)}
                        confValue={charge.confidence.value}
                      />
                      <td>
                        <ConfidenceDot value={charge.confidence.value} reason={charge.confidence.reason} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Totals Summary */}
        <div className="glass-card" style={{ padding: '20px 24px', display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Subtotal</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>₹{fmt(extracted?.computed_subtotal)}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Calculated Total</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-2)' }}>₹{fmt(extracted?.computed_total)}</div>
          </div>
          {extracted?.printed_total && (
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Printed Total</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: hasMismatch ? 'var(--warning)' : 'var(--text-secondary)' }}>
                ₹{fmt(extracted?.printed_total)}
                {hasMismatch && ' ⚠️'}
              </div>
            </div>
          )}
        </div>

        {/* Unresolved flags warning */}
        {unresolvedFlags.length > 0 && (
          <div className="alert alert-warning animate-fade">
            <span>⚠️</span>
            <span>
              {unresolvedFlags.length} field{unresolvedFlags.length > 1 ? 's' : ''} need attention.
              Edit the highlighted cells or click Dismiss to continue.
            </span>
          </div>
        )}
      </div>

      {/* Sticky Footer */}
      <div className="sticky-footer">
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            {unresolvedFlags.length > 0
              ? `${unresolvedFlags.length} unresolved flag${unresolvedFlags.length > 1 ? 's' : ''}`
              : hasMismatch && extracted?.trust_computed === undefined
              ? 'Resolve total mismatch to continue'
              : '✅ All fields verified'}
          </span>
          <button
            className="btn btn-primary"
            onClick={handleContinue}
            disabled={loading || (unresolvedFlags.length > 0) || (hasMismatch && extracted?.trust_computed === undefined)}
            id="review-continue-btn"
          >
            {loading ? 'Saving…' : 'Add People →'}
          </button>
        </div>
      </div>
    </div>
  )
}
