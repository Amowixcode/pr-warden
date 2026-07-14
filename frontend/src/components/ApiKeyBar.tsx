export function ApiKeyBar({
  apiKey,
  onChange,
}: {
  apiKey: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="api-key-bar">
      <label htmlFor="api-key-input" className="api-key-note">
        API key
      </label>
      <input
        id="api-key-input"
        type="password"
        value={apiKey}
        onChange={(e) => onChange(e.target.value)}
        placeholder="X-API-Key"
        autoComplete="off"
      />
      <span className="api-key-note">
        Stored only in your browser's local storage — a demo convenience, not real security.
        Don't use a key you wouldn't want exposed.
      </span>
    </div>
  );
}
