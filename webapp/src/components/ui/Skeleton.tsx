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

function Rect({
  width = '100%',
  height = '80px',
  rounded = 'rounded-2xl',
  className = '',
  delay = 0,
}: SkeletonProps) {
  return (
    <div
      className={`animate-skeleton ${rounded} ${className}`}
      style={{ width, height, animationDelay: `${delay}ms` }}
    />
  )
}

function Ornament({ width = '60%', className = '', delay = 0 }: SkeletonProps) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="animate-skeleton h-3 flex-1 rounded" style={{ animationDelay: `${delay}ms` }} />
      <div
        className="animate-skeleton w-3 h-3 rotate-45"
        style={{ animationDelay: `${delay + 80}ms` }}
      />
      <div className="animate-skeleton h-3 flex-1 rounded" style={{ animationDelay: `${delay + 160}ms`, width }} />
    </div>
  )
}

function Group({
  children,
  stagger = 60,
  className = '',
}: {
  children: React.ReactNode
  stagger?: number
  className?: string
}) {
  const items = React.Children.toArray(children)
  return (
    <div className={className}>
      {items.map((child, i) =>
        React.isValidElement(child)
          ? React.cloneElement(child as React.ReactElement<SkeletonProps>, {
              delay: (child.props as SkeletonProps).delay ?? i * stagger,
            })
          : child
      )}
    </div>
  )
}

const Skeleton = {
  Line: React.memo(Line),
  Circle: React.memo(Circle),
  Rect: React.memo(Rect),
  Ornament: React.memo(Ornament),
  Group,
}
export default Skeleton
