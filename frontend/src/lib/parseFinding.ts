// The separator before the finding text needs at least one space on each side — that's what
// tells it apart from the plain hyphen inside a line range like "245-314", which has none.
const LOCATION_PATTERN = /^(\S+:\d+(?:-\d+)?)\s+[-–—]\s+(.+)$/su;

/**
 * Splits a real issue string like "path/to/file.py:89 - the finding text" into its location
 * and body. Real pipeline output sometimes uses an en-dash or em-dash instead of a hyphen for
 * the separator, and line ranges like "245-314" — both handled. Text that doesn't match this
 * shape (e.g. a finding about a removed file with no line number) comes back with
 * `location: null` and the full original text as the body — never dropped, never guessed at.
 */
export function parseFinding(text: string): { location: string | null; body: string } {
  const match = LOCATION_PATTERN.exec(text);
  if (!match) {
    return { location: null, body: text };
  }
  return { location: match[1], body: match[2] };
}
