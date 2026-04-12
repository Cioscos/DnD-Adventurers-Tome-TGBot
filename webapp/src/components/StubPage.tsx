/**
 * Placeholder component for pages not yet fully implemented.
 * The user should replace these with real implementations following
 * the pattern of HP.tsx and Dice.tsx.
 */
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Layout from './Layout'
import Card from './Card'

interface StubPageProps {
  titleKey: string
  emoji: string
  description?: string
}

export default function StubPage({ titleKey, emoji, description }: StubPageProps) {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const title = t(titleKey, { defaultValue: titleKey })

  return (
    <Layout title={`${emoji} ${title}`} backTo={`/char/${id}`}>
      <Card>
        <div className="text-center py-6">
          <p className="text-4xl mb-3">{emoji}</p>
          <p className="font-semibold text-lg mb-2">{title}</p>
          <p className="text-sm text-[var(--tg-theme-hint-color)]">
            {description ?? 'Questa sezione è in costruzione.\nImplementazione in corso.'}
          </p>
        </div>
      </Card>
    </Layout>
  )
}
