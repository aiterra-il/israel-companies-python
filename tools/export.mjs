import { writeFileSync } from 'node:fs'
import {
  buildNameQuery,
  checkCompanyNumber,
  cleanText,
  corporatePrefixes,
  entityOf,
  isValidIsraeliId,
  searchCompanies,
  statusCatalog,
  statusInfo,
  toCompany,
  typeInfo,
  violationCatalog,
} from '../../israel-companies/index.js'

const [dataPath, fixturesPath] = process.argv.slice(2)

const snake = (name) => name.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase()
const snakeKeys = (value) => {
  if (Array.isArray(value)) return value.map(snakeKeys)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([name, item]) => [snake(name), snakeKeys(item)]))
  }
  return value
}
const pyLiteral = (value) => {
  if (value === null || value === undefined) return 'None'
  if (typeof value === 'boolean') return value ? 'True' : 'False'
  if (typeof value === 'number' || typeof value === 'string') return JSON.stringify(value)
  if (Array.isArray(value)) return `(\n${value.map((item) => `    ${pyLiteral(item)},`).join('\n')}\n)`
  return `{${Object.entries(value).map(([name, item]) => `${JSON.stringify(name)}: ${pyLiteral(item)}`).join(', ')}}`
}

writeFileSync(
  dataPath,
  [
    `CORPORATE_PREFIXES = ${pyLiteral(corporatePrefixes)}`,
    `STATUS_CATALOG = ${pyLiteral(statusCatalog)}`,
    `VIOLATION_CATALOG = ${pyLiteral(violationCatalog)}`,
    '',
  ].join('\n'),
)

let seed = 20261126
const random = () => {
  seed = (seed + 0x6d2b79f5) | 0
  let t = seed
  t = Math.imul(t ^ (t >>> 15), t | 1)
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296
}
const pick = (list) => list[Math.floor(random() * list.length)]
const between = (low, high) => low + Math.floor(random() * (high - low + 1))
const digits = (count) => Array.from({ length: count }, () => between(0, 9)).join('')
const WEIGHTS = [1, 2, 1, 2, 1, 2, 1, 2, 1]
const withCheckDigit = (base) => {
  const sum = [...base].reduce((total, char, index) => {
    const product = Number(char) * WEIGHTS[index]
    return total + (product > 9 ? product - 9 : product)
  }, 0)
  return `${base}${(10 - (sum % 10)) % 10}`
}
const decorate = (number) => {
  const style = between(0, 6)
  if (style === 0) return `${number.slice(0, 2)}-${number.slice(2, 5)}-${number.slice(5)}`
  if (style === 1) return ` ${number.slice(0, 3)} ${number.slice(3)} `
  if (style === 2) return `${number.slice(0, 4)}.${number.slice(4)}`
  if (style === 3) return `‏${number}‎`
  if (style === 4) return `${number.slice(0, 2)}־${number.slice(2)}`
  return number
}

const numbers = [
  '', ' ', 'abc', '51-abc', '000000000', '0', '123456782', '12345678', '1234567890', 515090004, 513257873, '520044322', '580000003', '560000008',
  ...Array.from({ length: 140 }, () => decorate(withCheckDigit(`${pick(['51', '52', '53', '54', '55', '56', '57', '58', '59', '50', '0', '3'])}${digits(6)}`.slice(0, 8).padEnd(8, '0')))),
  ...Array.from({ length: 80 }, () => decorate(`${pick(['51', '52', '56', '58'])}${digits(7)}`)),
  ...Array.from({ length: 40 }, () => digits(between(1, 12))),
  ...Array.from({ length: 20 }, () => withCheckDigit(digits(8)).slice(between(0, 3))),
]

const cleanInputs = [
  null, '', '  a   b  ', 'בע~מ', 'בע~מ ~quoted~', 'א~', '~א', 'מ~ב~ג', ' x ', 'tab\there', 123, true,
  ...Array.from({ length: 200 }, () => Array.from({ length: between(1, 12) }, () => pick(['א', 'ב', 'ת', '~', ' ', '  ', 'a', 'Z', '1', '\n', '"', '״'])).join('')),
]

