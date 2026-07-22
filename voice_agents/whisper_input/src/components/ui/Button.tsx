import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonTone = 'primary' | 'secondary' | 'danger';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  tone?: ButtonTone;
}

export function Button({ children, tone = 'secondary', className = '', ...props }: ButtonProps) {
  return (
    <button {...props} className={`ol-button ol-button-${tone} ${className}`.trim()}>
      {children}
    </button>
  );
}
