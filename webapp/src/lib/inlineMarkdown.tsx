import React from 'react'

/**
 * Minimal, dependency-free inline-markdown renderer for note previews.
 *
 * Notes are authored in light markdown (`**bold**`, `*italic*`, `` `code` ``);
 * the card preview was showing the literal markers. Rather than pull in a full
 * markdown library (none is present in the project) we tokenize the common
 * INLINE constructs and build React nodes — no `dangerouslySetInnerHTML`, so
 * there is no HTML-injection surface. Block constructs (headings, lists) are
 * intentionally not handled; newlines are preserved by the caller's
 * `whitespace-pre-wrap`.
 *
 * Supported: **bold** / __bold__, *italic* / _italic_, `code`.
 */

// Bold (** or __), italic (* or _), or inline code (`...`). Bold alternatives
// come first so `**` is consumed before a single `*`.
const TOKEN = /(\*\*|__)([\s\S]+?)\1|(\*|_)([\s\S]+?)\3|`([^`]+?)`/g

export function renderInlineMarkdown(input: string): React.ReactNode {
  if (!input) return input
  const nodes: React.ReactNode[] = []
  let lastIndex = 0
  let key = 0
  let match: RegExpExecArray | null

  TOKEN.lastIndex = 0
  while ((match = TOKEN.exec(input)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(input.slice(lastIndex, match.index))
    }
    if (match[1]) {
      nodes.push(<strong key={key++}>{match[2]}</strong>)
    } else if (match[3]) {
      nodes.push(<em key={key++}>{match[4]}</em>)
    } else if (match[5]) {
      nodes.push(
        <code key={key++} className="px-1 rounded bg-dnd-surface-raised font-mono text-[0.85em]">
          {match[5]}
        </code>,
      )
    }
    lastIndex = TOKEN.lastIndex
  }

  if (lastIndex < input.length) {
    nodes.push(input.slice(lastIndex))
  }

  return nodes
}
