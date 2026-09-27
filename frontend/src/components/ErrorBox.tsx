export function ErrorBox({ title, message }: { title: string; message: string }) {
  return (
    <div className="error-banner" role="alert">
      <p className="error-banner-title">{title}</p>
      <p className="error-banner-message">{message}</p>
    </div>
  );
}
