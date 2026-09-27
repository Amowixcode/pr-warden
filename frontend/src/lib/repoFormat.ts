/** Parses an "owner/repo" string, returning null if it doesn't match that shape. */
export function parseOwnerRepo(input: string): [owner: string, repo: string] | null {
  const parts = input.split("/");
  if (parts.length !== 2 || !parts[0] || !parts[1]) {
    return null;
  }
  return [parts[0], parts[1]];
}
