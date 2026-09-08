import axios from 'axios'

const api = axios.create({
  baseURL: '/bills',
  timeout: 60000, // Gemini can take a few seconds
})

/**
 * Upload 1-3 bill images. Returns { bill_id, extracted }.
 * @param {File[]} files
 */
export async function uploadBill(files) {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  const { data } = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Get full bill state (extracted, people, assignments, breakdown).
 */
export async function getBillState(billId) {
  const { data } = await api.get(`/${billId}`)
  return data
}

/**
 * Apply human corrections to the extracted bill.
 * @param {string} billId
 * @param {object} correction  Partial diff — only changed fields.
 */
export async function correctBill(billId, correction) {
  const { data } = await api.patch(`/${billId}/correct`, correction)
  return data
}

/**
 * Set the people for a bill.
 * @param {string} billId
 * @param {Array<{id, name, left_early}>} people
 */
export async function setPeople(billId, people) {
  const { data } = await api.post(`/${billId}/people`, { people })
  return data
}

/**
 * Set item assignments.
 * @param {string} billId
 * @param {Array<{line_item_id, shares}>} assignments
 */
export async function setAssignments(billId, assignments) {
  const { data } = await api.post(`/${billId}/assign`, { assignments })
  return data
}

/**
 * Compute the per-person breakdown.
 */
export async function computeBreakdown(billId) {
  const { data } = await api.get(`/${billId}/compute`)
  return data
}
