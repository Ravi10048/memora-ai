interface ConfidenceBadgeProps {
  value: number;
}

export default function ConfidenceBadge({ value }: ConfidenceBadgeProps) {
  const percent = Math.round(value * 100);
  const color =
    percent >= 80
      ? "text-emerald-400 bg-emerald-500/15"
      : percent >= 60
      ? "text-amber-400 bg-amber-500/15"
      : "text-red-400 bg-red-500/15";

  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>
      {percent}%
    </span>
  );
}
