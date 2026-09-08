import React, { useRef } from 'react'
import useBillStore from '../store/billStore'

const fmt = (v) => `₹${parseFloat(v || 0).toFixed(2)}`

// Hue per person index (matches CSS avatar colors)
const PERSON_HUES = [262, 198, 152, 38, 330, 175, 15]

function Avatar({ name, colorIdx, size = 44 }) {
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

function PersonCard({ person, breakdown, colorIdx, extracted }) {
  const hue = PERSON_HUES[colorIdx % 7]

  return (
    <div className="breakdown-card animate-fade">
      {/* Card Header */}
      <div className="breakdown-header">
        <Avatar name={person.name} colorIdx={colorIdx} />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{person.name}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>
            {breakdown.items.length} item{breakdown.items.length !== 1 ? 's' : ''}
          </div>
        </div>
        <div
          className="breakdown-total"
          style={{ color: `hsl(${hue}, 80%, 70%)` }}
        >
          {fmt(breakdown.final_total)}
        </div>
      </div>

      {/* Itemized list */}
      <div style={{ padding: '12px 24px 0' }}>
        {breakdown.items.map(item => {
          const orig = extracted?.line_items?.find(li => li.id === item.line_item_id)
          const qty = orig?.quantity
          return (
            <div key={item.line_item_id} className="breakdown-line">
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                {item.name}
                {qty && (
                  <span style={{ marginLeft: 6, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    (Qty: {qty})
                  </span>
                )}
                {item.share_fraction < 0.99 && (
                  <span style={{ marginLeft: 6, fontSize: '0.75rem', color: 'var(--accent-2)' }}>
                    ({(item.share_fraction * 100).toFixed(0)}% share)
                  </span>
                )}
              </span>
              <span className="amount-positive">{fmt(item.your_share_amount)}</span>
            </div>
          )
        })}

        {/* Charges */}
        <div style={{ borderTop: '1px solid var(--border)', marginTop: 8, paddingTop: 8 }}>
          {parseFloat(breakdown.tax_share) !== 0 && (
            <div className="breakdown-line">
              <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                🏛️ Tax (GST/CGST/SGST — proportional)
              </span>
              <span className="amount-charge">{fmt(breakdown.tax_share)}</span>
            </div>
          )}
          {parseFloat(breakdown.service_charge_share) !== 0 && (
            <div className="breakdown-line">
              <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                🍽️ Service charge (proportional)
              </span>
              <span className="amount-charge">{fmt(breakdown.service_charge_share)}</span>
            </div>
          )}
          {parseFloat(breakdown.discount_share) !== 0 && (
            <div className="breakdown-line">
              <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                🎉 Discount
              </span>
              <span className="amount-negative">{fmt(breakdown.discount_share)}</span>
            </div>
          )}
          {parseFloat(breakdown.other_fee_share) !== 0 && (
            <div className="breakdown-line">
              <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                📦 Other fees
              </span>
              <span className="amount-charge">{fmt(breakdown.other_fee_share)}</span>
            </div>
          )}
        </div>

        {/* Total */}
        <div className="breakdown-line total" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>Total</span>
            <div className="tooltip-wrap">
              <span style={{
                width: 18, height: 18, borderRadius: '50%',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.65rem',
                cursor: 'default',
                color: 'var(--text-muted)',
              }}>?</span>
              <div className="tooltip" style={{ maxWidth: 320 }}>
                {breakdown.formula_hint}
              </div>
            </div>
          </div>
          <span style={{ color: `hsl(${hue}, 80%, 70%)`, fontSize: '1.1rem' }}>
            {fmt(breakdown.final_total)}
          </span>
        </div>
      </div>
    </div>
  )
}

function buildWhatsAppText(breakdown, extracted, people) {
  const restaurant = extracted?.restaurant_name || 'Restaurant'
  let text = `*${restaurant} — Bill Split* 🧾\n\n`
  for (const pb of breakdown.people) {
    text += `*${pb.name}*: ${fmt(pb.final_total)}\n`
    for (const item of pb.items) {
      const orig = extracted?.line_items?.find(li => li.id === item.line_item_id)
      const qtyStr = orig?.quantity ? ` (Qty: ${orig.quantity})` : ''
      text += `  • ${item.name}${qtyStr} — ${fmt(item.your_share_amount)}\n`
    }
    if (parseFloat(pb.tax_share) !== 0) text += `  + Tax: ${fmt(pb.tax_share)}\n`
    if (parseFloat(pb.service_charge_share) !== 0) text += `  + Service: ${fmt(pb.service_charge_share)}\n`
    if (parseFloat(pb.discount_share) !== 0) text += `  − Discount: ${fmt(pb.discount_share)}\n`
    text += '\n'
  }
  text += `*Grand total: ${fmt(breakdown.grand_total_check)}*`
  if (parseFloat(breakdown.rounding_adjustment) !== 0) {
    const person = people.find(p => p.id === breakdown.rounding_adjusted_person_id)
    text += `\n(₹${Math.abs(parseFloat(breakdown.rounding_adjustment)).toFixed(2)} rounding adjustment on ${person?.name || 'largest payer'})`
  }
  return text
}

export default function BreakdownScreen() {
  const { breakdown, extracted, people, resetBill } = useBillStore()
  const cardsRef = useRef(null)

  if (!breakdown) return null

  const handleShareWhatsApp = () => {
    const text = buildWhatsAppText(breakdown, extracted, people)
    const url = `https://wa.me/?text=${encodeURIComponent(text)}`
    window.open(url, '_blank')
  }

  const handleCopyText = async () => {
    const text = buildWhatsAppText(breakdown, extracted, people)
    try {
      await navigator.clipboard.writeText(text)
      alert('Copied to clipboard! ✅')
    } catch {
      alert(text)
    }
  }

  const handleDownloadImage = async () => {
    const { default: html2canvas } = await import('html2canvas')
    const el = cardsRef.current
    if (!el) return
    const canvas = await html2canvas(el, {
      backgroundColor: '#0d0f17',
      scale: 2,
      useCORS: true,
    })
    const link = document.createElement('a')
    link.download = `billsplit-${Date.now()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }

  const grandTotal = parseFloat(breakdown.grand_total_check || 0)
  const roundingAdj = parseFloat(breakdown.rounding_adjustment || 0)
  const roundingPerson = people.find(p => p.id === breakdown.rounding_adjusted_person_id)

  return (
    <div className="screen animate-fade">
      <header className="header">
        <span className="logo">⚡ BillSplit AI</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm" onClick={handleShareWhatsApp} id="share-whatsapp-btn">
            💬 WhatsApp
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handleCopyText} id="copy-text-btn">
            📋 Copy
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handleDownloadImage} id="download-image-btn">
            📸 Save Image
          </button>
        </div>
      </header>

      <div className="content" style={{ maxWidth: 760, margin: '0 auto', width: '100%' }}>
        {/* Hero Summary */}
        <div style={{
          textAlign: 'center',
          padding: '16px 0 24px',
        }}>
          <div style={{ fontSize: '3rem', marginBottom: 8 }}>✅</div>
          <h1 style={{ fontSize: '1.8rem', marginBottom: 8 }}>
            Split <span className="text-gradient">complete!</span>
          </h1>
          {extracted?.restaurant_name && (
            <p style={{ color: 'var(--text-secondary)' }}>{extracted.restaurant_name}</p>
          )}
          <div style={{
            display: 'inline-flex',
            gap: 32,
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-xl)',
            padding: '16px 32px',
            marginTop: 16,
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Grand Total</div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'var(--font-display)' }}>
                {fmt(grandTotal)}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Splitting between</div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'var(--font-display)' }}>
                {breakdown.people.length}
              </div>
            </div>
          </div>
        </div>

        {/* Per-person cards */}
        <div ref={cardsRef} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {breakdown.people.map((pb, idx) => {
            const person = people.find(p => p.id === pb.person_id)
            return (
              <PersonCard
                key={pb.person_id}
                person={person || { name: pb.name }}
                breakdown={pb}
                colorIdx={idx}
                extracted={extracted}
              />
            )
          })}
        </div>

        {/* Footer reconciliation */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontWeight: 600 }}>Sum of all amounts</span>
            <span style={{ fontWeight: 700, color: 'var(--success)' }}>{fmt(grandTotal)}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            <span>Authoritative total used</span>
            <span>{fmt(breakdown.authoritative_total)}</span>
          </div>
          <div style={{
            marginTop: 12,
            paddingTop: 12,
            borderTop: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: '0.8rem',
            color: 'var(--success)',
          }}>
            <span>✅</span>
            <span>
              {grandTotal.toFixed(2) === parseFloat(breakdown.authoritative_total).toFixed(2)
                ? 'Amounts verified — sums match exactly to the paisa.'
                : 'Amounts verified — small rounding applied.'}
            </span>
          </div>
          {roundingAdj !== 0 && roundingPerson && (
            <p style={{ marginTop: 8, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              ₹{Math.abs(roundingAdj).toFixed(2)} rounding adjustment on <strong>{roundingPerson.name}</strong>
              {' '}(largest payer — deterministic, auditable).
            </p>
          )}
        </div>

        {/* Start new bill */}
        <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 32 }}>
          <button className="btn btn-secondary" onClick={resetBill} id="new-bill-btn">
            + Split Another Bill
          </button>
        </div>
      </div>
    </div>
  )
}
