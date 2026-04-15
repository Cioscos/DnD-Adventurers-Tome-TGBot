import React from 'react'

interface SkeletonProps {
  width?: string
  height?: string
  rounded?: string
  className?: string
  delay?: number
}

function Line({ width = '100%', height = '14px', className = '', delay = 0 }: SkeletonProps) {
  return (
    <div
      className={`animate-skeleton rounded ${className}`}
      style={{ width, height, animationDelay: `${delay}ms` }}
    />
  )
}

function Circle({ width = '40px', height, className = '', delay = 0 }: SkeletonProps) {
  return (
    <div
      className={`animate-skeleton rounded-full ${className}`}
      style={{ width, height: height ?? width, animationDelay: `${delay}ms` }}
    />
  )
}

function Rect({ width = '100%', height = '80px', rounded = 'rounded-2xl', className = '', delay = 0 }: SkeletonProps) {
  return (
    <div
      className={`animate-skeleton ${rounded} ${className}`}
      style={{ width, height, animationDelay: `${delay}ms` }}
    />
  )
}

const Skeleton = { Line: React.memo(Line), Circle: React.memo(Circle), Rect: React.memo(Rect) }
export default Skeleton
