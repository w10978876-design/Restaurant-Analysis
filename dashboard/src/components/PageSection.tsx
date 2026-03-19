interface PageSectionProps {
  /** 分区标签，如「经营概览」「销售与趋势」 */
  label?: string;
  children: React.ReactNode;
}

export function PageSection({ label, children }: PageSectionProps) {
  return (
    <section className="space-y-4">
      {label && (
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
            {label}
          </span>
          <span className="h-px flex-1 bg-gray-200" aria-hidden />
        </div>
      )}
      {children}
    </section>
  );
}
