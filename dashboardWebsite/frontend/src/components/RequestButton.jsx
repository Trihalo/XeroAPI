export default function RequestButton({ label, onClick }) {
  return (
    <button
      className="btn bg-base-200 text-primary px-4 py-2 rounded-lg shadow hover:bg-primary/20 transition"
      onClick={onClick}
    >
      {label}
    </button>
  );
}
