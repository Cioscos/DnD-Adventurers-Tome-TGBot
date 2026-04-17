import SectionDivider from './ui/SectionDivider'

interface SectionHeaderProps {
  children: React.ReactNode
}

export default function SectionHeader({ children }: SectionHeaderProps) {
  return <SectionDivider>{children}</SectionDivider>
}
