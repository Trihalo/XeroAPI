// src/components/RecruiterStatus.jsx
function RecruiterStatus({ name, isSubmitted }) {
  return (
    <div className="flex items-center space-x-2 text-sm">
      <span>{isSubmitted ? "✅" : "❌"}</span>
      <span>{name}</span>
    </div>
  );
}

export default RecruiterStatus;