const names = [
  '', ' ', 'a', 'בע"מ', 'אייטרה', 'אייטרה בע"מ', 'Aiterra Ltd', 'teva', 'טבע', 'בנק הפועלים', 'בנק הפועלים בע~מ', 'Check Point', 'צ׳ק פוינט', 'שטראוס', 'שופרסל', 'אל על', 'Mobileye', 'ב', 'ab', 'a b c d e f g h i j', 'מגדל ביטוח limited', 'אלביט מערכות Ltd', 'Hot Mobile', 'בזק', 'סלקום', 'פרטנר', 'הראל', 'כלל', 'מנורה', 'IBM', 'גוגל ישראל',
  ...Array.from({ length: 180 }, () => Array.from({ length: between(1, 5) }, () => pick(['חברה', 'בע"מ', 'ישראל', 'טכנולוגיות', 'ltd', 'tech', 'אחזקות', 'נדל"ן', 'ש.', 'בע', 'מ', 'Group', 'קבוצת', 'a', 'בנייה', '1', '(1999)', 'השקעות', 'limited', 'Ltd.'])).join(pick([' ', ' ', '-', ', ']))),
]

const raw = []
const capturing = async (url, init) => {
  const response = await fetch(url, init)
  const text = await response.text()
  raw.push({ url: String(url), body: JSON.parse(text) })
  return new Response(text, { status: response.status, headers: response.headers })
}

