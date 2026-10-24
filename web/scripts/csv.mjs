// Minimal CSV read/write for the headless simulation run. No dependency, and
// no build step: this script is run by `make reroute` and by hand.
import { readFileSync, writeFileSync } from 'node:fs'

/** RFC 4180-ish parser: quoted fields, embedded commas and newlines. */
export function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i++
        } else quoted = false
      } else field += ch
    } else if (ch === '"') {
      quoted = true
    } else if (ch === ',') {
      row.push(field)
      field = ''
    } else if (ch === '\n') {
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else if (ch !== '\r') {
      field += ch
    }
  }
  if (field.length || row.length) {
    row.push(field)
    rows.push(row)
  }
  if (!rows.length) return []
  const head = rows[0].map((h) => h.trim())
  return rows.slice(1).filter((r) => r.length > 1 || (r.length === 1 && r[0] !== '')).map((r) => {
    const obj = {}
    head.forEach((h, i) => {
      obj[h] = (r[i] ?? '').trim()
    })
    return obj
  })
}

export function readCsv(path) {
  return parseCsv(readFileSync(path, 'utf8'))
}

/** Stable column order; `undefined`/`null` become an empty field. */
export function writeCsv(path, columns, rows) {
  const esc = (v) => {
    if (v === undefined || v === null) return ''
    const s = String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = [columns.join(','), ...rows.map((r) => columns.map((c) => esc(r[c])).join(','))]
  writeFileSync(path, `${lines.join('\n')}\n`)
}
