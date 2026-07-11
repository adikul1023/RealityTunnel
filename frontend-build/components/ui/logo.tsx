import React from 'react'


interface LogoProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  className?: string
}

export function StealthyLogo({ className, ...props }: LogoProps) {
  return (
    <img
      src="/logo.jpg"
      alt="Stealthy Logo"
      className={className || 'h-8 w-8 object-contain'}
      {...props}
    />
  )
}