const HEBREW_WORDS = ['גשר', 'נתיב', 'מעגל', 'רימון', 'נחל', 'גבעה', 'שקד', 'צפון', 'מרכז', 'פסגה', 'יסוד', 'מקור', 'דגן', 'מגדלור', 'מפעל', 'סחר', 'שירותי', 'פתרונות', 'מערכות', 'תעשיות']
const LATIN_WORDS = ['NORTH', 'BRIDGE', 'DELTA', 'SUMMIT', 'VECTOR', 'ORBIT', 'PRIME', 'CORE', 'FIELD', 'HARBOR']
const STREETS = ['הגפן', 'התאנה', 'הזית', 'השקד', 'הרימון', 'הדקל', 'האלה', 'הנרקיס']
const CARE_OF_HEBREW = ['רו~ח דוגמה ושות~', 'משרד עורכי דין דוגמה', 'חברת ניהול דוגמה בע~מ', 'הנהלת חשבונות דוגמה']
const CARE_OF_LATIN = ['C/O EXAMPLE ADVISORS', 'C/O SAMPLE TRUST SERVICES']
const KEEP_TOKENS = /^(בע~מ|בעמ|בע"מ|LTD\.?|LIMITED|INC\.?|\(?\d+\)?|[-–&,.]+)$/i
const FIELD_NAMES = { number: 'מספר חברה', name: 'שם חברה', english: 'שם באנגלית', street: 'שם רחוב', house: 'מספר בית', zip: 'מיקוד', poBox: 'ת.ד.', careOf: 'אצל', description: 'תאור חברה', purpose: 'מטרת החברה' }

const letters = (token) => token.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')
const sameKind = (text, word) => (/[a-z]/.test(text) && text === text.toLowerCase() ? word.toLowerCase() : word)

const synthName = (value, queryToken) => {
  if (typeof value !== 'string' || !value.trim()) return value
  const made = rebuildName(value, queryToken)
  if (made !== value) return made
  const [head, ...rest] = made.split(' ')
  const latin = /[A-Za-z]/.test(head) && !/[א-ת]/.test(head)
  return [head, latin ? sameKind(head, pick(LATIN_WORDS)) : pick(HEBREW_WORDS), ...rest].join(' ')
}

const rebuildName = (value, queryToken) => {
  let first = true
  return value
    .split(/(\s+)/)
    .map((part) => {
      if (!part || /^\s+$/.test(part)) return part
      const isFirst = first
      first = false
      if (KEEP_TOKENS.test(part)) return part
      const latin = /[A-Za-z]/.test(part) && !/[א-ת]/.test(part)
      if (isFirst && queryToken && (latin === /[a-z]/.test(queryToken))) {
        const token = letters(part)
        if (token === queryToken) return latin ? sameKind(part, queryToken.toUpperCase()) : queryToken
        if (token.startsWith(queryToken)) return latin ? sameKind(part, `${queryToken.toUpperCase()}ON`) : `${queryToken}ית`
      }
      return latin ? sameKind(part, pick(LATIN_WORDS)) : pick(HEBREW_WORDS)
    })
    .join('')
}

const syntheticNumbers = new Map()
const synthNumber = (value) => {
  const text = String(value ?? '')
  if (!/^\d{9}$/.test(text)) return value
  if (!syntheticNumbers.has(text)) {
    let candidate
    do candidate = withCheckDigit(`${text.slice(0, 2)}${digits(6)}`)
    while ([...syntheticNumbers.values()].includes(candidate) || originalNumbers.has(candidate))
    syntheticNumbers.set(text, candidate)
  }
  const synthetic = syntheticNumbers.get(text)
  return typeof value === 'number' ? Number(synthetic) : synthetic
}

const sameDigits = (value) => {
  const text = String(value ?? '')
  if (!/\d/.test(text)) return value
  const replaced = text.replace(/\d/g, (_, index) => String(index === 0 ? between(1, 9) : between(0, 9)))
  return typeof value === 'number' ? Number(replaced) : replaced
}

const synthHouse = (value) => {
  const text = String(value ?? '')
  if (!text.trim()) return value
  const number = String(between(1, 120))
  const shaped = /[א-ת]/.test(text) ? `${number}א` : number
  return typeof value === 'number' ? Number(number) : shaped
}

const textCounts = new Map()
const commonText = (field) => [...textCounts.entries()].filter(([key]) => key.startsWith(`${field}|`)).sort((a, b) => b[1] - a[1])[0]?.[0].slice(field.length + 1) ?? ''

const deidentify = (record, queryToken) => {
  const copy = { ...record }
  const set = (field, make) => {
    if (field in copy) copy[field] = make(copy[field])
  }
  set(FIELD_NAMES.number, synthNumber)
  set(FIELD_NAMES.name, (value) => synthName(value, /[a-z]/.test(queryToken) ? '' : queryToken))
  set(FIELD_NAMES.english, (value) => synthName(value, /[a-z]/.test(queryToken) ? queryToken : ''))
  set(FIELD_NAMES.street, (value) => (typeof value === 'string' && value.trim() ? pick(STREETS) : value))
  set(FIELD_NAMES.house, synthHouse)
  set(FIELD_NAMES.zip, sameDigits)
  set(FIELD_NAMES.poBox, sameDigits)
  set(FIELD_NAMES.careOf, (value) => {
    if (typeof value !== 'string' || !value.trim()) return value
    return /[א-ת]/.test(value) ? pick(CARE_OF_HEBREW) : pick(CARE_OF_LATIN)
  })
  for (const field of [FIELD_NAMES.description, FIELD_NAMES.purpose]) {
    set(field, (value) => {
      if (typeof value !== 'string' || !value.trim()) return value
      return (textCounts.get(`${field}|${value}`) ?? 0) >= 5 ? value : commonText(field)
    })
  }
  return copy
}

const searchNames = ['בנק', 'טבע', 'אלביט', 'שופרסל', 'Check Point', 'teva', 'מגדל', 'אחזקות', 'אל על', 'הראל']
const captured = []
for (const name of searchNames) {
  const before = raw.length
  await searchCompanies(name, { fetch: capturing, timeoutMs: 60000, limit: 50 })
  captured.push({ name, records: raw[before].body.result.records })
  await new Promise((resolve) => setTimeout(resolve, 1500))
}
for (const { records: found } of captured) {
  for (const record of found) {
    for (const field of [FIELD_NAMES.description, FIELD_NAMES.purpose]) {
      const value = record[field]
      if (typeof value === 'string' && value.trim()) textCounts.set(`${field}|${value}`, (textCounts.get(`${field}|${value}`) ?? 0) + 1)
    }
  }
}
const originalNumbers = new Set(captured.flatMap(({ records: found }) => found.map((record) => String(record[FIELD_NAMES.number]))))
const searches = []
for (const { name, records: found } of captured) {
  const queryToken = letters(name.split(/\s+/)[0])
  const records = found.map((record) => deidentify(record, queryToken))
  const fake = async () => new Response(JSON.stringify({ success: true, result: { records } }), { status: 200 })
  const ranked = await searchCompanies(name, { fetch: fake, limit: 50 })
  searches.push({ name, records, limit: 50, result: ranked.map((company) => company.number) })
}

const synthetic = [
  {},
  { 'מספר חברה': 510000003, 'שם חברה': 'בדיקה  בע~מ', 'סטטוס חברה': 'פעילה', 'מפרה': 'מפרה', 'תת סטטוס': 'א; ב;א ;', 'תאריך התאגדות': '1/2/1999', 'חברה ממשלתית': 'כן', 'מגבלות': 'מוגבלת', 'שנה אחרונה של דוח שנתי (שהוגש)': '2023', 'שם רחוב': 'הרצל', 'מספר בית': 5, 'סוג תאגיד': 'ישראלית חברה פרטית' },
  { 'סטטוס חברה': 'מחוקה', 'מפרה': 'התראה', 'שנה אחרונה של דוח שנתי (שהוגש)': 1900, 'סוג תאגיד': 'משהו אחר', 'תאריך התאגדות': '1999-02-01' },
  { 'סטטוס חברה': 'לא ידוע', 'שנה אחרונה של דוח שנתי (שהוגש)': '2020.5', 'מדינה': 'ארה"ב' },
]
const records = [...searches.flatMap((search) => search.records), ...synthetic]
const pool = searches.flatMap((search) => search.records)
const rankings = []
for (const name of [...searchNames, ...names]) {
  const start = between(0, pool.length - 1)
  const indices = Array.from({ length: between(0, 100) }, (_, offset) => (start + offset * 7) % pool.length)
  const limit = pick([20, 5, 50, 1])
  let url = null
  const fake = async (address) => {
    url = String(address)
    return new Response(JSON.stringify({ success: true, result: { records: indices.map((index) => pool[index]) } }), { status: 200 })
  }
  const found = await searchCompanies(name, { fetch: fake, limit })
  rankings.push({ name, indices, limit, url, result: found.map((company) => company.number) })
}

const fixtures = {
  numbers: numbers.map((value) => ({ value, valid_id: isValidIsraeliId(value), entity: entityOf(value), check: snakeKeys(checkCompanyNumber(value)) })),
  clean_text: cleanInputs.map((value) => [value, cleanText(value)]),
  status_info: [...statusCatalog.map((entry) => entry.status), 'לא ידוע', ''].map((status) => [status, statusInfo(status)]),
  type_info: ['ישראלית חברה פרטית', 'ישראלית חברה ציבורית', 'ישראלית חברה אגח', 'חוץ חברה פרטית', 'חוץ חברה ציבורית', 'אחר', ''].map((type) => [type, typeInfo(type)]),
  name_query: names.map((name) => [name, buildNameQuery(name)]),
  companies: records.map((record) => ({ record, company: snakeKeys(toCompany(record)) })),
  searches: searches.map(({ name, records: found, limit, result }) => ({ name, records: found, limit, result })),
  search_urls: raw.map((entry) => entry.url),
  rankings,
}

writeFileSync(fixturesPath, `${JSON.stringify(fixtures)}\n`)
console.log(JSON.stringify(Object.fromEntries(Object.entries(fixtures).map(([name, cases]) => [name, cases.length]))))
