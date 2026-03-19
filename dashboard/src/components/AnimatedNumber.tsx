import { motion } from 'motion/react';

interface AnimatedNumberProps {
  value: string | number;
  className?: string;
}

export function AnimatedNumber({ value, className = '' }: AnimatedNumberProps) {
  const str = typeof value === 'number' ? String(value) : value;
  return (
    <motion.span
      className={className}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {str}
    </motion.span>
  );
}
