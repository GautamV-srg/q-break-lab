import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="page prose-page">
      <h1>Page not found</h1>
      <p>
        <Link to="/">Back to Q-Break →</Link>
      </p>
    </div>
  );
}
