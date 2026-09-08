import { create } from 'zustand'

/**
 * Global Zustand store for BillSplit AI.
 * Tracks the linear flow: Upload → Review → People → Assign → Breakdown
 */
const useBillStore = create((set, get) => ({
  // ── Navigation ────────────────────────────────────────────────
  screen: 'upload', // 'upload' | 'review' | 'people' | 'assign' | 'breakdown'

  // ── Bill Data ─────────────────────────────────────────────────
  billId: null,
  extracted: null,   // ExtractedBill from backend
  people: [],        // Person[]
  assignments: [],   // ItemAssignment[]
  breakdown: null,   // BillBreakdown | null

  // ── UI State ──────────────────────────────────────────────────
  loading: false,
  error: null,

  // ── Actions ───────────────────────────────────────────────────
  setScreen: (screen) => set({ screen }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  setBillData: ({ billId, extracted }) =>
    set({ billId, extracted, screen: 'review' }),

  setExtracted: (extracted) => set({ extracted }),

  setPeople: (people) => set({ people }),

  setAssignments: (assignments) => set({ assignments }),

  setBreakdown: (breakdown) => set({ breakdown, screen: 'breakdown' }),

  resetBill: () =>
    set({
      billId: null,
      extracted: null,
      people: [],
      assignments: [],
      breakdown: null,
      screen: 'upload',
      error: null,
    }),

  // ── Computed helpers ─────────────────────────────────────────
  getPersonRunningTotal: (personId) => {
    const { extracted, assignments } = get()
    if (!extracted) return 0
    let total = 0
    for (const a of assignments) {
      const share = a.shares[personId]
      if (!share) continue
      const item = extracted.line_items.find(i => i.id === a.line_item_id)
      if (item) total += parseFloat(item.total_price) * share
    }
    return total
  },
}))

export default useBillStore
