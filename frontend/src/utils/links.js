/**
 * Build a `tel:` href from a display phone string. Strips all non-digits
 * and prepends +1 if the result looks like a 10-digit US number without a
 * country code. Returns an empty string if there are no digits.
 */
export function phoneHref(phone) {
  if (!phone) return ''
  const digits = String(phone).replace(/\D+/g, '')
  if (!digits) return ''
  const withCountry = digits.length === 10 ? `+1${digits}` : `+${digits}`
  return `tel:${withCountry}`
}

/**
 * Build an Apple Maps search URL from a free-form address string. Marcus
 * uses iPhone so Apple Maps is the primary target; on other platforms
 * the URL still opens in a browser-based map viewer.
 */
export function mapHref(address) {
  if (!address) return ''
  return `https://maps.apple.com/?q=${encodeURIComponent(address)}`
}
